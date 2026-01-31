Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  ScrollWise AI - Setup & Installer" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

# --- Git Auto-Update ---
Write-Host "[INFO] Checking for updates..." -ForegroundColor Yellow
if (-not (Test-Path ".git")) {
    Write-Host "[INFO] Repository not found. Cloning from GitHub..."
    git clone https://github.com/LotusSerene/scrollwise-ai .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Git clone failed. Please check your internet connection." -ForegroundColor Red
        Read-Host "Press Enter to exit..."
        exit 1
    }
} else {
    Write-Host "[INFO] Checking for latest changes..."
    git fetch origin master
    $localHash = git rev-parse HEAD
    $remoteHash = git rev-parse origin/master

    if ($localHash -ne $remoteHash) {
        Write-Host "[INFO] Update found! Pulling latest code..." -ForegroundColor Green
        git pull origin master
        if ($LASTEXITCODE -ne 0) {
           Write-Host "[WARNING] Git pull failed. Continuing with current version..." -ForegroundColor DarkYellow
        } else {
           Write-Host "[SUCCESS] Updated to latest version." -ForegroundColor Green
        }
    } else {
        Write-Host "[INFO] You are already on the latest version." -ForegroundColor Gray
    }
}

Write-Host ""

# --- Step 1: Python Check ---
Write-Host "[INFO] Step 1: Checking for Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Python command failed" }
    Write-Host "[OK] Python found: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found or failed to run." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ and add it to your PATH."
    Read-Host "Press Enter to exit..."
    exit 1
}

# --- Step 2: Node Check ---
Write-Host ""
Write-Host "[INFO] Step 2: Checking for Node.js..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Node command failed" }
    Write-Host "[OK] Node.js found: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Node.js not found." -ForegroundColor Red
    Write-Host "Please install Node.js 18+ and add it to your PATH."
    Read-Host "Press Enter to exit..."
    exit 1
}

Write-Host ""
Write-Host "[INFO] Prerequisites check passed." -ForegroundColor Green
Start-Sleep -Seconds 1

# --- Step 3: Backend Setup ---
Write-Host ""
Write-Host "[INFO] Step 3: Setting up Backend (Python)..." -ForegroundColor Yellow
Set-Location "backend" 

if (-not (Test-Path "venv")) {
    Write-Host "[INFO] Creating Python virtual environment..."
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create venv." -ForegroundColor Red
        Read-Host "Press Enter to exit..."
        exit 1
    }
}

# Install requirements
Write-Host "[INFO] Installing backend requirements..."
& ".\venv\Scripts\python.exe" -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] Pip install encountered errors." -ForegroundColor DarkYellow
}
Set-Location ".."

# --- Step 4: Frontend Setup & Build ---
Write-Host ""
Write-Host "[INFO] Step 4: Setting up Frontend (Node.js)..." -ForegroundColor Yellow
Set-Location "frontend"

if (-not (Test-Path "node_modules")) {
    Write-Host "[INFO] Installing frontend dependencies..."
    cmd /c "npm install"
}

Write-Host "[INFO] Building Frontend for Production..."
cmd /c "npm run build"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Frontend build failed." -ForegroundColor Red
    Read-Host "Press Enter to exit..."
    exit 1
}

Set-Location ".."

Write-Host ""
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "[SUCCESS] Setup Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "You can now run the application using 'start_app.ps1'."
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to close..."
