"""
Configuration module for Cold Outreach Email Automation System.
Loads settings from .env file.
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Gmail Configuration
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# SMTP Verifier Configuration
VERIFIER_DELAY_SECONDS = float(os.getenv("VERIFIER_DELAY_SECONDS", "1.5"))
VERIFIER_FROM_EMAIL = os.getenv("VERIFIER_FROM_EMAIL", "verify@example.com")

# Rate Limits
EMAILS_PER_MINUTE = int(os.getenv("EMAILS_PER_MINUTE", "5"))
DAILY_EMAIL_CAP = int(os.getenv("DAILY_EMAIL_CAP", "50"))

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# AI Configuration
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic")

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
