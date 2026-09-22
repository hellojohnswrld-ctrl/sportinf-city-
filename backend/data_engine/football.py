import httpx
from datetime import datetime, timezone
from backend.config import THESPORTSDB_KEY
BASE="https://www.thesportsdb.com/api/v1/json"
def _url(path):return f"{BASE}/{THESPORTSDB_KEY}/{path}"
async def api_get(path,params=None):
    async with httpx.AsyncClient(timeout=15) as c:
        r=await c.get(_url(path),params=params or {});r.raise_for_status();return r.json()
def today_utc():return datetime.now(timezone.utc).date().isoformat()
async def todays_fixtures():
    d=today_utc();data=await api_get("eventsday.php",{"d":d,"s":"Soccer"});return {"source":"TheSportsDB","date":d,"events":data.get("events") or []}
async def live_fixtures():
    d=today_utc();data=await api_get("eventsday.php",{"d":d,"s":"Soccer"});return {"source":"TheSportsDB","live_available":False,"message":"Free TheSportsDB V1 does not expose live scores; showing today's football events.","date":d,"events":data.get("events") or []}
async def fixture(fixture_id:int):
    data=await api_get("lookupevent.php",{"id":fixture_id});return {"source":"TheSportsDB","events":data.get("events") or []}
async def search_team(name):
    data=await api_get("searchteams.php",{"t":name});return data.get("teams") or []
async def team_last_results(team_id:int,last:int=10):
    data=await api_get("eventslast.php",{"id":team_id});return {"source":"TheSportsDB","events":(data.get("results") or [])[:last]}
async def team_upcoming(team_id:int):
    data=await api_get("eventsnext.php",{"id":team_id});return {"source":"TheSportsDB","events":data.get("events") or []}
