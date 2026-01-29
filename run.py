#!/usr/bin/env python3
"""
Cold Outreach Email Automation System - Launcher Script
Run this file to start the application.
"""

import os
import sys
from pathlib import Path

# Add the project directory to Python path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

# Check for .env file
env_file = project_dir / ".env"
env_example = project_dir / ".env.example"

if not env_file.exists() and env_example.exists():
    print("No .env file found. Creating from .env.example...")
    import shutil
    shutil.copy(env_example, env_file)
    print("Created .env file. Please edit it with your Gmail credentials.")
    print("")

# Import and run the app
if __name__ == "__main__":
    import uvicorn
    from backend.config import HOST, PORT
    
    print("Starting Cold Outreach Email Automation System...")
    print(f"Server running at: http://localhost:{PORT}")
    print(f"API docs at: http://localhost:{PORT}/docs")
    print("")
    print("Press Ctrl+C to stop the server.")
    print("")
    
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=True
    )
