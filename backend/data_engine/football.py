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
    """Return currently live soccer matches from the broad ESPN scoreboard."""
    d=today_utc()
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r=await c.get(f"{ESPN_BASE}/all/scoreboard",params={"dates":d})
            r.raise_for_status()
            data=r.json()
    except Exception:
        return {"source":"ESPN","live_available":False,"date":d,"events":[]}
    out=[]
    for ev in data.get("events") or []:
        comp=(ev.get("competitions") or [{}])[0]
        status=((comp.get("status") or {}).get("type") or {})
        if status.get("completed") is True:
            continue
        state=(status.get("state") or "").lower()
        # ESPN uses in/post/pre states. Only expose genuinely in-progress events.
        if state not in ("in","live"):
            continue
        teams=comp.get("competitors") or []
        home=next((x for x in teams if x.get("homeAway")=="home"),None)
        away=next((x for x in teams if x.get("homeAway")=="away"),None)
        if not home or not away:
            continue
        ht=home.get("team") or {}; at=away.get("team") or {}
        out.append({
            "event_id":"espn-"+str(ev.get("id")),
            "home_team":ht.get("displayName") or "",
            "away_team":at.get("displayName") or "",
            "home_score":home.get("score"),
            "away_score":away.get("score"),
            "home_logo":ht.get("logo") or "",
            "away_logo":at.get("logo") or "",
            "minute":status.get("shortDetail") or status.get("detail") or "",
            "status":status.get("description") or status.get("detail") or "LIVE",
            "competition":((comp.get("league") or {}).get("name") or "Football")
        })
    return {"source":"ESPN soccer/all","live_available":True,"date":d,"count":len(out),"events":out}
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
            "strCompetitionId":comp.get("id"),
            "strLeagueId":((comp.get("league") or {}).get("id") or ""),
            "strSeason":(season.get("displayName") or season.get("year") or ""),
            "strWeek":((ev.get("week") or {}).get("number") if isinstance(ev.get("week"),dict) else ev.get("week")),
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


async def espn_event_details(event_id):
    eid=str(event_id).replace("espn-", "")
    async with httpx.AsyncClient(timeout=20) as c:
        r=await c.get(f"{ESPN_BASE}/all/summary",params={"event":eid})
        r.raise_for_status()
        return r.json()


async def espn_recent_results(date=None, days=45):
    """Fetch a rolling window of completed soccer results from ESPN's broad feed."""
    end=datetime.fromisoformat(date or today_utc()).date()
    start=end - __import__("datetime").timedelta(days=days)
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.get(
                f"{ESPN_BASE}/all/scoreboard",
                params={"dates":f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"}
            )
            r.raise_for_status()
            data=r.json()
    except Exception:
        return {"source":"ESPN","events":[]}
    out=[]
    for ev in data.get("events") or []:
        comp=(ev.get("competitions") or [{}])[0]
        teams=comp.get("competitors") or []
        home=next((x for x in teams if x.get("homeAway")=="home"),None)
        away=next((x for x in teams if x.get("homeAway")=="away"),None)
        if not home or not away:
            continue
        hs=home.get("score")
        aws=away.get("score")
        try:
            hs=float(hs); aws=float(aws)
        except (TypeError,ValueError):
            continue
        status=((comp.get("status") or {}).get("type") or {}).get("completed")
        if status is False:
            continue
        out.append({
            "date":(ev.get("date") or "")[:10],
            "home_team":(home.get("team") or {}).get("displayName"),
            "away_team":(away.get("team") or {}).get("displayName"),
            "home_goals":hs,
            "away_goals":aws,
            "event_id":"espn-"+str(ev.get("id"))
        })
    return {"source":"ESPN","events":out}
