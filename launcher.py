import os
import subprocess
import signal
import sys
import threading
import time
import webbrowser
import requests
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

# Configuration
BACKEND_CMD = [sys.executable, "server.py"]
FRONTEND_CMD = ["npm", "start"]
DASHBOARD_URL = "http://localhost:3000"
BACKEND_HEALTH_CHECK_URL = "http://localhost:8000/health"  # Adjust if backend uses different health endpoint
BACKEND_API_URL = "http://localhost:8000"  # Fallback: just check if backend is responding

# Global process handles
backend_process = None
frontend_process = None

def create_icon():
    # Generate a simple icon completely with code to avoid file dependency issues
    width = 64
    height = 64
    color1 = (63, 81, 181) # Indigo
    color2 = (255, 255, 255) # White

    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    
    # Draw a stylized 'S' or scroll shape
    dc.rectangle((16, 16, 48, 48), fill=color2)
    dc.rectangle((20, 20, 44, 44), fill=color1)
    
    return image

def start_services():
    global backend_process, frontend_process
    
    # Start Backend
    print("Starting Backend...")
    backend_env = os.environ.copy()
    backend_cwd = os.path.join(os.getcwd(), "backend")
    
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW

    # Open log file
    try:
        backend_log = open("backend.log", "w")
    except Exception as e:
        print(f"Failed to open backend log: {e}")
        backend_log = subprocess.DEVNULL

    backend_process = subprocess.Popen(
        BACKEND_CMD, 
        cwd=backend_cwd,
        env=backend_env,
        creationflags=creation_flags,
        stdout=backend_log,
        stderr=backend_log
    )

    # Start Frontend
    print("Starting Frontend...")
    frontend_cwd = os.path.join(os.getcwd(), "frontend")
    
    try:
        frontend_log = open("frontend.log", "w")
    except Exception as e:
        print(f"Failed to open frontend log: {e}")
        frontend_log = subprocess.DEVNULL

    frontend_process = subprocess.Popen(
        "npm start", 
        shell=True,
        cwd=frontend_cwd,
        creationflags=creation_flags,
        stdout=frontend_log,
        stderr=frontend_log
    )

def is_backend_ready():
    """
    Check if the backend is ready to accept requests.
    Tries health endpoint first, then falls back to general API check.
    """
    try:
        # Try health check endpoint first
        response = requests.get(BACKEND_HEALTH_CHECK_URL, timeout=2)
        if response.status_code == 200:
            return True
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        pass
    
    try:
        # Fallback: try to reach any backend endpoint
        response = requests.get(BACKEND_API_URL, timeout=2)
        if response.status_code in [200, 404, 401]:  # Any response means backend is up
            return True
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        pass
    
    return False

def is_frontend_ready():
    """
    Check if the frontend is ready by trying to access the dashboard URL.
    """
    try:
        response = requests.get(DASHBOARD_URL, timeout=2)
        if response.status_code in [200, 404]:  # Frontend responds (even 404 means it's running)
            return True
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        pass
    
    return False

def wait_for_services(max_wait_seconds=120):
    """
    Wait for both backend and frontend to be ready before opening the browser.
    Uses exponential backoff to avoid hammering the services.
    
    Args:
        max_wait_seconds: Maximum time to wait before giving up (default 120 seconds / 2 minutes)
    """
    print("Waiting for services to be ready...")
    start_time = time.time()
    wait_time = 1  # Start with 1 second between checks
    max_wait_time = 5  # Cap the wait time at 5 seconds between checks
    
    backend_ready = False
    frontend_ready = False
    
    while time.time() - start_time < max_wait_seconds:
        # Check backend
        if not backend_ready:
            if is_backend_ready():
                print("✓ Backend is ready!")
                backend_ready = True
            else:
                print("⏳ Waiting for backend to start...")
        
        # Check frontend
        if not frontend_ready:
            if is_frontend_ready():
                print("✓ Frontend is ready!")
                frontend_ready = True
            else:
                print("⏳ Waiting for frontend to start...")
        
        # If both are ready, we're good to go
        if backend_ready and frontend_ready:
            print("\n✓ Both services are ready! Opening dashboard...")
            return True
        
        # Wait before next check (exponential backoff)
        time.sleep(wait_time)
        wait_time = min(wait_time * 1.5, max_wait_time)  # Increase wait time but cap it
    
    # Timeout reached
    elapsed = int(time.time() - start_time)
    print(f"\n⚠ Timeout after {elapsed} seconds. Backend ready: {backend_ready}, Frontend ready: {frontend_ready}")
    print("Proceeding anyway (services may still be initializing)...\n")
    return False

def stop_services():
    global backend_process, frontend_process
    print("Stopping services...")
    
    if backend_process:
        if sys.platform == "win32":
            subprocess.call(['taskkill', '/F', '/T', '/PID', str(backend_process.pid)])
        else:
            backend_process.terminate()
            
    if frontend_process:
        # npm start spawns node, so we need to kill the tree
        if sys.platform == "win32":
            subprocess.call(['taskkill', '/F', '/T', '/PID', str(frontend_process.pid)])
        else:
            frontend_process.terminate()

def on_open_dashboard(icon, item):
    webbrowser.open(DASHBOARD_URL)

def on_quit(icon, item):
    icon.stop()
    stop_services()
    sys.exit(0)

def main():
    # Start processes in a separate thread or just before the icon loop
    start_services()
    
    # Wait for services and then open browser
    def open_browser_when_ready():
        wait_for_services(max_wait_seconds=120)
        webbrowser.open(DASHBOARD_URL)
    
    threading.Thread(target=open_browser_when_ready, daemon=True).start()

    # Create and run the tray icon
    image = create_icon()
    menu = (item('Open Dashboard', on_open_dashboard, default=True), item('Quit', on_quit))
    icon = pystray.Icon("ScrollWise", image, "ScrollWise AI", menu)
    
    icon.run()

if __name__ == "__main__":
    main()
