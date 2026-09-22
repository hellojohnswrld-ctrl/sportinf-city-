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

ESPN_BASE="https://site.api.espn.com/apis/site/v2/sports/soccer"

async def espn_fixtures(date=None):
    """
    Pull the ESPN soccer-wide scoreboard instead of querying only a small
    hard-coded set of leagues. ESPN exposes a public soccer/all scoreboard,
    which is much broader than the previous league list.
    """
    d=date or today_utc()
    compact=d.replace("-", "")
    try:
        async with httpx.AsyncClient(timeout=25) as c:
            r=await c.get(f"{ESPN_BASE}/all/scoreboard",params={"dates":compact})
            r.raise_for_status()
            data=r.json()
    except Exception:
        return {"source":"ESPN","date":d,"events":[]}

    out=[]
    for ev in data.get("events") or []:
        comp=(ev.get("competitions") or [{}])[0]
        teams=comp.get("competitors") or []
        home=next((x for x in teams if x.get("homeAway")=="home"),None)
        away=next((x for x in teams if x.get("homeAway")=="away"),None)
        if not home or not away:
            continue
        season=ev.get("season") or {}
        slug=season.get("slug") or ""
        league=((comp.get("league") or {}).get("name")
                or ((ev.get("league") or {}).get("name") if isinstance(ev.get("league"),dict) else None)
                or slug.replace("-", " ").title()
                or "Football")
        out.append({
            "idEvent":"espn-"+str(ev.get("id")),
            "idHomeTeam":"espn-team-"+str((home.get("team") or {}).get("id")),
            "idAwayTeam":"espn-team-"+str((away.get("team") or {}).get("id")),
            "strHomeTeam":(home.get("team") or {}).get("displayName"),
            "strAwayTeam":(away.get("team") or {}).get("displayName"),
            "dateEvent":d,
            "strTime":(ev.get("date") or "")[11:16],
            "strLeague":league,
            "strVenue":((comp.get("venue") or {}).get("fullName") or ""),
            "strStatus":((comp.get("status") or {}).get("type") or {}).get("description"),
            "strSport":"Soccer",
            "source":"ESPN",
            "source_team_ids":{
                "home":(home.get("team") or {}).get("id"),
                "away":(away.get("team") or {}).get("id")
            }
        })

    unique={}
    for e in out:
        k=(_key(e.get("strHomeTeam")),_key(e.get("strAwayTeam")),e.get("dateEvent"))
        if k[0] and k[1]:
            unique[k]=e
    return {"source":"ESPN","date":d,"events":list(unique.values())}

def _key(v):
    return "".join(ch.lower() for ch in (v or "") if ch.isalnum())
