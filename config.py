import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = "pg_management"
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-in-production")
SESSION_COOKIE = "pg_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days
