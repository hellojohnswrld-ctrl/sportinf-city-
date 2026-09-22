from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from backend.config import APP_NAME, APP_VERSION, THESPORTSDB_KEY, ODDS_API_KEY, ODDS_API_REGION, ODDS_API_SPORT
from backend.data_engine import football
from backend.data_engine.odds import fetch_odds, match_odds, value_layer
from backend.prediction_engine.football_model import baseline
from backend.storage.prediction_store import log_prediction

app=FastAPI(title=APP_NAME,version=APP_VERSION)
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

@app.get("/",include_in_schema=False)
async def root(): return FileResponse("frontend/index.html")

@app.get("/health")
async def health(): return {"status":"ok","sports_data_provider":"TheSportsDB","thesportsdb_configured":bool(THESPORTSDB_KEY),"odds_provider":"The Odds API","odds_configured":bool(ODDS_API_KEY),"odds_region":ODDS_API_REGION,"odds_sport":ODDS_API_SPORT}
@app.get("/api/health")
async def api_health(): return await health()
@app.get("/api/live")
async def live(): return await football.live_fixtures()
@app.get("/api/fixtures/today")
async def today(): return await football.todays_fixtures()

def _num(v,d=0.0):
    try:return float(v)
    except(TypeError,ValueError):return d

def _form_stats(events,team_id):
    played=points=gd=0.0
    for e in events:
        if str(e.get("idHomeTeam"))==str(team_id): gf,ga=_num(e.get("intHomeScore")),_num(e.get("intAwayScore"))
        elif str(e.get("idAwayTeam"))==str(team_id): gf,ga=_num(e.get("intAwayScore")),_num(e.get("intHomeScore"))
        else: continue
        if e.get("intHomeScore") in (None,"") or e.get("intAwayScore") in (None,""): continue
        played+=1;gd+=gf-ga;points+=3 if gf>ga else 1 if gf==ga else 0
    return {"played":int(played),"ppg":round(points/played,3) if played else 1.0,"avg_goal_difference":round(gd/played,3) if played else 0.0}

def _key(name): return "".join(ch.lower() for ch in (name or "") if ch.isalnum())

async def _odds_map():
    if not ODDS_API_KEY:return {}
    try:return match_odds([],await fetch_odds())
    except Exception:return {}

async def _predict_event(event,odds_map=None):
    home_id,away_id=event.get("idHomeTeam"),event.get("idAwayTeam")
    if not home_id or not away_id:return None
    import asyncio
    hd,ad=await asyncio.gather(football.team_last_results(int(home_id),10),football.team_last_results(int(away_id),10))
    hf,af=_form_stats(hd.get("events",[]),home_id),_form_stats(ad.get("events",[]),away_id)
    prediction=baseline(hf["ppg"],af["ppg"],hf["avg_goal_difference"],af["avg_goal_difference"])
    odds=odds_map.get((_key(event.get("strHomeTeam")),_key(event.get("strAwayTeam")))) if odds_map else None
    result={"fixture_id":event.get("idEvent"),"home_team":event.get("strHomeTeam"),"away_team":event.get("strAwayTeam"),"date":event.get("dateEvent"),"time":event.get("strTime"),"league":event.get("strLeague"),"venue":event.get("strVenue"),"home_form":hf,"away_form":af,"prediction":prediction,"odds":odds,"value":value_layer(prediction,odds),"model_note":"Transparent baseline using recent points-per-game, goal difference and home advantage. Not a guarantee."}
    log_prediction(result);return result

@app.get("/api/predict/{fixture_id}")
async def predict_fixture(fixture_id:int):
    data=await football.fixture(fixture_id);events=data.get("events") or []
    if not events:return {"error":"Fixture not found","fixture_id":fixture_id}
    return await _predict_event(events[0],await _odds_map())

@app.get("/api/predictions/today")
async def predictions_today():
    data=await football.todays_fixtures();events=data.get("events") or [];odds_map=await _odds_map();results=[]
    for event in events[:8]:
        result=await _predict_event(event,odds_map)
        if result:results.append(result)
    return {"source":"TheSportsDB","date":data.get("date"),"count":len(results),"odds_configured":bool(ODDS_API_KEY),"predictions":results}

@app.get("/api/fixture/{fixture_id}")
async def get_fixture(fixture_id:int):return await football.fixture(fixture_id)
@app.get("/api/analyze/demo")
async def demo_analyze():
    result=baseline(1.75,1.25,.8,-.1,{"home":2.0,"draw":3.4,"away":3.8});log_prediction({"fixture_id":"demo","prediction":result});return result
@app.get("/docs-info")
async def docs_info():return {"swagger":"/docs","health":"/health","live":"/api/live","fixtures":"/api/fixtures/today","predictions":"/api/predictions/today","provider":"TheSportsDB","odds_provider":"The Odds API","odds_configured":bool(ODDS_API_KEY)}
