import httpx
import asyncio
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

ESPN_LEAGUES = [
    "eng.1","esp.1","ita.1","ger.1","fra.1","ned.1","por.1","bel.1","tur.1","sco.1",
    "usa.1","mex.1","bra.1","arg.1","col.1","chi.1","jpn.1","kor.1","aus.1",
    "uefa.champions","uefa.europa","uefa.europa.conf","eng.league_cup","eng.2",
    "esp.2","ita.2","ger.2","fra.2"
]
ESPN_BASE="https://site.api.espn.com/apis/site/v2/sports/soccer"

async def espn_fixtures(date=None):
    d=date or today_utc()
    async def one(league):
        try:
            async with httpx.AsyncClient(timeout=12) as c:
                r=await c.get(f"{ESPN_BASE}/{league}/scoreboard",params={"dates":d})
                r.raise_for_status()
                data=r.json()
                out=[]
                for ev in data.get("events") or []:
                    comp=(ev.get("competitions") or [{}])[0]
                    teams=comp.get("competitors") or []
                    home=next((x for x in teams if x.get("homeAway")=="home"),None)
                    away=next((x for x in teams if x.get("homeAway")=="away"),None)
                    if not home or not away: continue
                    out.append({
                        "idEvent":"espn-"+str(ev.get("id")),
                        "strHomeTeam":(home.get("team") or {}).get("displayName"),
                        "strAwayTeam":(away.get("team") or {}).get("displayName"),
                        "dateEvent":d,
                        "strTime":(ev.get("date") or "")[11:16],
                        "strLeague":((comp.get("league") or {}).get("name") or league),
                        "strVenue":((comp.get("venue") or {}).get("fullName") or ""),
                        "strStatus":((comp.get("status") or {}).get("type") or {}).get("description"),
                        "strSport":"Soccer",
                        "source":"ESPN"
                    })
                return out
        except Exception:
            return []
    results=await asyncio.gather(*(one(x) for x in ESPN_LEAGUES))
    unique={}
    for group in results:
        for e in group:
            k=(str(e.get("strHomeTeam","")).lower(),str(e.get("strAwayTeam","")).lower(),e.get("dateEvent"))
            unique[k]=e
    return {"source":"ESPN","date":d,"events":list(unique.values())}
