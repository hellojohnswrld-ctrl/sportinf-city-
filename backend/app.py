from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.config import APP_NAME, APP_VERSION, THESPORTSDB_KEY
from backend.data_engine import football
from backend.prediction_engine.football_model import baseline
from backend.storage.prediction_store import log_prediction

app = FastAPI(title=APP_NAME, version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse("frontend/index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "sports_data_provider": "TheSportsDB",
        "thesportsdb_configured": bool(THESPORTSDB_KEY),
    }


@app.get("/api/health")
async def api_health():
    return await health()


@app.get("/api/live")
async def live():
    return await football.live_fixtures()


@app.get("/api/fixtures/today")
async def today():
    return await football.todays_fixtures()


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _form_stats(events, team_id):
    played = points = gd = 0.0
    for e in events:
        if str(e.get("idHomeTeam")) == str(team_id):
            gf, ga = _num(e.get("intHomeScore")), _num(e.get("intAwayScore"))
        elif str(e.get("idAwayTeam")) == str(team_id):
            gf, ga = _num(e.get("intAwayScore")), _num(e.get("intHomeScore"))
        else:
            continue
        if e.get("intHomeScore") in (None, "") or e.get("intAwayScore") in (None, ""):
            continue
        played += 1
        gd += gf - ga
        points += 3 if gf > ga else 1 if gf == ga else 0
    return {
        "played": int(played),
        "ppg": round(points / played, 3) if played else 1.0,
        "avg_goal_difference": round(gd / played, 3) if played else 0.0,
    }


async def _predict_event(event):
    home_id = event.get("idHomeTeam")
    away_id = event.get("idAwayTeam")
    if not home_id or not away_id:
        return None

    home_data, away_data = await __import__("asyncio").gather(
        football.team_last_results(int(home_id), 10),
        football.team_last_results(int(away_id), 10),
    )
    home_form = _form_stats(home_data.get("events", []), home_id)
    away_form = _form_stats(away_data.get("events", []), away_id)

    prediction = baseline(
        home_form["ppg"],
        away_form["ppg"],
        home_form["avg_goal_difference"],
        away_form["avg_goal_difference"],
    )

    result = {
        "fixture_id": event.get("idEvent"),
        "home_team": event.get("strHomeTeam"),
        "away_team": event.get("strAwayTeam"),
        "date": event.get("dateEvent"),
        "time": event.get("strTime"),
        "league": event.get("strLeague"),
        "venue": event.get("strVenue"),
        "home_form": home_form,
        "away_form": away_form,
        "prediction": prediction,
        "model_note": "Transparent baseline using recent points-per-game, goal difference and home advantage. Not a guarantee.",
    }
    log_prediction(result)
    return result


@app.get("/api/predict/{fixture_id}")
async def predict_fixture(fixture_id: int):
    data = await football.fixture(fixture_id)
    events = data.get("events") or []
    if not events:
        return {"error": "Fixture not found", "fixture_id": fixture_id}
    result = await _predict_event(events[0])
    return result or {"error": "Unable to build prediction", "fixture_id": fixture_id}


@app.get("/api/predictions/today")
async def predictions_today():
    data = await football.todays_fixtures()
    events = data.get("events") or []
    results = []
    for event in events[:8]:
        result = await _predict_event(event)
        if result:
            results.append(result)
    return {"source": "TheSportsDB", "date": data.get("date"), "count": len(results), "predictions": results}


@app.get("/api/fixture/{fixture_id}")
async def get_fixture(fixture_id: int):
    return await football.fixture(fixture_id)


@app.get("/api/analyze/demo")
async def demo_analyze():
    result = baseline(1.75, 1.25, 0.8, -0.1, {"home": 2.0, "draw": 3.4, "away": 3.8})
    log_prediction({"fixture_id": "demo", "prediction": result})
    return result


@app.get("/docs-info")
async def docs_info():
    return {
        "swagger": "/docs",
        "health": "/health",
        "live": "/api/live",
        "fixtures": "/api/fixtures/today",
        "predictions": "/api/predictions/today",
        "provider": "TheSportsDB",
    }
