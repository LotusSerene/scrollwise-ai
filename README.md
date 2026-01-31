# ScrollWise AI (Local Desktop App)

ScrollWise is an intelligent co-pilot for crafting compelling narratives, worldbuilding, and managing creative projects. This version runs completely locally on your machine, ensuring data privacy and zero cloud dependencies.

## Features
- **Local-First**: All data (stories, worldbuilding, vectors) is stored locally.
- **Privacy Focused**: No data is sent to ScrollWise servers.
- **Full Pro Access**: All advanced features (Codex, Architect Mode, AI Integrations) are unlocked by default.
- **System Tray App**: Runs seamlessly in the background with a convenient tray icon.

## Prerequisites
- **Windows OS** (Recommended)
- **Python 3.10+** (Make sure to check "Add Python to PATH" during installation)
- **Node.js 18+**

## Installation

1.  Open the project folder.
2.  Double-click **`setup_app.ps1`**.
    *   This script will verify your environment, create a virtual environment, install all dependencies, and build the application for production.
    *   *Note: This may take a few minutes the first time.*

## Usage

1.  Double-click **`start_app.ps1`**.
2.  A blue "Scroll" icon will appear in your **System Tray** (near the clock).
3.  The application will automatically launch in your default browser at `http://localhost:3000`.
4.  **To Quit**: Right-click the System Tray icon and select **Quit**.

## Updates

To update the application, simply run **`setup_app.ps1`** again.
- It automatically checks for updates on GitHub.
- If updates are found, it pulls the latest code.
- It then re-installs dependencies and rebuilds the app to ensure everything is up to date.

---
*Created by [LotusSerene]*
