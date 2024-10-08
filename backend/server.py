# server.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import google.generativeai as genai
from context_manager import ContextManager
from chapter_generator import ChapterGenerator
import logging
from utils import save_state, load_state, ChapterGeneratorLoop
import tempfile
import json
import jwt
import datetime
import uuid  # Add this import
from database import db

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
        data = request.form
        num_chapters = int(data.get('numChapters', 1))
        plot = data.get('plot', '')
        writing_style = data.get('writingStyle', '')
        instructions = data.get('instructions', '')
        style_guide = data.get('styleGuide', '')
        api_key = data.get('apiKey', '')
        generation_model = data.get('generationModel', 'gemini-1.5-flash-002')
        check_model = data.get('checkModel', 'gemini-1.5-flash-002')
        min_word_count = int(data.get('minWordCount', 1000))
        characters = json.loads(data.get('characters', '{}'))
        chapter_title = data.get('chapterTitle', '')

        if not api_key:
            return jsonify({'error': 'API Key is required'}), 400

        # Fetch previous chapters from the database for the user
        previous_chapters = json.loads(data.get('previousChapters', '[]'))

        # Ensure previous_chapters is a list
        if not isinstance(previous_chapters, list):
            previous_chapters = []

        context_manager = ContextManager()
        looping_generator = ChapterGeneratorLoop(
            api_key=api_key,
            generation_model=generation_model,
            check_model=check_model
        )

        chapters = []
        validities = []

        for chapter_number in range(1, num_chapters + 1):
            chapter, chapter_title, validity = looping_generator.generate_chapter(
                chapter_number=chapter_number,
                plot=plot,
                writing_style=writing_style,
                instructions={"general": instructions, "style_guide": style_guide, 'min_word_count': min_word_count, 'chapter_number': chapter_number, 'chapter_title': chapter_title},
                characters=characters,
                previous_chapters=previous_chapters
            )
            chapters.append({'chapter': chapter, 'title': chapter_title})
            validities.append(validity)

            # Save the chapter to the database
            db.create_user_chapter(f'Chapter {chapter_number}', chapter, chapter_title)

            # Save validity to the database
            db.save_validity_check(f'Chapter {chapter_number}', validity)

        return jsonify({'chapters': chapters, 'validities': validities}), 200

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        logging.error(f"Request data: {request.form}")
        return jsonify({'error': 'An error occurred while generating chapters. Please try again later.'}), 500

@app.route('/api/chapters', methods=['GET'])
def get_chapters():
    try:
        # Fetch chapters from the database for the user
        chapters = db.get_all_chapters()  # Use a default user for now
        return jsonify({'chapters': chapters}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chapters/<chapter_id>', methods=['PUT'])
def update_chapter(chapter_id):
    try:
        data = request.json
        updated_chapter = db.update_chapter(chapter_id, data)
        if updated_chapter:
            return jsonify(updated_chapter), 200
        else:
            return jsonify({'error': 'Chapter not found'}), 404
    except Exception as e:
        logging.error(f"Error updating chapter: {str(e)}")
        logging.error(f"Request data: {data}")
        logging.error(f"Chapter ID: {chapter_id}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chapters', methods=['POST'])
def create_chapter():
    try:
        data = request.json
        chapter_id = uuid.uuid4().hex
        chapter_name = data.get('name', 'New Chapter')
        chapter_content = data.get('content', '')
        chapter_title = data.get('title', '')
        db.create_user_chapter(chapter_name, chapter_content, chapter_title)
        return jsonify({'id': chapter_id, 'name': chapter_name, 'content': chapter_content, 'title': chapter_title}), 201
    except Exception as e:
        logging.error(f"Error creating chapter: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chapters/<chapter_id>', methods=['DELETE'])
def delete_chapter(chapter_id):
    try:
        db.delete_chapter(chapter_id)
        return jsonify({'message': 'Chapter deleted successfully'}), 200
    except Exception as e:
        logging.error(f"Error deleting chapter: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/validity-checks', methods=['GET'])
def get_validity_checks():
    try:
        # Fetch validity checks from the database for the user
        validity_checks = db.get_all_validity_checks()
        return jsonify({'validityChecks': validity_checks}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/validity-checks/<check_id>', methods=['DELETE'])
def delete_validity_check(check_id):
    try:
        # Delete the validity check from the database
        db.delete_validity_check(check_id)
        return jsonify({'message': 'Validity check deleted successfully'}), 200
    except Exception as e:
        logging.error(f"Error deleting validity check: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
    port = int(os.environ.get('PORT', 5000))  # Default to 5000 if no PORT env is set
    app.run(host='0.0.0.0', port=port)  # This line will not be executed in production
