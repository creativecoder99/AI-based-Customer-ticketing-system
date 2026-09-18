import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
DATA_DIR = BASE_DIR / "data"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
JWT_SECRET = os.getenv("JWT_SECRET", "dev_secret_key_antigravity_fastapi_jwt_9837429187349182374")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "support_system.db"))
# Handle sqlite:/// prefix if passed
if DATABASE_PATH.startswith("sqlite:///"):
    DATABASE_PATH = DATABASE_PATH.replace("sqlite:///", "")

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))
