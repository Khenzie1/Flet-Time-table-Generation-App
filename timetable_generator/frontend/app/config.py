"""Frontend configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# Server configuration
SERVER_URL = os.getenv("SERVER_URL", "https://flet-time-table-generation-app.onrender.com")
API_BASE_URL = f"{SERVER_URL}/api/v1"

# Database configuration
DB_PATH = DATA_DIR / "local_timetable.db"
DB_ECHO = os.getenv("DB_ECHO", "False").lower() == "true"

# Sync configuration
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS"))
SYNC_RETRY_INTERVALS = [2, 4, 8, 16, 32]  # Seconds between retries

# App configuration
APP_NAME = os.getenv("APP_NAME")
APP_VERSION = os.getenv("APP_VERSION")
COMPANY_NAME = os.getenv("COMPANY_NAME")

# UI configuration
THEME_COLOR = "#1976D2"
THEME_DARK_COLOR = "#004BA0"
THEME_LIGHT_COLOR = "#63A4FF"
ERROR_COLOR = "#B00020"
SUCCESS_COLOR = "#4CAF50"
WARNING_COLOR = "#FFC107"

# Periods configuration
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
MAX_PERIODS_PER_DAY = 8
BREAK_PERIODS = [4, 6]  # Period numbers that are breaks

# Export configuration
EXPORT_FORMATS = ["CSV", "Excel (XLSX)"]
