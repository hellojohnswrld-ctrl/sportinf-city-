from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from backend.config import APP_NAME,APP_VERSION,THESPORTSDB_KEY,ODDS_API_KEY,ODDS_API_REGION,ODDS_API_SPORT,ODDS_API_ALL_SOCCER
from backend.data_engine import football
from backend.data_engine.odds import fetch_odds,fetch_all_soccer_odds,match_odds,value_layer,analysis_layer
from backend.prediction_engine.football_model import baseline
from backend.storage.prediction_store import log_prediction
import asyncio
app=FastAPI(title=APP_NAME,version=APP_VERSION)
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
@app.get("/",include_in_schema=False)
async def root():return FileResponse("frontend/index.html")
@app.get("/health")
async def health():return {"status":"ok","sports_data_provider":"TheSportsDB","thesportsdb_configured":bool(THESPORTSDB_KEY),"odds_provider":"The Odds API","odds_configured":bool(ODDS_API_KEY),"odds_region":ODDS_API_REGION,"all_soccer_scanning":ODDS_API_ALL_SOCCER}
@app.get("/api/health")
async def api_health():return await health()
@app.get("/api/live")
async def live():return await football.live_fixtures()
@app.get("/api/fixtures/today")
async def today():return await football.todays_fixtures()
def _num(v,d=0.0):
    try:return float(v)
    except(TypeError,ValueError):return d
def _form_stats(events,team_id):
    played=points=gd=0.0
    for e in events:
        if str(e.get("idHomeTeam"))==str(team_id):gf,ga=_num(e.get("intHomeScore")),_num(e.get("intAwayScore"))
        elif str(e.get("idAwayTeam"))==str(team_id):gf,ga=_num(e.get("intAwayScore")),_num(e.get("intHomeScore"))
        else:continue
        if e.get("intHomeScore") in (None,"") or e.get("intAwayScore") in (None,""):continue
        played+=1;gd+=gf-ga;points+=3 if gf>ga else 1 if gf==ga else 0
    return {"played":int(played),"ppg":round(points/played,3) if played else 1.0,"avg_goal_difference":round(gd/played,3) if played else 0.0}
def _key(v):return "".join(ch.lower() for ch in (v or "") if ch.isalnum())
async def _odds_map():
    if not ODDS_API_KEY:return {},[]
    try:
        sports,games=await fetch_all_soccer_odds(ODDS_API_REGION) if ODDS_API_ALL_SOCCER else ([],await fetch_odds())
        return match_odds([],games),sports
    except Exception:return {},[]
async def _predict_event(event,odds_map=None):
    hi,ai=event.get("idHomeTeam"),event.get("idAwayTeam")
    if not hi or not ai:return None
    hd,ad=await asyncio.gather(football.team_last_results(int(hi),10),football.team_last_results(int(ai),10))
    hf,af=_form_stats(hd.get("events",[]),hi),_form_stats(ad.get("events",[]),ai)
    pred=baseline(hf["ppg"],af["ppg"],hf["avg_goal_difference"],af["avg_goal_difference"])
    odds=odds_map.get((_key(event.get("strHomeTeam")),_key(event.get("strAwayTeam")))) if odds_map else None
    val=value_layer(pred,odds)
    out={"fixture_id":event.get("idEvent"),"home_team":event.get("strHomeTeam"),"away_team":event.get("strAwayTeam"),"date":event.get("dateEvent"),"time":event.get("strTime"),"league":event.get("strLeague"),"venue":event.get("strVenue"),"home_form":hf,"away_form":af,"prediction":pred,"odds":odds,"value":val,"analysis":analysis_layer(pred,val),"model_note":"Baseline model using recent form, goal difference and home advantage. Not a guarantee."}
    log_prediction(out);return out
async def _scan_game(game,odds_map):
    home,away=game.get("home_team"),game.get("away_team")
    try:
        hs,as_=await asyncio.gather(football.search_team(home),football.search_team(away))
        h=next((x for x in hs if str(x.get("strSport","" )).lower()=="soccer"),hs[0] if hs else None);a=next((x for x in as_ if str(x.get("strSport","" )).lower()=="soccer"),as_[0] if as_ else None)
        if h and a:
            event={"idEvent":game.get("id"),"idHomeTeam":h.get("idTeam"),"idAwayTeam":a.get("idTeam"),"strHomeTeam":home,"strAwayTeam":away,"dateEvent":(game.get("commence_time") or "")[:10],"strTime":(game.get("commence_time") or "")[11:16],"strLeague":game.get("sport_title")}
            return await _predict_event(event,odds_map)
    except Exception:pass
    return {"fixture_id":game.get("id"),"home_team":home,"away_team":away,"date":(game.get("commence_time") or "")[:10],"time":(game.get("commence_time") or "")[11:16],"league":game.get("sport_title"),"odds":odds_map.get((_key(home),_key(away))),"value":None,"analysis":{"signal":"ODDS_ONLY","score":0,"reasons":["Fixture found from bookmaker feeds; recent-form team lookup was unavailable."]}}
@app.get("/api/predict/{fixture_id}")
async def predict_fixture(fixture_id:int):
    data=await football.fixture(fixture_id);events=data.get("events") or []
    if not events:return {"error":"Fixture not found","fixture_id":fixture_id}
    return await _predict_event(events[0],(await _odds_map())[0])
@app.get("/api/predictions/today")
async def predictions_today():
    data=await football.todays_fixtures();odds_map,_=await _odds_map();results=[]
    for e in (data.get("events") or [])[:8]:
        r=await _predict_event(e,odds_map)
        if r:results.append(r)
    return {"source":"TheSportsDB","date":data.get("date"),"count":len(results),"odds_configured":bool(ODDS_API_KEY),"predictions":results}
@app.get("/api/scan/today")
async def scan_today():
    if not ODDS_API_KEY:return {"error":"ODDS_API_KEY is not configured","matches":[]}
    odds_map,sports=await _odds_map();games=[]
    for key in list(odds_map):
        pass
    # Re-fetch raw all-soccer games so the scanner can include every available bookmaker fixture.
    try:_,raw=await fetch_all_soccer_odds(ODDS_API_REGION) if ODDS_API_ALL_SOCCER else ([],await fetch_odds())
    except Exception:return {"error":"Unable to load odds feeds","matches":[]}
    unique={(_key(g.get("home_team")),_key(g.get("away_team"))):g for g in raw}
    for g in list(unique.values()):games.append(await _scan_game(g,odds_map))
    games.sort(key=lambda x:(-(x.get("analysis") or {}).get("score",0),x.get("date") or "",x.get("time") or ""))
    return {"source":"The Odds API + TheSportsDB","date":"today","sports_scanned":len(sports),"matches":games,"count":len(games),"note":"Scanner aggregates available bookmaker feeds and enriches matches with TheSportsDB form where team matching succeeds. It does not place bets or guarantee outcomes."}
@app.get("/api/fixture/{fixture_id}")
async def get_fixture(fixture_id:int):return await football.fixture(fixture_id)
@app.get("/docs-info")
async def docs_info():return {"swagger":"/docs","health":"/health","live":"/api/live","fixtures":"/api/fixtures/today","predictions":"/api/predictions/today","scanner":"/api/scan/today","provider":"TheSportsDB","odds_provider":"The Odds API"}
