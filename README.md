# ScrollWise AI

ScrollWise AI is an open-source AI-powered writing assistant that helps authors create, manage, and analyze their stories. It provides comprehensive worldbuilding tools, character development features, and AI-assisted content generation.

> **Note**: This project is under active development. Some features may be experimental or subject to change.

## 🌟 Features

### Story Management

- Create and organize multiple writing projects
- Chapter management and organization
- Import existing documents (PDF, DOCX)
- Real-time content editing and saving

### AI-Powered Tools

- Character development assistance
- Worldbuilding generation
- Plot consistency checking
- Relationship analysis between characters
- Knowledge base generation from your content

### Codex System

- Maintain a detailed story bible
- Track characters, locations, items, and lore
- Automatic codex entry generation from your writing
- Relationship mapping between story elements

### Cross-Platform Support

- Primary support for Windows
- Cross-platform compatibility for other operating systems in development

## Some Previews

<details>
  <summary>Project Management</summary>
  
  ![1](https://github.com/user-attachments/assets/0587edbb-2c0a-4ff7-9594-58329606422e)
</details>
<details>
  <summary>Codex Entries</summary>
  
  ![2](https://github.com/user-attachments/assets/a263fed7-80af-4ecb-9df4-3d8da0f37fa8)
</details>

<details>
  <summary>Codex Generation</summary>
  
![3](https://github.com/user-attachments/assets/a6e330d2-51d6-41bb-9aad-8f07622c92fc)
  
</details>

<details>
  <summary>Login</summary>
  
![4](https://github.com/user-attachments/assets/c48cfa05-23cd-47f1-8278-817d3649918c)
  
</details>

## 🚀 Getting Started

### Prerequisites

- Flutter SDK >=3.1.3
- Python 3.8+
- No external database required (uses local SQLite by default)
- No API keys required for basic functionality

### Installation

1. Clone the repository:

```bash
git clone https://github.com/LotusSerene/scrollwise-ai.git
cd scrollwise-ai
```

2. Install backend dependencies:

```bash
cd backend
pip install -r requirements.txt
```

3. Install frontend dependencies:

```bash
cd frontend
flutter pub get
```

4. Configure environment variables:
   
   Copy the example environment files and customize as needed:
   
   ```bash
   # Backend configuration
   cd backend
   copy .env.example .env
   
   # Frontend configuration
   cd ../frontend
   copy .env.example .env
   ```
   
   **Backend Environment (backend/.env)**:
   - `ALLOWED_ORIGINS`: CORS origins (automatically set by ServerManager)
   - `LOG_DIR`: Log directory path (automatically set by ServerManager)
   - `YOUR_SITE_URL`: Optional site URL for analytics
   - `YOUR_SITE_NAME`: Optional site name for analytics
   
   **Frontend Environment (frontend/.env)**:
   - `API_URL`: Backend server URL (default: http://localhost:8080)
   
   > **Note**: The application works entirely offline with local storage. No external API keys or cloud services are required for core functionality.

5. Run the application:

```bash
# Start backend server
cd backend
python server.py

# Start frontend (in a new terminal)
cd frontend
flutter run
```

## 🛠️ Technology Stack

### Frontend

- **Flutter/Dart** - Cross-platform UI framework
- **Provider** - State management solution
- **Material Design** - Modern UI components
- **HTTP** - API communication with backend
- **Path Provider** - File system access
- **Logging** - Application logging and debugging

### Backend

- **FastAPI** - Modern web framework for building APIs
- **SQLAlchemy** - Database ORM with async support
- **LangChain** - AI/LLM integration framework
- **Qdrant** - Local vector database for semantic search
- **Pydantic** - Data validation and serialization
- **SQLite** - Local database storage (no setup required)
- **Python-dotenv** - Environment variable management

## 🏗️ Architecture

### System Overview

ScrollWise AI follows a client-server architecture:

- **Flutter Frontend**: Cross-platform UI handling user interactions
- **FastAPI Backend**: RESTful API server managing business logic
- **Local SQLite**: Primary data storage for projects, chapters, and metadata
- **Local Qdrant**: Vector database for semantic search and AI-powered features
- **File System**: Local storage for logs, cache, and temporary files

### Data Flow

1. User interacts with Flutter UI components
2. UI triggers actions through Provider-based state management
3. HTTP requests sent to FastAPI backend
4. Backend processes requests using SQLAlchemy and LangChain
5. Results stored in local SQLite and Qdrant databases
6. Responses returned to frontend for UI updates

### Directory Structure

```
GeminiFrontend/
├── backend/
│   ├── .env.example          # Backend environment template
│   ├── requirements.txt      # Python dependencies
│   ├── server.py            # FastAPI application entry point
│   ├── database.py          # Database models and operations
│   ├── agent_manager.py     # AI agent management
│   ├── api_key_manager.py   # API key handling (if needed)
│   ├── vector_store.py      # Qdrant vector operations
│   └── models.py           # Pydantic data models
├── frontend/
│   ├── .env.example         # Frontend environment template
│   ├── lib/
│   │   ├── components/      # Feature-specific UI logic
│   │   ├── models/         # Data models
│   │   ├── providers/      # State management
│   │   ├── screens/        # Full-page views
│   │   ├── utils/          # Utilities and configuration
│   │   ├── widgets/        # Reusable UI components
│   │   └── main.dart       # Application entry point
│   └── pubspec.yaml        # Flutter dependencies
└── README.md               # This file
```

## 🤝 Contributing

We welcome contributions! You can contribute to the project by creating a pull request.

### Development Setup

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Guidelines

- Follow Flutter/Dart coding conventions
- Use Provider pattern for state management
- Implement proper error handling and logging
- Write clear commit messages
- Test on Windows platform primarily

## 📝 License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0) - see the [LICENSE](LICENSE) file for details.

This means:

- ✅ You can use the software freely
- ✅ You can modify the software
- ✅ You can distribute the software
- ✅ You can use it commercially
- ❗ You must disclose source code when you distribute or serve the software
- ❗ You must state changes you make to the code
- ❗ You must license derivative works under AGPL-3.0

## 🌐 Links

- [Official Website](https://scrllwise.com/)
- [Discord](https://discord.gg/R8PUtxFPUq)
- [Changelog](https://github.com/LotusSerene/scrollwise-ai/blob/master/changelog.md)

## 💝 Support the Project

ScrollWise AI is and will always be free and open source. If you'd like to support the project:

- ⭐ Star the repository
- 🐛 Report bugs and contribute fixes
- 📖 Improve documentation
- 🎨 Contribute new features

## 🔧 Troubleshooting

### Common Issues

**Backend won't start**:
- Ensure Python 3.8+ is installed
- Install dependencies: `pip install -r requirements.txt`
- Check that port 8080 is available

**Frontend can't connect to backend**:
- Verify backend is running on correct port
- Check `API_URL` in frontend/.env file
- Ensure CORS settings allow frontend origin

**Database errors**:
- Delete local database files to reset: `*.db`, `*.sqlite`
- Restart both backend and frontend

**Missing dependencies**:
- Run `flutter doctor` to check Flutter installation
- Run `pip list` to verify Python packages

### Logging

- Backend logs: `logs/server.log`
- Frontend logs: Available in console during development
- Vector store data: `qdrant_db/` directory

## 📊 Project Status

ScrollWise AI is under active development. Current focus areas:

- ✅ Core writing and project management features
- ✅ Local-first architecture with no external dependencies
- ✅ AI-powered content analysis and generation
- 🔄 Cross-platform compatibility improvements
- 🔄 Enhanced UI/UX polish
- 🔄 Advanced AI features and integrations
