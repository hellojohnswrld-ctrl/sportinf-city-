import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "AI Wager")
APP_VERSION = os.getenv("APP_VERSION", "2.0.0")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
THESPORTSDB_KEY = os.getenv("THESPORTSDB_KEY", "123")
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_API_REGION = os.getenv("ODDS_API_REGION", "eu")
ODDS_API_SPORT = os.getenv("ODDS_API_SPORT", "soccer_epl")
