from flask import Flask, request, jsonify, Blueprint
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
import os
from dotenv import load_dotenv
import logging
import jwt
import datetime
import uuid
from database import db_instance, get_chapter_count, Character
from werkzeug.utils import secure_filename
import tempfile
import pypdf
import docx2txt
from vector_store import VectorStore
from agent_manager import AgentManager

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

# Function to get the current user's ID from the JWT token
def get_current_user_id():
    return get_jwt_identity()


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
        user_id = get_jwt_identity()

        num_chapters = int(data.get('numChapters', 1))
        plot = data.get('plot', '')
        writing_style = data.get('writingStyle', '')
        instructions = data.get('instructions', {})
        style_guide = instructions.get('styleGuide', '')
        min_word_count = int(instructions.get('minWordCount', 1000))
        previous_chapters = db_instance.get_all_chapters(user_id)

        try:
            agent_manager = AgentManager(user_id)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

        generated_chapters = []
        validities = []

        current_chapter_count = get_chapter_count(user_id)

        for i in range(num_chapters):
            chapter_number = current_chapter_count + i + 1
            characters = db_instance.get_all_characters(user_id)

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
            except Exception as e:
                logging.error(f"Error generating chapter {chapter_number}: {str(e)}")
                raise

            if new_characters:
                for name, description in new_characters.items():
                    db_instance.create_character(name, description, user_id)

            chapter_id = db_instance.create_chapter(chapter_title, chapter_content, user_id)


            validity = agent_manager.check_chapter(chapter_content, instructions, previous_chapters)

            db_instance.save_validity_check(chapter_id, chapter_title, validity, user_id)

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
        user_id = get_jwt_identity()
        chapters = db_instance.get_all_chapters(user_id)
        return jsonify({'chapters': chapters}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chapters/<chapter_id>', methods=['PUT'])
@jwt_required()
def update_chapter(chapter_id):
    try:
        data = request.json
        user_id = get_jwt_identity()
        updated_chapter = db_instance.update_chapter(chapter_id, data.get('title'), data.get('content'), user_id)


        return jsonify(updated_chapter), 200
    except Exception as e:
        logging.error(f"Error updating chapter: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chapters/<chapter_id>', methods=['DELETE'])
@jwt_required()
def delete_chapter(chapter_id):
    app.logger.debug('Delete chapter function called for chapter_id: %s', chapter_id)
    try:
        user_id = get_jwt_identity()
        if db_instance.delete_chapter(chapter_id, user_id):
            return jsonify({'message': 'Chapter deleted successfully'}), 200
        else:
            return jsonify({'error': 'Chapter not found'}), 404
    except Exception as e:
        logging.error(f"Error deleting chapter: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/validity-checks', methods=['GET'])
@jwt_required()
def get_validity_checks():
    try:
        user_id = get_jwt_identity()
        validity_checks = db_instance.get_all_validity_checks(user_id)
        return jsonify({'validityChecks': validity_checks}), 200
    except Exception as e:
        logging.error(f"An error occurred in get_validity_checks: {str(e)}", exc_info=True)
        return jsonify({'error': 'An internal server error occurred'}), 500

@app.route('/api/validity-checks/<check_id>', methods=['DELETE'])
@jwt_required()
def delete_validity_check(check_id):
    try:
        user_id = get_jwt_identity()
        if db_instance.delete_validity_check(check_id, user_id):
            return jsonify({'message': 'Validity check deleted successfully'}), 200
        else:
            return jsonify({'error': 'Validity check not found'}), 404
    except Exception as e:
        logging.error(f"Error deleting validity check: {str(e)}")
        return jsonify({'error': f'An error occurred while deleting the validity check: {str(e)}'}), 500

@app.route('/api/chapters', methods=['POST'])
@jwt_required()
def create_chapter():
    try:
        data = request.get_json()
        user_id = get_jwt_identity()
        chapter = db_instance.create_chapter(data.get('title', 'Untitled'), data.get('content', ''), user_id)

        agent_manager = AgentManager(user_id)
        agent_manager.add_chapter_to_knowledge_base(chapter)

        return jsonify({'message': 'Chapter created successfully', 'id': chapter['id']}), 201
    except Exception as e:
        logging.error(f"Error creating chapter: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/characters', methods=['GET'])
@jwt_required()
def get_characters():
    try:
        user_id = get_jwt_identity()
        characters = db_instance.get_all_characters(user_id)
        return jsonify({'characters': characters}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/characters/<character_id>', methods=['DELETE'])
@jwt_required()
def delete_character(character_id):
    try:
        user_id = get_jwt_identity()
        character = db_instance.get_character_by_id(character_id, user_id)
        if character:
            db_instance.delete_character(character_id, user_id)

            return jsonify({'message': 'Character deleted successfully'}), 200
        else:
            return jsonify({'error': 'Character not found'}), 404
    except Exception as e:
        logging.error(f"Error deleting character: {str(e)}", exc_info=True)
        return jsonify({'error': f'An error occurred while deleting the character: {str(e)}'}), 500

@app.route('/api/characters', methods=['POST'])
@jwt_required()
def create_character():
    try:
        data = request.json
        user_id = get_jwt_identity()
        character = db_instance.create_character(data['name'], data['description'], user_id)

        agent_manager = AgentManager(user_id)
        character_info = {"id": character['id'], "name": character['name'], "description": character['description']}
        # Log the adding of the character to the knowledge base
        logging.info(f"Character {character['name']} added to the knowledge base")

        return jsonify(character), 201
    except Exception as e:
        logging.error(f"Error creating character: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/characters/<character_id>', methods=['PUT'])
@jwt_required()
def update_character(character_id):
    try:
        data = request.json
        user_id = get_jwt_identity()
        updated_character = db_instance.update_character(character_id, data['name'], data['description'], user_id)

        character_info = {"id": updated_character['id'], "name": updated_character['name'], "description": updated_character['description']}

        return jsonify(updated_character), 200
    except Exception as e:
        logging.error(f"Error updating character: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge-base', methods=['POST'])
@jwt_required()
def add_to_knowledge_base():
    try:
        data = request.json
        documents = data.get('documents', [])
        if not documents:
            return jsonify({'error': 'Documents are required'}), 400

        user_id = get_jwt_identity()
        api_key = db_instance.get_api_key(user_id)
        model_settings = db_instance.get_model_settings(user_id)
        vector_store = VectorStore(user_id, api_key, model_settings['embeddingsModel'])

        for doc in documents:
            vector_store.add_to_knowledge_base(doc)

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
@jwt_required()
def upload_document():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        if file:
            filename = secure_filename(file.filename)
            temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(temp_dir, filename)
            file.save(file_path)

            extracted_text = extract_text_from_document(file_path)

            user_id = get_jwt_identity()
            agent_manager = AgentManager(user_id)
            agent_manager.add_to_knowledge_base([extracted_text], metadata={"type": "doc"})

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

@app.route('/api/model-settings', methods=['GET'])
@jwt_required()
def get_model_settings():
    try:
        user_id = get_jwt_identity()
        settings = db_instance.get_model_settings(user_id)
        return jsonify(settings), 200
    except Exception as e:
        logging.error(f"An error occurred in get_model_settings: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/model-settings', methods=['POST'])
@jwt_required()
def save_model_settings():
    try:
        user_id = get_jwt_identity()
        settings = request.json
        db_instance.save_model_settings(user_id, settings)
        return jsonify({'message': 'Model settings saved successfully'}), 200
    except Exception as e:
        logging.error(f"An error occurred in save_model_settings: {str(e)}", exc_info=True)
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
        chat_history = data.get('chatHistory', [])

        if not query:
            return jsonify({'error': 'Query is required'}), 400

        user_id = get_jwt_identity()
        agent_manager = AgentManager(user_id)
        result = agent_manager.generate_with_retrieval(query, chat_history)

        return jsonify({'result': result}), 200
    except Exception as e:
        logging.error(f"An error occurred in query_knowledge_base: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge-base', methods=['GET', 'POST', 'PUT', 'DELETE'])
@jwt_required()
def manage_knowledge_base():
    try:
        user_id = get_jwt_identity()
        agent_manager = AgentManager(user_id)

        if request.method == 'GET':
            content = agent_manager.get_knowledge_base_content()
            formatted_content = [
                {
                    'type': item['metadata'].get('type', 'Unknown'),
                    'content': item['page_content'],
                    'embedding_id': item['id']
                }
                for item in content
            ]
            return jsonify({'content': formatted_content}), 200

        elif request.method == 'POST':
            data = request.json
            item_type = data.get('type')
            content = data.get('content')
            metadata = data.get('metadata', {})
            
            if not item_type or not content:
                return jsonify({'error': 'Type and content are required'}), 400

            embedding_id = agent_manager.add_to_knowledge_base(item_type, content, metadata)
            return jsonify({'message': 'Item added to knowledge base successfully', 'embedding_id': embedding_id}), 201

        elif request.method in ['PUT', 'DELETE']:
            embedding_id = request.json.get('embedding_id')
            if not embedding_id:
                return jsonify({'error': 'Embedding ID is required'}), 400

            if request.method == 'PUT':
                new_content = request.json.get('content')
                new_metadata = request.json.get('metadata')
                agent_manager.update_or_remove_from_knowledge_base(embedding_id, 'update', new_content, new_metadata)
                return jsonify({'message': 'Item updated in knowledge base successfully'}), 200
            else:  # DELETE
                agent_manager.update_or_remove_from_knowledge_base(embedding_id, 'delete')
                return jsonify({'message': 'Item deleted from knowledge base successfully'}), 200

    except Exception as e:
        logging.error(f"An error occurred in manage_knowledge_base: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/reset-chat-history', methods=['POST'])
@jwt_required()
def reset_chat_history():
    try:
        user_id = get_jwt_identity()
        agent_manager = AgentManager(user_id)
        agent_manager.reset_memory()
        return jsonify({'message': 'Chat history reset successfully'}), 200
    except Exception as e:
        logging.error(f"An error occurred in reset_chat_history: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)