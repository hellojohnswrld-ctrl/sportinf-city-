import os
from dotenv import load_dotenv
load_dotenv()
APP_NAME=os.getenv("APP_NAME","AI Wager")
APP_VERSION=os.getenv("APP_VERSION","2.0.0")
API_FOOTBALL_KEY=os.getenv("API_FOOTBALL_KEY","")
THESPORTSDB_KEY=os.getenv("THESPORTSDB_KEY","123")
ODDS_API_KEY=os.getenv("ODDS_API_KEY","")
ODDS_API_REGION=os.getenv("ODDS_API_REGION","eu")
ODDS_API_SPORT=os.getenv("ODDS_API_SPORT","soccer_epl")
ODDS_API_ALL_SOCCER=os.getenv("ODDS_API_ALL_SOCCER","true").lower()=="true"
PAYDUNYA_MASTER_KEY=os.getenv("PAYDUNYA_MASTER_KEY","")
PAYDUNYA_PRIVATE_KEY=os.getenv("PAYDUNYA_PRIVATE_KEY","")
PAYDUNYA_TOKEN=os.getenv("PAYDUNYA_TOKEN","")
VIP_PRICE_XOF=int(os.getenv("VIP_PRICE_XOF","0") or "0")
VIP_MERCHANT_NAME=os.getenv("VIP_MERCHANT_NAME","JOHN FORCAST VIP")
PAYDUNYA_ENV=os.getenv("PAYDUNYA_ENV","production").lower()
PAYDUNYA_CALLBACK_URL=os.getenv("PAYDUNYA_CALLBACK_URL","").strip()
VIP_ACCESS_TTL=60*60*24*30