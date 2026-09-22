import httpx
from backend.config import API_FOOTBALL_KEY

BASE = "https://v3.football.api-sports.io"

def _headers():
    return {"x-apisports-key": API_FOOTBALL_KEY}

async def api_get(path: str, params: dict | None = None):
    if not API_FOOTBALL_KEY:
        return {"response": [], "errors": {"message": "API_FOOTBALL_KEY is not configured"}}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{BASE}/{path}", headers=_headers(), params=params or {})
        r.raise_for_status()
        return r.json()

async def todays_fixtures():
    return await api_get("fixtures", {"date": "2026-09-22"})

async def live_fixtures():
    return await api_get("fixtures", {"live": "all"})

async def fixture(fixture_id: int):
    return await api_get("fixtures", {"id": fixture_id})

async def team_last_results(team_id: int, last: int = 10):
    return await api_get("fixtures", {"team": team_id, "last": last})

async def h2h(home_id: int, away_id: int, last: int = 10):
    return await api_get("fixtures/headtohead", {"h2h": f"{home_id}-{away_id}", "last": last})
