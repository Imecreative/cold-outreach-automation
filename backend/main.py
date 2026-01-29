"""
Cold Outreach Email Automation System - FastAPI Main Application
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

from .routes import files, leads, actions
from .config import HOST, PORT, DATA_DIR

# Create FastAPI app
app = FastAPI(
    title="Cold Outreach Email Automation",
    description="System for managing cold email outreach with SMTP verification, website scanning, AI drafts, and Gmail sending.",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(files.router)
app.include_router(leads.router)
app.include_router(actions.router)

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Get paths
BACKEND_DIR = Path(__file__).parent
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"

# Mount static files for frontend
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def serve_frontend():
    """Serve the frontend index.html"""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Cold Outreach API is running. Frontend not found."}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Cold Outreach API is running"}


# Run with: uvicorn backend.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
