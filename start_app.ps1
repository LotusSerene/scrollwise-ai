Write-Host "Starting ScrollWise AI..." -ForegroundColor Cyan

# Define paths
$pythonPath = "backend\venv\Scripts\pythonw.exe"
$launcherScript = "launcher.py"

if (-not (Test-Path $pythonPath)) {
    Write-Host "[ERROR] Python venv not found. Please run setup_app.ps1 first." -ForegroundColor Red
    Read-Host "Press Enter to exit..."
    exit 1
}

# Install pystray if missing (quick check)
# Ideally setup_app does this, but for robustness:
if (-not (Test-Path "backend\venv\Lib\site-packages\pystray")) {
    Write-Host "[INFO] Installing tray icon dependencies..."
    & "backend\venv\Scripts\python.exe" -m pip install pystray Pillow
}

Write-Host "[INFO] Launching System Tray Application..."
Start-Process -FilePath $pythonPath -ArgumentList $launcherScript -WindowStyle Hidden

Write-Host ""
Write-Host "ScrollWise is running in your System Tray (look for the blue icon)." -ForegroundColor Green
Write-Host "Right-click the icon to Quit."
Start-Sleep -Seconds 3
