# backend/server.py
from flask import Flask, request, jsonify, Blueprint
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
import os
from dotenv import load_dotenv
import logging
import jwt
import datetime
import uuid
from database import db_instance, get_chapter_count, Character
from agent_manager import AgentManager
from werkzeug.utils import secure_filename
import tempfile
import pypdf
import docx2txt

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

# Load environment variables from .env file
load_dotenv()

# Secret key for JWT (replace with a strong secret in production)
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "your-secret-key")
API_KEY = os.environ.get("API_KEY")  # Get API key from environment

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# JWT Configuration
app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY
app.config['JWT_TOKEN_LOCATION'] = ['headers']
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(hours=1)
jwt = JWTManager(app)

# Initialize Database
# db = db(app, None)  # Pass None for agent_manager for now

# Create a test user if they don't already exist
if not db_instance.get_user_by_email("test@example.com"):
    db_instance.create_user("test@example.com", "password")

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"message": "Email and password are required"}), 400

        # Check if user already exists
        if db_instance.get_user_by_email(email):
            return jsonify({"message": "User already exists"}), 400

        # Create new user
        db_instance.create_user(email, password)
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

        user = db_instance.get_user_by_email(email)
        if user and user['password'] == password:
            access_token = create_access_token(identity=user['id'])
            return jsonify(access_token=access_token), 200
        else:
            return jsonify({"message": "Invalid email or password"}), 401

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate', methods=['POST'])
@jwt_required()
def generate_chapters():
    try:
        data = request.json
        #logging.debug(f"Received data: {data}")
        
        num_chapters = int(data.get('numChapters', 1))
        plot = data.get('plot', '')
        writing_style = data.get('writingStyle', '')
        instructions = data.get('instructions', {})
        style_guide = instructions.get('styleGuide', '')
        generation_model = data.get('generationModel', 'gemini-1.5-pro-002')
        check_model = data.get('checkModel', 'gemini-1.5-pro-002')
        min_word_count = int(instructions.get('minWordCount', 1000))
        previous_chapters = chapters = db_instance.get_all_chapters()
        #logging.debug(f"Received previousChapters: {previous_chapters}")
        
        user_id = get_jwt_identity()  # Get user ID from JWT token
        
        try:
            agent_manager = AgentManager(user_id, generation_model, check_model)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400  # Return 400 Bad Request if API key is not set
       # logging.debug("AgentManager initialized")

        generated_chapters = []
        validities = []

        # Get the current chapter count from the database
        current_chapter_count = get_chapter_count()

        for i in range(num_chapters):
            chapter_number = current_chapter_count + i + 1
            #logging.debug(f"Generating chapter {chapter_number}")
            # Log the characters being sent to the agent
            #logging.debug(f"Sending characters to agent: {db.get_all_characters()}")

            characters = db_instance.get_all_characters()
           # logging.debug(f"Retrieved {len(characters)} characters")

            try:
                chapter_content, chapter_title, new_characters = agent_manager.generate_chapter(
                    chapter_number=chapter_number,
                    plot=plot,
                    writing_style=writing_style,
                    instructions={
                        "general": instructions,
                        "style_guide": style_guide,
                        'min_word_count': min_word_count,
                        'chapter_number': chapter_number
                    },
                    previous_chapters=previous_chapters, 
                    characters=characters
                )
                logging.debug(f"Chapter {chapter_number} generated successfully")
            except Exception as e:
                logging.error(f"Error generating chapter {chapter_number}: {str(e)}")
                raise

            # Check for new characters
            if new_characters:
                for name, description in new_characters.items():
                    db_instance.create_character(name, description)
                
            # Save the chapter to the database
            chapter_id = db_instance.create_chapter(chapter_title, chapter_content)
                
            # Get validity from the agent's check_chapter method
            validity = agent_manager.check_chapter(chapter_content, instructions, previous_chapters)
                
            # Save validity to the database
            db_instance.save_validity_check(chapter_id, chapter_title, validity)
                
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
@jwt_required()
def get_chapters():
    try:
        chapters = db_instance.get_all_chapters()
        logging.debug(f"Retrieved {len(chapters)} chapters")
        return jsonify({'chapters': chapters}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chapters/<chapter_id>', methods=['PUT'])
def update_chapter(chapter_id):
    try:
        data = request.json
        updated_chapter = db_instance.update_chapter(chapter_id, data.get('title'), data.get('content'))
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
        if db_instance.delete_chapter(chapter_id):
            return jsonify({'message': 'Chapter deleted successfully'}), 200
        else:
            return jsonify({'error': 'Chapter not found'}), 404
    except Exception as e:
        logging.error(f"Error deleting chapter: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/validity-checks', methods=['GET'])
def get_validity_checks():
    try:
        validity_checks = db_instance.get_all_validity_checks()
        return jsonify({'validityChecks': validity_checks}), 200
    except Exception as e:
        logging.error(f"An error occurred in get_validity_checks: {str(e)}", exc_info=True)
        return jsonify({'error': 'An internal server error occurred'}), 500

@app.route('/api/validity-checks/<check_id>', methods=['DELETE'])
def delete_validity_check(check_id):
    try:
        if db_instance.delete_validity_check(check_id):
            return jsonify({'message': 'Validity check deleted successfully'}), 200
        else:
            return jsonify({'error': 'Validity check not found'}), 404
    except Exception as e:
        logging.error(f"Error deleting validity check: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chapters', methods=['POST'])
@jwt_required()
def create_chapter():
    try:
        data = request.get_json()
        chapter = db_instance.create_chapter(data.get('title', 'Untitled'), data.get('content', ''))
        
        user_id = get_jwt_identity()
        agent_manager = AgentManager(user_id, 'gemini-1.5-pro-002', 'gemini-1.5-pro-002')
        agent_manager.add_chapter_to_knowledge_base(chapter)
        
        return jsonify({'message': 'Chapter created successfully', 'id': chapter['id']}), 201
    except Exception as e:
        logging.error(f"Error creating chapter: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/characters', methods=['GET'])
def get_characters():
    try:
        characters = db_instance.get_all_characters()
        return jsonify({'characters': characters}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/characters/<character_id>', methods=['DELETE'])
@jwt_required()
def delete_character(character_id):
    try:
        character = db_instance.get_character_by_id(character_id)
        if character:
            db_instance.delete_character(character_id)
            
            user_id = get_jwt_identity()
            agent_manager = AgentManager(user_id, 'gemini-1.5-pro-002', 'gemini-1.5-pro-002')
            agent_manager.remove_character_from_knowledge_base(character)
            
            return jsonify({'message': 'Character deleted successfully'}), 200
        else:
            return jsonify({'error': 'Character not found'}), 404
    except Exception as e:
        logging.error(f"Error deleting character: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/characters', methods=['POST'])
@jwt_required()
def create_character():
    try:
        data = request.json
        character = db_instance.create_character(data['name'], data['description'])
        
        user_id = get_jwt_identity()
        agent_manager = AgentManager(user_id, 'gemini-1.5-pro-002', 'gemini-1.5-pro-002')
        agent_manager.add_character_to_knowledge_base(character)
        
        return jsonify(character), 201
    except Exception as e:
        logging.error(f"Error creating character: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge-base', methods=['POST'])
def add_to_knowledge_base():
    try:
        data = request.json
        documents = data.get('documents', [])
        if not documents:
            return jsonify({'error': 'Documents are required'}), 400

        user_id = get_jwt_identity()  # Get user ID from JWT token
        agent_manager = AgentManager(user_id, 'gemini-1.5-flash-002', 'gemini-1.5-flash-002')  # Pass user ID to AgentManager
        agent_manager.add_to_knowledge_base(documents)

        return jsonify({'message': 'Documents added to the knowledge base successfully'}), 200
    except Exception as e:
        logging.error(f"An error occurred in add_to_knowledge_base: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/save-api-key', methods=['POST'])
@jwt_required()
def save_api_key():
    try:
        data = request.get_json()
        api_key = data.get('apiKey')
        if not api_key:
            return jsonify({'error': 'API key is required'}), 400

        user_id = get_jwt_identity()
        db_instance.save_api_key(user_id, api_key)

        return jsonify({'message': 'API key saved successfully'}), 200
    except Exception as e:
        logging.error(f"An error occurred in save_api_key: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload-document', methods=['POST'])
def upload_document():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        if file:
            filename = secure_filename(file.filename)
            # Save the file temporarily
            temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(temp_dir, filename)
            file.save(file_path)

            # Process the document (extract text, etc.)
            extracted_text = extract_text_from_document(file_path)

            # Add the processed document to the knowledge base
            user_id = get_jwt_identity()
            agent_manager = AgentManager(user_id, 'gemini-1.5-pro-002', 'gemini-1.5-pro-002')
            agent_manager.add_to_knowledge_base([extracted_text])

            # Remove the temporary file
            os.remove(file_path)
            os.rmdir(temp_dir)

            return jsonify({'message': 'Document uploaded and added to knowledge base successfully'}), 200

    except Exception as e:
        logging.error(f"An error occurred in upload_document: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

def extract_text_from_document(file_path):
    if file_path.endswith('.pdf'):
        with open(file_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            num_pages = len(reader.pages)
            text = ""
            for i in range(num_pages):
                page = reader.pages[i]
                text += page.extract_text()
            return text
    elif file_path.endswith('.docx'):
        return docx2txt.process(file_path)
    else:
        return "Unsupported file type"

@app.route('/api/check-api-key', methods=['GET'])
@jwt_required()
def check_api_key():
    try:
        user_id = get_jwt_identity()
        api_key = db_instance.get_api_key(user_id)
        is_set = bool(api_key)
        masked_key = '*' * (len(api_key) - 4) + api_key[-4:] if is_set else None
        return jsonify({'isSet': is_set, 'apiKey': masked_key}), 200
    except Exception as e:
        logging.error(f"An error occurred in check_api_key: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/remove-api-key', methods=['DELETE'])
@jwt_required()
def remove_api_key():
    try:
        user_id = get_jwt_identity()
        db_instance.remove_api_key(user_id)
        return jsonify({'message': 'API key removed successfully'}), 200
    except Exception as e:
        logging.error(f"An error occurred in remove_api_key: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/query-knowledge-base', methods=['POST'])
@jwt_required()
def query_knowledge_base():
    try:
        data = request.json
        query = data.get('query')
        model = data.get('model', 'gemini-1.5-pro-002')
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400

        user_id = get_jwt_identity()
        agent_manager = AgentManager(user_id, model, model)
        result = agent_manager.generate_with_retrieval(query)

        return jsonify({'result': result}), 200
    except Exception as e:
        logging.error(f"An error occurred in query_knowledge_base: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge-base', methods=['GET'])
@jwt_required()
def get_knowledge_base_content():
    try:
        user_id = get_jwt_identity()
        agent_manager = AgentManager(user_id, 'gemini-1.5-pro-002', 'gemini-1.5-pro-002')
        content = agent_manager.get_knowledge_base_content()
        return jsonify({'content': content}), 200
    except Exception as e:
        logging.error(f"An error occurred in get_knowledge_base_content: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)