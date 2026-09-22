import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "AI Wager")
APP_VERSION = os.getenv("APP_VERSION", "2.0.0")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
THESPORTSDB_KEY = os.getenv("THESPORTSDB_KEY", "123")
