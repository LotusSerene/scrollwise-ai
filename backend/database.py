# backend/database.py
from flask_sqlalchemy import SQLAlchemy
import sqlite3
import uuid
import json
import logging

db = SQLAlchemy()

class Character(db.Model):
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.String, nullable=False)

    @classmethod
    def get_or_create(cls, user_id, name, description):
        existing_character = cls.query.filter_by(user_id=user_id, name=name).first()
        if existing_character:
            return existing_character
        new_character = cls(id=str(uuid.uuid4()), name=name, description=description, user_id=user_id)
        db.session.add(new_character)
        db.session.commit()
        return new_character

class Chapter(db.Model):
    id = db.Column(db.String, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    chapter_number = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.String, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'chapter_number': self.chapter_number
        }

class ValidityCheck(db.Model):
    id = db.Column(db.String, primary_key=True)
    chapter_id = db.Column(db.String, nullable=False)
    chapter_title = db.Column(db.String, nullable=False)
    is_valid = db.Column(db.Boolean, nullable=False)
    feedback = db.Column(db.Text, nullable=False)
    review = db.Column(db.Text, nullable=True)
    style_guide_adherence = db.Column(db.Boolean, nullable=True)
    style_guide_feedback = db.Column(db.Text, nullable=True)
    continuity = db.Column(db.Boolean, nullable=True)
    continuity_feedback = db.Column(db.Text, nullable=True)
    test_results = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.String, nullable=False)

