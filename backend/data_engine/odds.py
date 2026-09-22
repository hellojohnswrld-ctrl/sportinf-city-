import httpx
from backend.config import ODDS_API_KEY, ODDS_API_REGION, ODDS_API_SPORT

BASE = "https://api.the-odds-api.com/v4"


def _norm(value: str) -> str:
    return "".join(ch.lower() for ch in (value or "") if ch.isalnum())


async def fetch_odds():
    if not ODDS_API_KEY:
        return []
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": ODDS_API_REGION,
        "markets": "h2h",
        "oddsFormat": "decimal",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{BASE}/sports/{ODDS_API_SPORT}/odds", params=params)
        r.raise_for_status()
        return r.json()


def match_odds(events, odds_events):
    output = {}
    for game in odds_events or []:
        home = _norm(game.get("home_team"))
        away = _norm(game.get("away_team"))
        if not home or not away:
            continue
        bookmakers = game.get("bookmakers") or []
        best = {}
        best_book = {}
        for book in bookmakers:
            for market in book.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name")
                    price = outcome.get("price")
                    try:
                        price = float(price)
                    except (TypeError, ValueError):
                        continue
                    key = "home" if _norm(name) == home else "away" if _norm(name) == away else "draw" if _norm(name) == "draw" else None
                    if key and price > 1 and (key not in best or price > best[key]):
                        best[key] = price
                        best_book[key] = book.get("title") or book.get("key") or "Bookmaker"
        if len(best) >= 2:
            output[(home, away)] = {
                "bookmaker": best_book,
                "odds": best,
                "source": "The Odds API",
                "updated": max((b.get("last_update", "") for b in bookmakers), default=""),
            }
    return output


def value_layer(prediction, odds):
    if not odds:
        return None
    model = {
        "home": float(prediction.get("home_probability", 0)),
        "draw": float(prediction.get("draw_probability", 0)),
        "away": float(prediction.get("away_probability", 0)),
    }
    values = {}
    for key, price in odds.get("odds", {}).items():
        implied = 1.0 / price
        edge = model[key] - implied
        ev = model[key] * price - 1.0
        values[key] = {
            "odds": round(price, 3),
            "implied_probability": round(implied, 4),
            "model_probability": round(model[key], 4),
            "edge": round(edge, 4),
            "expected_value": round(ev, 4),
            "value": ev > 0,
        }
    return values
