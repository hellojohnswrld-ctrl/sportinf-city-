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
        "provider": "TheSportsDB",
    }
