# Expect a few things to break here and there

# ScrollWise AI

ScrollWise AI is an open-source AI-powered writing assistant that helps authors create, manage, and analyze their stories. It provides comprehensive worldbuilding tools, character development features, and AI-assisted content generation.

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

### Cross-Platform

- Available for Windows only (Cross-platform coming soon)

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
- PostgreSQL (optional, SQLite supported by default)

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
   Create a `.env` file in both `backend` and `frontend` directories with necessary configurations.

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

- Flutter/Dart
- Provider for state management
- Material Design
- HTTP for API communication

### Backend

- FastAPI
- SQLAlchemy
- LangChain
- ChromaDB for vector storage
- Gemini AI API

## 🤝 Contributing

We welcome contributions! You can contribute to the project by creating a pull request.

### Development Setup

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

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

- [Official Website](https://scrollwise.netlify.app/)
- [Discord](https://discord.gg/R8PUtxFPUq)
- [Changelog](https://github.com/LotusSerene/scrollwise-ai/blob/master/changelog.md)

## 💝 Support the Project

ScrollWise AI is and will always be free and open source. If you'd like to support the project:

- ⭐ Star the repository
- 🐛 Report bugs and contribute fixes
- 📖 Improve documentation
- 🎨 Contribute new features

## 📊 Project Status

ScrollWise AI is under active development.
