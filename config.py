"""Settings, read from environment variables (see .env.example)."""
import os
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "prepledger.db"

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_EXPIRE_DAYS = int(os.getenv("JWT_EXPIRE_DAYS", "14"))
# "Today" is computed in the user's timezone. Default: India (UTC+5:30).
TZ_OFFSET_MINUTES = int(os.getenv("TZ_OFFSET_MINUTES", "330"))
ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "true").lower() == "true"
