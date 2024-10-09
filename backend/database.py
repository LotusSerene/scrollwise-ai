from flask_sqlalchemy import SQLAlchemy
import sqlite3
import uuid
import json
import logging

db = SQLAlchemy()

class Character(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    @classmethod
    def get_or_create(cls, name, description, user_id):
        existing_character = cls.query.filter_by(name=name, user_id=user_id).first()
        if existing_character:
            return existing_character
        new_character = cls(name=name, description=description, user_id=user_id)
        db.session.add(new_character)
        db.session.commit()
        return new_character

class Chapter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    chapter_number = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'chapter_number': self.chapter_number
        }

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE,
                password TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS chapters (
                id TEXT PRIMARY KEY,
                name TEXT,
                content TEXT,
                title TEXT
            )
        ''')
        self.cursor.execute('''
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
                FOREIGN KEY (chapter_id) REFERENCES chapters (id)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT
            )
        ''')
        self.conn.commit()
        
        # Add the chapter_title column if it doesn't exist
        self.cursor.execute('PRAGMA table_info(validity_checks)')
        columns = [column[1] for column in self.cursor.fetchall()]
        if 'chapter_title' not in columns:
            self.cursor.execute('ALTER TABLE validity_checks ADD COLUMN chapter_title TEXT')
            self.conn.commit()

    def create_user(self, email, password):
        user_id = uuid.uuid4().hex
        self.cursor.execute('INSERT INTO users (id, email, password) VALUES (?, ?, ?)', (user_id, email, password))
        self.conn.commit()
        return user_id

    def get_user_by_email(self, email):
        self.cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        row = self.cursor.fetchone()
        return {'id': row[0], 'email': row[1], 'password': row[2]} if row else None

    def get_all_chapters(self):
        self.cursor.execute('SELECT * FROM chapters')
        return [{'id': row[0], 'name': row[1], 'content': row[2], 'title': row[3]} for row in self.cursor.fetchall()]

    def create_chapter(self, title, content):
        chapter_id = str(uuid.uuid4())
        self.cursor.execute('''
            INSERT INTO chapters (id, title, content)
            VALUES (?, ?, ?)
        ''', (chapter_id, title, content))
        self.conn.commit()
        return chapter_id

    def update_chapter(self, chapter_id, title, content):
        self.cursor.execute('''
            UPDATE chapters
            SET content = ?, title = ?
            WHERE id = ?
        ''', (content, title, chapter_id))
        self.conn.commit()
        return self.get_chapter(chapter_id)

    def delete_chapter(self, chapter_id):
        self.cursor.execute('DELETE FROM chapters WHERE id = ?', (chapter_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get_chapter(self, chapter_id):
        self.cursor.execute('SELECT * FROM chapters WHERE id = ?', (chapter_id,))
        row = self.cursor.fetchone()
        return {'id': row[0], 'name': row[1], 'content': row[2], 'title': row[3]} if row else None

    def save_validity_check(self, chapter_id, chapter_title, validity):
        self.cursor.execute('''
            INSERT INTO validity_checks (id, chapter_id, chapter_title, is_valid, feedback, review, style_guide_adherence, style_guide_feedback, continuity, continuity_feedback, test_results)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            validity.get('test_results', '')
        ))
        self.conn.commit()

    def get_all_validity_checks(self):
        self.cursor.execute('SELECT * FROM validity_checks')
        return [
            {
                'id': row[0],
                'chapterId': row[1],
                'chapterTitle': row[2],
                'isValid': bool(row[3]),
                'feedback': row[4],
                'review': row[5],
                'style_guide_adherence': bool(row[6]),
                'style_guide_feedback': row[7],
                'continuity': bool(row[8]),
                'continuity_feedback': row[9],
                'test_results': row[10]
            }
            for row in self.cursor.fetchall()
        ]

    def delete_validity_check(self, check_id):
        self.cursor.execute('DELETE FROM validity_checks WHERE id = ?', (check_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def create_character(self, name: str, description: str) -> str:
        character_id = uuid.uuid4().hex
        self.cursor.execute('INSERT INTO characters (id, name, description) VALUES (?, ?, ?)', (character_id, name, description))
        self.conn.commit()
        return character_id

    def get_all_characters(self):
        self.cursor.execute('SELECT * FROM characters')
        return [{'id': row[0], 'name': row[1], 'description': row[2]} for row in self.cursor.fetchall()]

    def update_character(self, character_id: str, name: str, description: str):
        self.cursor.execute('''
            UPDATE characters
            SET name = ?, description = ?
            WHERE id = ?
        ''', (name, description, character_id))
        self.conn.commit()

    def delete_character(self, character_id: str):
        self.cursor.execute('DELETE FROM characters WHERE id = ?', (character_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get_chapter_count(self):
        self.cursor.execute("SELECT COUNT(*) FROM chapters")
        count = self.cursor.fetchone()[0]
        return count

db = Database('novel_generator.db')

def get_chapter_count():
    return len(db.get_all_chapters())
