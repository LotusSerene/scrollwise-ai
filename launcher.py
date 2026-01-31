import os
import subprocess
import signal
import sys
import threading
import time
import webbrowser
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

# Configuration
BACKEND_CMD = [sys.executable, "server.py"]
FRONTEND_CMD = ["npm", "start"]
DASHBOARD_URL = "http://localhost:3000"

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
    
    # Wait a moment for startup then open browser
    def open_browser_delayed():
        time.sleep(5)
        webbrowser.open(DASHBOARD_URL)
    
    threading.Thread(target=open_browser_delayed, daemon=True).start()

    # Create and run the tray icon
    image = create_icon()
    menu = (item('Open Dashboard', on_open_dashboard, default=True), item('Quit', on_quit))
    icon = pystray.Icon("ScrollWise", image, "ScrollWise AI", menu)
    
    icon.run()

if __name__ == "__main__":
    main()
