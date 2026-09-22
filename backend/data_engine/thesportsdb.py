import httpx
from backend.config import THESPORTSDB_KEY

BASE = "https://www.thesportsdb.com/api/v1/json"

async def search_team(name: str):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{BASE}/{THESPORTSDB_KEY}/searchteams.php", params={"t": name})
        r.raise_for_status()
        return r.json()
