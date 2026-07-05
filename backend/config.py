from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)

TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_SESSION = os.getenv("TELEGRAM_SESSION", "todoba")
TELEGRAM_SIGNAL_GROUP = os.getenv("TELEGRAM_SIGNAL_GROUP", "")
TELEGRAM_SIGNAL_GROUP_ID = int(
    os.getenv("TELEGRAM_SIGNAL_GROUP_ID", "0")
)

DEBUG = True