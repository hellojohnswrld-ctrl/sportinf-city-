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
    return {"played":int(played),"ppg":round(points/played,3) if played else 1.0,"avg_goal_difference":round(gd/played,3) if played else 0.0,"avg_goals_for":round(sum(_num(e.get("intHomeScore") if str(e.get("idHomeTeam"))==str(team_id) else e.get("intAwayScore")) for e in events if str(e.get("idHomeTeam"))==str(team_id) or str(e.get("idAwayTeam"))==str(team_id))/played,3) if played else 1.4,"avg_goals_against":round(sum(_num(e.get("intAwayScore") if str(e.get("idHomeTeam"))==str(team_id) else e.get("intHomeScore")) for e in events if str(e.get("idHomeTeam"))==str(team_id) or str(e.get("idAwayTeam"))==str(team_id))/played,3) if played else 1.4}
def _key(v):return "".join(ch.lower() for ch in (v or "") if ch.isalnum())
def _name_form_stats(events):
    stats={}
    for e in events or []:
        h,a=e.get("home_team"),e.get("away_team")
        if not h or not a: continue
        hg,ag=_num(e.get("home_goals")),_num(e.get("away_goals"))
        for name,gf,ga in ((h,hg,ag),(a,ag,hg)):
            k=_key(name)
            if not k: continue
            x=stats.setdefault(k,{"played":0,"points":0.0,"gf":0.0,"ga":0.0})
            x["played"]+=1; x["gf"]+=gf; x["ga"]+=ga
            x["points"]+=3 if gf>ga else 1 if gf==ga else 0
    for x in stats.values():
        n=x["played"]; x.update(ppg=x["points"]/n if n else 1.0,
                                avg_goal_difference=(x["gf"]-x["ga"])/n if n else 0.0,
                                avg_goals_for=x["gf"]/n if n else 1.4,
                                avg_goals_against=x["ga"]/n if n else 1.4)
    return stats


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
    # Free-first scanner: aggregate TheSportsDB + ESPN before analysis.
    # Odds are optional enrichment; a missing odds feed must never prevent analysis.
    try:
        data = await football.todays_fixtures()
    except Exception as exc:
        return {"error":"Unable to load today's football fixtures","matches":[],"detail":str(exc)}

    events = data.get("events") or []
    # TheSportsDB free tier can return a very small schedule slice. ESPN adds
    # broad free fixture coverage across many domestic and UEFA competitions.
    try:
        espn = await football.espn_fixtures(data.get("date"))
        events.extend(espn.get("events") or [])
    except Exception:
        pass
    unique_events = {}
    for e in events:
        k = (_key(e.get("strHomeTeam")), _key(e.get("strAwayTeam")), e.get("dateEvent"))
        if k[0] and k[1]: unique_events[k] = e
    events = list(unique_events.values())
    # Build a broad historical form database from ESPN's soccer-wide results.
    # This avoids the 3-match/1-team free limits of TheSportsDB for analysis.
    try:
        recent = await football.espn_recent_results(data.get("date"), 45)
        espn_form = _name_form_stats(recent.get("events") or [])
    except Exception:
        espn_form = {}

    odds_map = {}
    odds_status = "not_configured"
    if ODDS_API_KEY:
        try:
            odds_map, _ = await _odds_map()
            odds_status = "available"
        except Exception:
            odds_status = "unavailable"

    # The free TheSportsDB V1 tier is rate-limited. Enrich a bounded set of
    # unique teams with recent form, while still producing a prediction for
    # every fixture using a neutral baseline when form is unavailable.
    unique_teams = []
    seen = set()
    for e in events:
        for side in ("idHomeTeam","idAwayTeam"):
            tid = e.get(side)
            # Only numeric TheSportsDB IDs can use the free form-history endpoint.
            # ESPN IDs remain fixture-only so they are never sent to TheSportsDB.
            if tid and str(tid).isdigit() and str(tid) not in seen:
                seen.add(str(tid))
                unique_teams.append(int(tid))

    form_cache = {}
    sem = asyncio.Semaphore(6)
    async def load_form(tid):
        async with sem:
            try:
                d = await football.team_last_results(tid, 10)
                return tid, _form_stats(d.get("events", []), tid)
            except Exception:
                return tid, {"played":0,"ppg":1.0,"avg_goal_difference":0.0}

    # 24 team lookups = 12 matches of detailed recent-form enrichment.
    # All remaining fixtures still receive a model result, explicitly marked
    # as low-data rather than silently pretending recent form was available.
    for i in range(0, min(len(unique_teams), 24), 6):
        batch = unique_teams[i:i+6]
        for tid, stats in await asyncio.gather(*(load_form(x) for x in batch)):
            form_cache[tid] = stats

    matches = []
    for e in events:
        hi, ai = e.get("idHomeTeam"), e.get("idAwayTeam")
        neutral={"played":0,"ppg":1.0,"avg_goal_difference":0.0,"avg_goals_for":1.4,"avg_goals_against":1.4}
        hf = form_cache.get(int(hi), neutral) if hi and str(hi).isdigit() else espn_form.get(_key(e.get("strHomeTeam")), neutral)
        af = form_cache.get(int(ai), neutral) if ai and str(ai).isdigit() else espn_form.get(_key(e.get("strAwayTeam")), neutral)
        market=None
        if odds_map:
            oo=odds_map.get((_key(e.get("strHomeTeam")),_key(e.get("strAwayTeam"))))
            if oo:
                market={k:1/v for k,v in oo.get("odds",{}).items() if v and v>1}
        pred = baseline(hf["ppg"], af["ppg"], hf["avg_goal_difference"], af["avg_goal_difference"],
                        odds=None)
        from backend.prediction_engine.football_model import advanced_model
        pred = advanced_model(hf["ppg"],af["ppg"],hf["avg_goal_difference"],af["avg_goal_difference"],
                              hf.get("avg_goals_for",1.4),hf.get("avg_goals_against",1.4),
                              af.get("avg_goals_for",1.4),af.get("avg_goals_against",1.4),
                              hf.get("played",0),af.get("played",0),market)
        odds = odds_map.get((_key(e.get("strHomeTeam")),_key(e.get("strAwayTeam")))) if odds_map else None
        val = value_layer(pred, odds)
        detailed = hf["played"] > 0 and af["played"] > 0
        analysis = analysis_layer(pred, val)
        if not detailed:
            analysis = {
                **analysis,
                "signal": "LOW_DATA" if not val else analysis.get("signal","LOW_DATA"),
                "reasons": ["Recent-form enrichment was unavailable within the free data-source rate limits.", *analysis.get("reasons", [])]
            }
        matches.append({
            "fixture_id": e.get("idEvent"),
            "home_team": e.get("strHomeTeam"),
            "away_team": e.get("strAwayTeam"),
            "date": e.get("dateEvent"),
            "time": e.get("strTime"),
            "league": e.get("strLeague"),
            "venue": e.get("strVenue"),
            "home_form": hf,
            "away_form": af,
            "data_sources": ["ESPN historical results"] if not (hi and str(hi).isdigit() and ai and str(ai).isdigit()) else ["TheSportsDB recent results","ESPN historical results"],
            "prediction": pred,
            "odds": odds,
            "value": val,
            "analysis": analysis,
            "data_quality": "detailed" if detailed else "fixture_only",
            "model_note": "Advanced model uses a 45-day historical window, goals for/against, points rate, goal difference, home advantage and Poisson scoreline probabilities. Bookmaker prices are used only as a small calibration input when available. Not a guarantee."
        })

    matches.sort(key=lambda x: (-(x.get("analysis") or {}).get("score",0), x.get("time") or "", x.get("home_team") or ""))
    return {
        "source":"ESPN soccer/all + TheSportsDB",
        "date":data.get("date"),
        "count":len(matches),
        "odds_status":odds_status,
        "matches":matches,
        "coverage_note":"Fixtures come from TheSportsDB plus ESPN's soccer-wide scoreboard. Historical form is independently built from ESPN's rolling 45-day results, so ESPN fixtures no longer depend on TheSportsDB team-history limits. TheSportsDB history is retained as an additional source where available."
    }

@app.get("/api/fixture/{fixture_id}")
async def get_fixture(fixture_id:int):return await football.fixture(fixture_id)
@app.get("/docs-info")
async def docs_info():return {"swagger":"/docs","health":"/health","live":"/api/live","fixtures":"/api/fixtures/today","predictions":"/api/predictions/today","scanner":"/api/scan/today","provider":"TheSportsDB","odds_provider":"The Odds API"}
