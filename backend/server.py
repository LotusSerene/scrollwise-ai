from flask import Flask, request, jsonify, Blueprint
from flask_cors import CORS
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
from dotenv import load_dotenv
import logging
import jwt
import datetime
import uuid
from database import db, get_chapter_count, Character
from agent_manager import AgentManager

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

# Load environment variables from .env file
load_dotenv()

# Secret key for JWT (replace with a strong secret in production)
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "your-secret-key")

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Create a test user if they don't already exist
if not db.get_user_by_email("test@example.com"):
    db.create_user("test@example.com", "password")

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"message": "Email and password are required"}), 400

        # Check if user already exists
        if db.get_user_by_email(email):
            return jsonify({"message": "User already exists"}), 400

        # Create new user
        db.create_user(email, password)
        return jsonify({"message": "User registered successfully"}), 201

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"message": "Email and password are required"}), 400

        # Check if user exists and password matches
        user = db.get_user_by_email(email)
        if user and user['password'] == password:
            # Generate JWT token
            payload = {
                "email": email,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # Token expires in 1 hour
            }
            token = jwt.encode(payload, JWT_SECRET_KEY)
            return jsonify({"token": token}), 200
        else:
            return jsonify({"message": "Invalid email or password"}), 401

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def generate_chapters():
    try:
        data = request.json
        logging.debug(f"Received data: {data}")
        
        num_chapters = int(data.get('numChapters', 1))
        plot = data.get('plot', '')
        writing_style = data.get('writingStyle', '')
        instructions = data.get('instructions', {})
        style_guide = instructions.get('styleGuide', '')
        api_key = data.get('apiKey', '')
        generation_model = data.get('generationModel', 'gemini-1.5-pro-002')
        check_model = data.get('checkModel', 'gemini-1.5-pro-002')
        min_word_count = int(instructions.get('minWordCount', 1000))
        characters = data.get('characters', {})
        
        logging.debug(f"Parsed data: num_chapters={num_chapters}, plot={plot[:50]}..., writing_style={writing_style[:50]}..., api_key={api_key[:5]}..., generation_model={generation_model}, check_model={check_model}, min_word_count={min_word_count}")
        
        if not api_key:
            return jsonify({'error': 'API Key is required'}), 400

        agent = AgentManager(api_key, generation_model, check_model)
        logging.debug("AgentManager initialized")

        generated_chapters = []
        validities = []

        # Get the current chapter count from the database
        current_chapter_count = get_chapter_count()
        logging.debug(f"Current chapter count: {current_chapter_count}")

        for i in range(num_chapters):
            chapter_number = current_chapter_count + i + 1
            logging.debug(f"Generating chapter {chapter_number}")
            previous_chapters = db.get_all_chapters()
            logging.debug(f"Retrieved {len(previous_chapters)} previous chapters")

            try:
                chapter_content, chapter_title, new_characters = agent.generate_chapter(
                    chapter_number=chapter_number,
                    plot=plot,
                    writing_style=writing_style,
                    instructions={
                        "general": instructions,
                        "style_guide": style_guide,
                        'min_word_count': min_word_count,
                        'chapter_number': chapter_number
                    },
                    characters=characters,  # This should be a dictionary of character names to descriptions
                    previous_chapters=previous_chapters
                )
                logging.debug(f"Chapter {chapter_number} generated successfully")
            except Exception as e:
                logging.error(f"Error generating chapter {chapter_number}: {str(e)}")
                raise

            # Check for new characters
            if new_characters:
                for name, description in new_characters.items():
                    db.create_character(name, description)
            
            # Save the chapter to the database
            chapter_id = db.create_chapter(f'Chapter {chapter_number}', chapter_content, chapter_number)
            
            # Get validity from the agent's check_chapter method
            validity = agent.check_chapter(chapter_content, instructions, previous_chapters)
            
            # Save validity to the database
            db.save_validity_check(chapter_id, validity)
            
            generated_chapters.append({
                'id': chapter_id,
                'content': chapter_content,
                'title': chapter_title,
                'new_characters': new_characters
            })
            validities.append(validity)

        return jsonify({'chapters': generated_chapters, 'validities': validities}), 200

    except Exception as e:
        logging.error(f"An error occurred in generate_chapters: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/chapters', methods=['GET'])
def get_chapters():
    try:
        chapters = db.get_all_chapters()
        logging.debug(f"Retrieved {len(chapters)} chapters")
        return jsonify({'chapters': chapters}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chapters/<chapter_id>', methods=['PUT'])
def update_chapter(chapter_id):
    try:
        data = request.json
        updated_chapter = db.update_chapter(chapter_id, data.get('title'), data.get('content'))
        if updated_chapter:
            return jsonify(updated_chapter), 200
        else:
            return jsonify({'error': 'Chapter not found'}), 404
    except Exception as e:
        logging.error(f"Error updating chapter: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chapters/<chapter_id>', methods=['DELETE'])
def delete_chapter(chapter_id):
    try:
        if db.delete_chapter(chapter_id):
            return jsonify({'message': 'Chapter deleted successfully'}), 200
        else:
            return jsonify({'error': 'Chapter not found'}), 404
    except Exception as e:
        logging.error(f"Error deleting chapter: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/validity-checks', methods=['GET'])
def get_validity_checks():
    try:
        validity_checks = db.get_all_validity_checks()
        return jsonify({'validityChecks': validity_checks}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/validity-checks/<check_id>', methods=['DELETE'])
def delete_validity_check(check_id):
    try:
        if db.delete_validity_check(check_id):
            return jsonify({'message': 'Validity check deleted successfully'}), 200
        else:
            return jsonify({'error': 'Validity check not found'}), 404
    except Exception as e:
        logging.error(f"Error deleting validity check: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chapters', methods=['POST'])
def create_chapter():
    try:
        data = request.get_json()
        chapter_id = db.create_chapter(data.get('title', 'Untitled'), data.get('content', ''), data.get('title', 'Untitled'))
        return jsonify({'message': 'Chapter created successfully', 'id': chapter_id}), 201
    except Exception as e:
        logging.error(f"Error creating chapter: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/characters', methods=['GET'])
def get_characters():
    try:
        characters = db.get_all_characters()
        return jsonify({'characters': characters}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/characters/<character_id>', methods=['DELETE'])
def delete_character(character_id):
    try:
        if db.delete_character(character_id):
            return jsonify({'message': 'Character deleted successfully'}), 200
        else:
            return jsonify({'error': 'Character not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/characters', methods=['POST'])
@jwt_required()
def create_character():
    data = request.json
    user_id = get_jwt_identity()
    character = Character.get_or_create(data['name'], data['description'], user_id)
    return jsonify(character.to_dict()), 201

if __name__ == '__main__':
    app.run(debug=True)
