from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi import Request
import os,hmac,hashlib,base64,time,httpx,datetime
from backend.config import APP_NAME,APP_VERSION,THESPORTSDB_KEY,ODDS_API_KEY,ODDS_API_REGION,ODDS_API_SPORT,ODDS_API_ALL_SOCCER,PAYDUNYA_MASTER_KEY,PAYDUNYA_PRIVATE_KEY,PAYDUNYA_TOKEN,VIP_PRICE_XOF,VIP_MERCHANT_NAME
from backend.data_engine import football
from backend.data_engine.odds import fetch_odds,fetch_all_soccer_odds,match_odds,value_layer,analysis_layer
from backend.prediction_engine.football_model import baseline
from backend.storage.prediction_store import log_prediction
import asyncio
app=FastAPI(title=APP_NAME,version=APP_VERSION)
ACCESS_CODE=os.getenv("JOHN_ACCESS_CODE","")
ACCESS_SECRET=os.getenv("JOHN_ACCESS_SECRET","")
ACCESS_TTL=60*60*24*7

def _access_token():
    payload=str(int(time.time()))
    sig=hmac.new(ACCESS_SECRET.encode(),payload.encode(),hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode((payload+"."+sig).encode()).decode()

def _access_valid(token):
    if not token or not ACCESS_SECRET:
        return False
    try:
        raw=base64.urlsafe_b64decode(token.encode()).decode()
        ts,sig=raw.split(".",1)
        if time.time()-int(ts)>ACCESS_TTL:return False
        expected=hmac.new(ACCESS_SECRET.encode(),ts.encode(),hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig,expected)
    except Exception:
        return False

@app.middleware("http")
async def access_gate(request:Request,call_next):
    path=request.url.path
    if path.startswith("/api/") and path!="/api/access":
        if not _access_valid(request.cookies.get("john_access")):
            return JSONResponse({"error":"Access key required"},status_code=401)
    return await call_next(request)

app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
@app.get("/",include_in_schema=False)
async def root():return FileResponse("frontend/index.html")
@app.get("/api/access/status")
async def access_status(request:Request):
    return {"authenticated":_access_valid(request.cookies.get("john_access"))}

@app.post("/api/access")
async def access_login(request:Request):
    try:
        data=await request.json()
        code=str(data.get("code","")).strip()
    except Exception:
        code=""
    if not ACCESS_CODE or not hmac.compare_digest(code,ACCESS_CODE):
        return JSONResponse({"error":"Invalid access key"},status_code=401)
    response=JSONResponse({"authenticated":True})
    response.set_cookie("john_access",_access_token(),httponly=True,secure=True,samesite="lax",max_age=ACCESS_TTL,path="/")
    return response

@app.post("/api/access/logout")
async def access_logout():
    response=JSONResponse({"authenticated":False})
    response.delete_cookie("john_access",path="/")
    return response

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
def _competition_category(name):
    n=(name or "").lower()
    if any(x in n for x in ("friendly","international friendly")): return "Friendly"
    if any(x in n for x in ("qualifying","qualification","qualifiers")): return "Qualification"
    if any(x in n for x in ("cup","copa","fa cup","knvb","beker","coupe","trophy","shield","super cup","community shield")): return "Cup"
    if any(x in n for x in ("world cup","champions league","europa league","conference league","libertadores","sudamericana","champions cup","nations league","african nations","asian cup","gold cup","copa am")): return "International/Tournament"
    if any(x in n for x in ("women","womens","women's")): return "Women's League"
    return "League"
def _decorate_event(e):
    out=dict(e)
    out["competition_category"]=_competition_category(out.get("strLeague") or out.get("league"))
    return out
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
    out={"fixture_id":event.get("idEvent"),"home_team":event.get("strHomeTeam"),"away_team":event.get("strAwayTeam"),"home_logo":event.get("strHomeTeamBadge") or event.get("home_logo") or "","away_logo":event.get("strAwayTeamBadge") or event.get("away_logo") or "","date":event.get("dateEvent"),"time":event.get("strTime"),"league":event.get("strLeague"),"venue":event.get("strVenue"),"home_form":hf,"away_form":af,"prediction":pred,"odds":odds,"value":val,"analysis":analysis_layer(pred,val),"model_note":"Baseline model using recent form, goal difference and home advantage. Not a guarantee."}
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
@app.get("/api/search")
async def search_matches(q: str = "", category: str = "all"):
    """Search today's broad football feed by teams/competition and filter by competition type."""
    try:
        data=await football.todays_fixtures()
        events=data.get("events") or []
        try:
            espn=await football.espn_fixtures(data.get("date"))
            events.extend(espn.get("events") or [])
        except Exception:
            pass
    except Exception as exc:
        return {"error":"Unable to load football fixtures","matches":[],"detail":str(exc)}
    unique={}
    for e in events:
        k=(_key(e.get("strHomeTeam")),_key(e.get("strAwayTeam")),e.get("dateEvent"))
        if not (k[0] and k[1]): continue
        if k not in unique: unique[k]=e
        else:
            cur=unique[k]
            for fld in ("strHomeTeamBadge","strAwayTeamBadge","strVenue","idHomeTeam","idAwayTeam","idEvent","strLeague"):
                if not cur.get(fld) and e.get(fld): cur[fld]=e.get(fld)
    query=_key(q); wanted=(category or "all").lower()
    matches=[]
    for e in unique.values():
        x=_decorate_event(e); cat=x["competition_category"]
        hay=_key(" ".join(str(e.get(k) or "") for k in ("strHomeTeam","strAwayTeam","strLeague","strVenue")))
        if query and query not in hay: continue
        if wanted!="all" and cat.lower()!=wanted: continue
        matches.append(x)
    matches.sort(key=lambda x:(x.get("strLeague") or "",x.get("strTime") or "",x.get("strHomeTeam") or ""))
    categories={}
    for x in matches: categories[x["competition_category"]]=categories.get(x["competition_category"],0)+1
    return {"source":"ESPN soccer/all + TheSportsDB","date":data.get("date"),"count":len(matches),"categories":categories,"matches":matches}


@app.get("/api/vip")
async def vip_forecast():
    """Return 15 upcoming matches with the strongest model probabilities."""
    today=datetime.date.today()
    events=[]
    for i in range(0,8):
        try:
            x=await football.espn_fixtures((today+datetime.timedelta(days=i)).isoformat())
            events.extend(x.get("events") or [])
        except Exception:
            pass
    unique={}
    for e in events:
        if (e.get("strStatus") or "").lower() in ("final","completed"):
            continue
        k=(_key(e.get("strHomeTeam")),_key(e.get("strAwayTeam")),e.get("dateEvent"))
        if k[0] and k[1]: unique[k]=e
    try:
        recent=await football.espn_recent_results(today.isoformat(),45)
        espn_form=_name_form_stats(recent.get("events") or [])
    except Exception:
        espn_form={}
    rows=[]
    for e in unique.values():
        neutral={"played":0,"ppg":1.0,"avg_goal_difference":0.0,"avg_goals_for":1.4,"avg_goals_against":1.4}
        hf=espn_form.get(_key(e.get("strHomeTeam")),neutral)
        af=espn_form.get(_key(e.get("strAwayTeam")),neutral)
        pred=baseline(hf["ppg"],af["ppg"],hf["avg_goal_difference"],af["avg_goal_difference"])
        probs={"HOME":float(pred.get("home_probability",0)),"DRAW":float(pred.get("draw_probability",0)),"AWAY":float(pred.get("away_probability",0))}
        top=max(probs,key=probs.get)
        rows.append({"fixture_id":e.get("idEvent"),"home_team":e.get("strHomeTeam"),"away_team":e.get("strAwayTeam"),"competition":e.get("strLeague"),"date":e.get("dateEvent"),"time":e.get("strTime"),"venue":e.get("strVenue"),"home_logo":e.get("strHomeTeamBadge") or "","away_logo":e.get("strAwayTeamBadge") or "","prediction":pred,"selection":top,"selection_probability":probs[top],"data_quality":"standard ESPN recent-form sample"})
    rows.sort(key=lambda x:x["selection_probability"],reverse=True)
    return {"title":"JOHN FORCAST VIP","count":min(15,len(rows)),"matches":rows[:15],"disclaimer":"These are the 15 highest model-probability upcoming matches available to the scanner. Probabilities are estimates, not guarantees."}

@app.post("/api/vip/payment")
async def vip_payment(request:Request):
    if not all((PAYDUNYA_MASTER_KEY,PAYDUNYA_PRIVATE_KEY,PAYDUNYA_TOKEN)):
        return JSONResponse({"error":"VIP payments are not configured yet. Add the PayDunya production keys in Render environment variables."},status_code=503)
    if VIP_PRICE_XOF<=0:
        return JSONResponse({"error":"VIP_PRICE_XOF is not configured yet."},status_code=503)
    try:
        data=await request.json()
    except Exception:
        data={}
    email=str(data.get("email") or "").strip()
    phone=str(data.get("phone") or "").strip()
    provider=str(data.get("provider") or "mobile_money").strip()
    if not email:
        return JSONResponse({"error":"Email is required for the payment receipt."},status_code=400)
    payload={"invoice":{"total_amount":VIP_PRICE_XOF,"description":"JOHN FORCAST VIP — 15-match premium forecast"},"store":{"name":VIP_MERCHANT_NAME},"customer":{"name":"VIP Customer","email":email,"phone":phone}}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r=await client.post("https://app.paydunya.com/api/v1/checkout-invoice/create",json=payload,headers={"PAYDUNYA-MASTER-KEY":PAYDUNYA_MASTER_KEY,"PAYDUNYA-PRIVATE-KEY":PAYDUNYA_PRIVATE_KEY,"PAYDUNYA-TOKEN":PAYDUNYA_TOKEN})
            data=r.json()
        if data.get("response_code")!="00":
            return JSONResponse({"error":data.get("response_text") or "Payment invoice creation failed."},status_code=502)
        return {"ok":True,"payment_url":data.get("response_text"),"token":data.get("token"),"provider":provider,"amount":VIP_PRICE_XOF,"currency":"XOF"}
    except Exception:
        return JSONResponse({"error":"Payment provider is temporarily unavailable."},status_code=502)

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
        if not (k[0] and k[1]): continue
        if k not in unique_events: unique_events[k] = e
        else:
            cur = unique_events[k]
            for fld in ("strHomeTeamBadge","strAwayTeamBadge","strVenue","idHomeTeam","idAwayTeam","idEvent","strLeague"):
                if not cur.get(fld) and e.get(fld): cur[fld] = e.get(fld)
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
            "home_logo": e.get("strHomeTeamBadge") or e.get("home_logo") or "",
            "away_logo": e.get("strAwayTeamBadge") or e.get("away_logo") or "",
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


def _performance_history(events, team_name, limit=10):
    key=_key(team_name)
    rows=[]
    for e in sorted(events or [], key=lambda x:x.get("date") or "", reverse=True):
        h,a=e.get("home_team"),e.get("away_team")
        if _key(h)!=key and _key(a)!=key: continue
        hg,ag=_num(e.get("home_goals")),_num(e.get("away_goals"))
        is_home=_key(h)==key
        gf,ga=(hg,ag) if is_home else (ag,hg)
        points=3 if gf>ga else 1 if gf==ga else 0
        rows.append({"date":e.get("date"),"opponent":a if is_home else h,"home":is_home,
                     "goals_for":gf,"goals_against":ga,"goal_difference":gf-ga,
                     "points":points,"result":"W" if points==3 else "D" if points==1 else "L"})
        if len(rows)>=limit: break
    rows.reverse()
    cumulative=0
    for r in rows:
        cumulative+=r["points"];r["cumulative_points"]=cumulative
    return rows

def _probability_questions(pred, home_form, away_form, odds=None):
    hp=float(pred.get("home_probability",0)); dp=float(pred.get("draw_probability",0)); ap=float(pred.get("away_probability",0))
    questions=[
        {"if":"Home probability is clearly above away probability","then":f"Home is the model's stronger 1X2 outcome at {hp:.1%}; check price and team news before acting.","ask":"Is the available home price high enough to justify the model edge?"},
        {"if":"Draw probability is competitive","then":f"Draw probability is {dp:.1%}; a close expected scoreline can make the draw relevant.","ask":"Does the match profile suggest a low-scoring or balanced game?"},
        {"if":"Away probability is clearly above home probability","then":f"Away is the model's stronger 1X2 outcome at {ap:.1%}; verify away form and price.","ask":"Is the away price consistent with the risk you are taking?"},
        {"if":"Recent data is thin","then":"Treat the probability as a wider-range estimate rather than a precise forecast.","ask":"Do we have enough recent matches, line-up information and competition context?"},
        {"if":"Model probability differs materially from market implied probability","then":"The difference may represent potential value, model error, stale odds, or missing information.","ask":"What evidence could explain the gap before relying on it?"}
    ]
    return questions

@app.get("/api/match/{match_id}/analysis")
async def match_analysis(match_id:str):
    """Return interactive analysis without requiring an ESPN event id."""
    source = "ESPN"
    header = {}
    comp = {}
    event_date = None
    home_name = ""
    away_name = ""
    home_logo = ""
    away_logo = ""
    event = None

    # Resolve the match first. Never make the analysis UI depend on ESPN.
    if match_id.startswith("espn-"):
        try:
            detail = await football.espn_event_details(match_id)
            header = detail.get("header") if isinstance(detail.get("header"), dict) else {}
            competitions = header.get("competitions") if isinstance(header.get("competitions"), list) else []
            comp = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
            competitors = comp.get("competitors") if isinstance(comp.get("competitors"), list) else []
            home = next((x for x in competitors if isinstance(x, dict) and x.get("homeAway") == "home"), None)
            away = next((x for x in competitors if isinstance(x, dict) and x.get("homeAway") == "away"), None)
            home_team_obj = home.get("team") if isinstance(home, dict) and isinstance(home.get("team"), dict) else {}
            away_team_obj = away.get("team") if isinstance(away, dict) and isinstance(away.get("team"), dict) else {}
            home_name = home_team_obj.get("displayName") or ""
            away_name = away_team_obj.get("displayName") or ""
            home_logo = home_team_obj.get("logo") or ""
            away_logo = away_team_obj.get("logo") or ""
            event_date = str(header.get("date") or "")[:10]
        except Exception:
            home_name = away_name = ""
    elif str(match_id).isdigit():
        source = "TheSportsDB"
        try:
            data = await football.fixture(int(match_id))
            events = data.get("events") or []
            event = events[0] if events else None
        except Exception:
            event = None

        # Fallback: the numeric id came from today's fixture feed, so resolve
        # it there if the individual lookup is rate-limited or temporarily fails.
        if not event:
            try:
                day = await football.todays_fixtures()
                event = next((x for x in (day.get("events") or [])
                              if str(x.get("idEvent")) == str(match_id)), None)
            except Exception:
                event = None

        if event:
            home_name = event.get("strHomeTeam") or ""
            away_name = event.get("strAwayTeam") or ""
            home_logo = event.get("strHomeTeamBadge") or ""
            away_logo = event.get("strAwayTeamBadge") or ""
            event_date = event.get("dateEvent") or ""
            comp = {"league": {"name": event.get("strLeague") or "Football"}}
            header = {
                "date": event_date,
                "season": event.get("strSeason") or "",
                "week": event.get("intRound") or event.get("strRound") or "",
            }
    else:
        return {"error":"Unsupported match id","event_id":match_id}

    if not home_name or not away_name:
        return {"error":"Match teams could not be resolved","event_id":match_id}

    # ESPN is used as a broad historical source, but it is optional. The
    # modal must still work when ESPN has no coverage for this competition.
    recent_events = []
    try:
        recent = await football.espn_recent_results(event_date or None, 45)
        recent_events = recent.get("events") or []
    except Exception:
        recent_events = []

    # If ESPN has no history, use the two teams' TheSportsDB recent results
    # as a secondary source. Failure here only means less graph data.
    if not recent_events and event:
        try:
            hs, aws = await asyncio.gather(
                football.search_team(home_name),
                football.search_team(away_name)
            )
            ht = next((x for x in hs if str(x.get("strSport","")).lower()=="soccer"), hs[0] if hs else None)
            at = next((x for x in aws if str(x.get("strSport","")).lower()=="soccer"), aws[0] if aws else None)
            if ht and at:
                hd, ad = await asyncio.gather(
                    football.team_last_results(int(ht.get("idTeam")), 10),
                    football.team_last_results(int(at.get("idTeam")), 10)
                )
                home_hist = hd.get("events") or []
                away_hist = ad.get("events") or []
                recent_events = []
                for x in home_hist:
                    recent_events.append({
                        "date": x.get("dateEvent") or "",
                        "home_team": x.get("strHomeTeam") or "",
                        "away_team": x.get("strAwayTeam") or "",
                        "home_goals": _num(x.get("intHomeScore")),
                        "away_goals": _num(x.get("intAwayScore"))
                    })
                for x in away_hist:
                    recent_events.append({
                        "date": x.get("dateEvent") or "",
                        "home_team": x.get("strHomeTeam") or "",
                        "away_team": x.get("strAwayTeam") or "",
                        "home_goals": _num(x.get("intHomeScore")),
                        "away_goals": _num(x.get("intAwayScore"))
                    })
        except Exception:
            pass

    stats = _name_form_stats(recent_events)
    neutral = {"played":0,"ppg":1.0,"avg_goal_difference":0.0,"avg_goals_for":1.4,"avg_goals_against":1.4}
    hf = stats.get(_key(home_name), neutral)
    af = stats.get(_key(away_name), neutral)
    history_home = _performance_history(recent_events, home_name, 10)
    history_away = _performance_history(recent_events, away_name, 10)

    from backend.prediction_engine.football_model import advanced_model
    pred = advanced_model(
        hf["ppg"], af["ppg"],
        hf["avg_goal_difference"], af["avg_goal_difference"],
        hf.get("avg_goals_for",1.4), hf.get("avg_goals_against",1.4),
        af.get("avg_goals_for",1.4), af.get("avg_goals_against",1.4),
        hf.get("played",0), af.get("played",0), None
    )

    league_obj = comp.get("league") if isinstance(comp.get("league"), dict) else {}
    season_obj = header.get("season") if isinstance(header.get("season"), dict) else {}
    status_obj = comp.get("status") if isinstance(comp.get("status"), dict) else {}
    status_type = status_obj.get("type") if isinstance(status_obj.get("type"), dict) else {}
    venue_obj = comp.get("venue") if isinstance(comp.get("venue"), dict) else {}
    season_raw = header.get("season")
    season_value = season_raw if isinstance(season_raw, (str, int, float)) else ""
    return {
        "source": source,
        "event_id": match_id,
        "home_team": home_name,
        "away_team": away_name,
        "home_logo": home_logo,
        "away_logo": away_logo,
        "competition": league_obj.get("name") or "Football",
        "season": season_obj.get("displayName") or season_obj.get("year") or season_value or "",
        "week": ((header.get("week") or {}).get("number") if isinstance(header.get("week"),dict) else header.get("week")),
        "status": status_type.get("description") or "Scheduled",
        "venue": venue_obj.get("fullName") or "",
        "history": {"home": history_home, "away": history_away},
        "form": {"home": hf, "away": af},
        "prediction": pred,
        "probability_toolbox": _probability_questions(pred, hf, af),
        "questions_to_check": [
            "Is the model based on enough recent matches for both teams?",
            "Is there a meaningful home/away split that this compact model does not capture?",
            "Are injuries, suspensions, rotation or confirmed line-ups changing the expected strength?",
            "Is the bookmaker price materially different from the model probability, and why?",
            "Could this be a cup/qualification situation where incentives differ from league matches?",
            "What is the downside if the model is wrong?"
        ],
        "data_note": "Historical performance is shown when available from ESPN or TheSportsDB. Missing history lowers confidence; it does not block the analysis.",
        "disclaimer": "Probabilities are model estimates, not certainties. Use the graph to inspect evidence and uncertainty; do not treat it as a guarantee."
    }

@app.get("/api/match/{match_id}/result")
async def match_result(match_id:str):
    """Return final score/result when the selected match has completed."""
    if match_id.startswith("espn-"):
        try:
            data=await football.espn_event_details(match_id)
            header=data.get("header") if isinstance(data.get("header"),dict) else {}
            comps=header.get("competitions") if isinstance(header.get("competitions"),list) else []
            comp=comps[0] if comps and isinstance(comps[0],dict) else {}
            competitors=comp.get("competitors") if isinstance(comp.get("competitors"),list) else []
            home=next((x for x in competitors if isinstance(x,dict) and x.get("homeAway")=="home"),None)
            away=next((x for x in competitors if isinstance(x,dict) and x.get("homeAway")=="away"),None)
            def score(x):
                if not isinstance(x,dict): return None
                try:return int(float(x.get("score")))
                except(TypeError,ValueError):return None
            hs,as_=score(home),score(away)
            status_obj=comp.get("status") if isinstance(comp.get("status"),dict) else {}
            status_type=status_obj.get("type") if isinstance(status_obj.get("type"),dict) else {}
            if hs is None or as_ is None:
                return {"event_id":match_id,"completed":False,"status":status_type.get("description") or "Not finished"}
            return {"event_id":match_id,"completed":bool(status_type.get("completed",False)),"status":status_type.get("description") or "Final","home_score":hs,"away_score":as_,"result":"HOME" if hs>as_ else "DRAW" if hs==as_ else "AWAY"}
        except Exception as exc:
            return {"event_id":match_id,"completed":False,"error":"Result unavailable","detail":str(exc)}
    if str(match_id).isdigit():
        try:
            data=await football.fixture(int(match_id))
            e=(data.get("events") or [None])[0]
            if not e:return {"event_id":match_id,"completed":False,"status":"Not found"}
            try: hs=int(float(e.get("intHomeScore"))); as_=int(float(e.get("intAwayScore")))
            except(TypeError,ValueError): return {"event_id":match_id,"completed":False,"status":e.get("strStatus") or "Not finished"}
            return {"event_id":match_id,"completed":True,"status":e.get("strStatus") or "Final","home_score":hs,"away_score":as_,"result":"HOME" if hs>as_ else "DRAW" if hs==as_ else "AWAY"}
        except Exception as exc:
            return {"event_id":match_id,"completed":False,"error":"Result unavailable","detail":str(exc)}
    return {"event_id":match_id,"completed":False,"error":"Unsupported match id"}

@app.get("/api/match/{match_id}/details")
async def match_details(match_id:str):
    if match_id.startswith("espn-"):
        try:
            data=await football.espn_event_details(match_id)
            header=data.get("header") or {}; comp=(header.get("competitions") or [{}])[0]
            return {"source":"ESPN","event_id":match_id,"competition":((comp.get("league") or {}).get("name") or ""),"season":((header.get("season") or {}).get("displayName") or (header.get("season") or {}).get("year") or ""),"week":((header.get("week") or {}).get("number") if isinstance(header.get("week"),dict) else header.get("week")),"status":((comp.get("status") or {}).get("type") or {}).get("description"),"venue":((comp.get("venue") or {}).get("fullName") or ""),"notes":[n.get("headline") or n.get("text") for n in (data.get("notes") or []) if isinstance(n,dict)],"standings":data.get("standings") or []}
        except Exception as exc:
            return {"error":"Match details unavailable","event_id":match_id,"detail":str(exc)}
    try:
        data=await football.fixture(int(match_id))
        return {"source":"TheSportsDB","event_id":match_id,"events":data.get("events") or []}
    except Exception as exc:
        return {"error":"Match details unavailable","event_id":match_id,"detail":str(exc)}

@app.get("/api/fixture/{fixture_id}")
async def get_fixture(fixture_id:int):return await football.fixture(fixture_id)
@app.get("/docs-info")
async def docs_info():return {"swagger":"/docs","health":"/health","live":"/api/live","fixtures":"/api/fixtures/today","predictions":"/api/predictions/today","scanner":"/api/scan/today","provider":"TheSportsDB","odds_provider":"The Odds API"}
