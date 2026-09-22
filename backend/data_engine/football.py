import httpx
from datetime import datetime, timezone
from backend.config import THESPORTSDB_KEY

BASE = "https://www.thesportsdb.com/api/v1/json"


def _url(path: str) -> str:
    return f"{BASE}/{THESPORTSDB_KEY}/{path}"


async def api_get(path: str, params: dict | None = None):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(_url(path), params=params or {})
        r.raise_for_status()
        return r.json()


def today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


async def todays_fixtures():
    data = await api_get("eventsday.php", {"d": today_utc(), "s": "Soccer"})
    return {
        "source": "TheSportsDB",
        "date": today_utc(),
        "events": data.get("events") or [],
    }


async def live_fixtures():
    # The free TheSportsDB V1 API does not provide premium live-score data.
    # Return today's football schedule so the dashboard remains useful.
    data = await todays_fixtures()
    return {
        "source": "TheSportsDB",
        "live_available": False,
        "message": "TheSportsDB live scores require premium access; showing today's football events instead.",
        "date": data["date"],
        "events": data["events"],
    }


async def fixture(fixture_id: int):
    data = await api_get("lookupevent.php", {"id": fixture_id})
    return {
        "source": "TheSportsDB",
        "events": data.get("events") or [],
    }


async def team_last_results(team_id: int, last: int = 10):
    data = await api_get("eventslast.php", {"id": team_id})
    events = data.get("results") or []
    return {
        "source": "TheSportsDB",
        "events": events[:last],
    }


async def h2h(home_id: int, away_id: int, last: int = 10):
    # V1 free API has no direct H2H endpoint. Keep a stable empty response.
    return {
        "source": "TheSportsDB",
        "events": [],
        "message": "Head-to-head is not available through the free TheSportsDB V1 endpoint.",
    }