class ChatHistory(db.Model):
    id = db.Column(db.String, primary_key=True)
    user_id = db.Column(db.String, nullable=False)
    messages = db.Column(db.Text, nullable=False)

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE,
                password TEXT,
                api_key TEXT,
                model_settings TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chapters (
                id TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                chapter_number INTEGER,
                user_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS validity_checks (
                id TEXT PRIMARY KEY,
                chapter_id TEXT,
                chapter_title TEXT,
                is_valid INTEGER,
                feedback TEXT,
                review TEXT,
                style_guide_adherence INTEGER,
                style_guide_feedback TEXT,
                continuity INTEGER,
                continuity_feedback TEXT,
                test_results TEXT,
                user_id TEXT,
                FOREIGN KEY (chapter_id) REFERENCES chapters (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                user_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                messages TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        self.conn.commit()
        
        # Add the chapter_title column if it doesn't exist
        cursor.execute('PRAGMA table_info(validity_checks)')
        columns = [column[1] for column in cursor.fetchall()]
        if 'chapter_title' not in columns:
            cursor.execute('ALTER TABLE validity_checks ADD COLUMN chapter_title TEXT')
            self.conn.commit()
        
        # Ensure all columns are present
        required_columns = ['id', 'chapter_id', 'chapter_title', 'is_valid', 'feedback', 'review', 'style_guide_adherence', 'style_guide_feedback', 'continuity', 'continuity_feedback', 'test_results', 'user_id']
        for column in required_columns:
            if column not in columns:
                cursor.execute(f'ALTER TABLE validity_checks ADD COLUMN {column} TEXT')
                self.conn.commit()
        
        # Ensure the api_key column exists in the users table
        cursor.execute('PRAGMA table_info(users)')
        columns = [column[1] for column in cursor.fetchall()]
        if 'api_key' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN api_key TEXT')
            self.conn.commit()
        
        # Add the model_settings column if it doesn't exist
        cursor.execute('PRAGMA table_info(users)')
        columns = [column[1] for column in cursor.fetchall()]
        if 'model_settings' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN model_settings TEXT')
            self.conn.commit()
        
        cursor.close()

    def create_user(self, email, password):
        cursor = self.conn.cursor()
        user_id = uuid.uuid4().hex
        cursor.execute('INSERT INTO users (id, email, password) VALUES (?, ?, ?)', (user_id, email, password))
        self.conn.commit()
        cursor.close()
        return user_id

    def get_user_by_email(self, email):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()
        cursor.close()
        if row:
            # Ensure the row has the expected number of columns
            if len(row) == 5:
                return {'id': row[0], 'email': row[1], 'password': row[2], 'api_key': row[3], 'model_settings': row[4]}
            else:
                # If the row has fewer columns, handle it gracefully
                return {'id': row[0], 'email': row[1], 'password': row[2], 'api_key': None, 'model_settings': None}
        return None

    def get_all_chapters(self, user_id: str):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM chapters WHERE user_id = ? ORDER BY chapter_number', (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        return [{'id': row[0], 'title': row[1], 'content': row[2], 'chapter_number': row[3]} for row in rows]

    def create_chapter(self, title, content, user_id):
        chapter_id = str(uuid.uuid4())
        chapter_number = self.get_chapter_count(user_id) + 1
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO chapters (id, title, content, chapter_number, user_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (chapter_id, title, content, chapter_number, user_id))
        self.conn.commit()
        cursor.close()
        return {
            'id': chapter_id,
            'title': title,
            'content': content,
            'chapter_number': chapter_number
        }

    def update_chapter(self, chapter_id, title, content, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE chapters
            SET content = ?, title = ?
            WHERE id = ? AND user_id = ?
        ''', (content, title, chapter_id, user_id))
        self.conn.commit()
        cursor.close()
        return self.get_chapter(chapter_id, user_id)

    def delete_chapter(self, chapter_id, user_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM chapters WHERE id = ? AND user_id = ?', (chapter_id, user_id))
        self.conn.commit()
        cursor.close()
        return cursor.rowcount > 0

    def get_chapter(self, chapter_id, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM chapters WHERE id = ? AND user_id = ?', (chapter_id, user_id))
        row = cursor.fetchone()
        cursor.close()
        return {'id': row[0], 'title': row[1], 'content': row[2], 'chapter_number': row[3]} if row else None

    def save_validity_check(self, chapter_id, chapter_title, validity, user_id):
        cursor = self.conn.cursor()
        logging.debug(f"Inserting validity check: id={uuid.uuid4().hex}, chapter_id={chapter_id}, chapter_title={chapter_title}, is_valid={1 if validity['is_valid'] else 0}, feedback={validity['feedback']}, review={validity.get('review', '')}, style_guide_adherence={1 if validity.get('style_guide_adherence', False) else 0}, style_guide_feedback={validity.get('style_guide_feedback', '')}, continuity={1 if validity.get('continuity', False) else 0}, continuity_feedback={validity.get('continuity_feedback', '')}, test_results={validity.get('test_results', '')}, user_id={user_id}")
        cursor.execute('''
            INSERT INTO validity_checks (id, chapter_id, chapter_title, is_valid, feedback, review, style_guide_adherence, style_guide_feedback, continuity, continuity_feedback, test_results, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            uuid.uuid4().hex,
            chapter_id,
            chapter_title,
            1 if validity['is_valid'] else 0,
            validity['feedback'],
            validity.get('review', ''),
            1 if validity.get('style_guide_adherence', False) else 0,
            validity.get('style_guide_feedback', ''),
            1 if validity.get('continuity', False) else 0,
            validity.get('continuity_feedback', ''),
            validity.get('test_results', ''),
            user_id
        ))
        self.conn.commit()
        cursor.close()

    def get_all_validity_checks(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM validity_checks WHERE user_id = ?', (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        return [
            {
                'id': row[0],
                'chapterId': row[1],
                'chapterTitle': row[2],
                'isValid': bool(row[3]),
                'feedback': row[4],
                'review': row[5] if len(row) > 5 else None,
                'style_guide_adherence': bool(row[6]) if len(row) > 6 else None,
                'style_guide_feedback': row[7] if len(row) > 7 else None,
                'continuity': bool(row[8]) if len(row) > 8 else None,
                'continuity_feedback': row[9] if len(row) > 9 else None,
                'test_results': row[10] if len(row) > 10 else None
            }
            for row in rows
        ]

    def delete_validity_check(self, check_id, user_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM validity_checks WHERE id = ? AND user_id = ?', (check_id, user_id))
        self.conn.commit()
        cursor.close()
        return cursor.rowcount > 0

    def create_character(self, name: str, description: str, user_id: str) -> str:
        cursor = self.conn.cursor()
        character_id = uuid.uuid4().hex
        cursor.execute('INSERT INTO characters (id, name, description, user_id) VALUES (?, ?, ?, ?)', (character_id, name, description, user_id))
        self.conn.commit()
        cursor.close()
        return character_id

    def get_all_characters(self, user_id: str):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM characters WHERE user_id = ?', (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        return [{'id': row[0], 'name': row[1], 'description': row[2]} for row in rows]

    def update_character(self, character_id: str, name: str, description: str, user_id: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE characters
            SET name = ?, description = ?
            WHERE id = ? AND user_id = ?
        ''', (name, description, character_id, user_id))
        self.conn.commit()
        cursor.close()

    def delete_character(self, character_id: str, user_id: str):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM characters WHERE id = ? AND user_id = ?', (character_id, user_id))
        self.conn.commit()
        cursor.close()
        return cursor.rowcount > 0

    def get_chapter_count(self, user_id: str):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chapters WHERE user_id = ?", (user_id,))
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    def get_character_by_id(self, character_id: str, user_id: str):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM characters WHERE id = ? AND user_id = ?', (character_id, user_id))
        row = cursor.fetchone()
        cursor.close()
        return {'id': row[0], 'name': row[1], 'description': row[2]} if row else None

    def save_api_key(self, user_id: str, api_key: str):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE users SET api_key = ? WHERE id = ?', (api_key, user_id))
        self.conn.commit()
        cursor.close()

    def get_api_key(self, user_id: str) -> str:
        cursor = self.conn.cursor()
        cursor.execute('SELECT api_key FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else None

    def delete_from_knowledge_base(self, text: str, user_id: str):
        # Placeholder for the actual implementation
        pass

    def remove_api_key(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE users SET api_key = NULL WHERE id = ?', (user_id,))
        self.conn.commit()
        cursor.close()

    def save_model_settings(self, user_id: str, settings: dict):
        cursor = self.conn.cursor()
        settings_json = json.dumps(settings)
        cursor.execute('UPDATE users SET model_settings = ? WHERE id = ?', (settings_json, user_id))
        self.conn.commit()
        cursor.close()

    def get_model_settings(self, user_id: str) -> dict:
        cursor = self.conn.cursor()
        cursor.execute('SELECT model_settings FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        cursor.close()
        if row and row[0]:
            return json.loads(row[0])
        return {
            'mainLLM': 'gemini-1.5-pro-002',
            'checkLLM': 'gemini-1.5-pro-002',
            'embeddingsModel': 'models/text-embedding-004',
            'titleGenerationLLM': 'gemini-1.5-pro-002',
            'characterExtractionLLM': 'gemini-1.5-pro-002',
            'knowledgeBaseQueryLLM': 'gemini-1.5-pro-002'
        }

    def save_chat_history(self, user_id: str, messages: list):
        cursor = self.conn.cursor()
        messages_json = json.dumps(messages)
        cursor.execute('INSERT OR REPLACE INTO chat_history (id, user_id, messages) VALUES (?, ?, ?)',
                       (user_id, user_id, messages_json))
        self.conn.commit()
        cursor.close()

    def get_chat_history(self, user_id: str) -> list:
        cursor = self.conn.cursor()
        cursor.execute('SELECT messages FROM chat_history WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        cursor.close()
        return json.loads(row[0]) if row else []

db_instance = Database('novel_generator.db')

def get_chapter_count(user_id: str):
    return len(db_instance.get_all_chapters(user_id))