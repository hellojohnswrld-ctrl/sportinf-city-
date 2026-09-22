import httpx
from backend.config import ODDS_API_KEY,ODDS_API_REGION,ODDS_API_SPORT
BASE="https://api.the-odds-api.com/v4"
def _norm(v):return "".join(ch.lower() for ch in (v or "") if ch.isalnum())
async def fetch_sports():
    if not ODDS_API_KEY:return []
    async with httpx.AsyncClient(timeout=15) as c:
        r=await c.get(f"{BASE}/sports",params={"apiKey":ODDS_API_KEY});r.raise_for_status();return r.json()
async def fetch_odds(sport=ODDS_API_SPORT,region=ODDS_API_REGION):
    if not ODDS_API_KEY:return []
    p={"apiKey":ODDS_API_KEY,"regions":region,"markets":"h2h,btts,draw_no_bet","oddsFormat":"decimal","includeLinks":"true"}
    async with httpx.AsyncClient(timeout=20) as c:
        r=await c.get(f"{BASE}/sports/{sport}/odds",params=p);r.raise_for_status();return r.json()
async def fetch_all_soccer_odds(region=ODDS_API_REGION):
    sports=await fetch_sports(); soccer=[s for s in sports if str(s.get("group","")).lower().startswith("soccer") and s.get("active")]; results=[]
    for s in soccer:
        try:results.extend(await fetch_odds(s.get("key"),region))
        except Exception:continue
    return soccer,results
def match_odds(events,odds_events):
    output={}
    for game in odds_events or []:
        home,away=_norm(game.get("home_team")),_norm(game.get("away_team"))
        if not home or not away:continue
        best={};books={};links={};markets=set()
        for book in game.get("bookmakers") or []:
            title=book.get("title") or book.get("key") or "Bookmaker"
            for market in book.get("markets",[]):
                mk=market.get("key");markets.add(mk)
                for out in market.get("outcomes",[]):
                    name=out.get("name");price=out.get("price")
                    try:price=float(price)
                    except(TypeError,ValueError):continue
                    key="home" if _norm(name)==home else "away" if _norm(name)==away else "draw" if _norm(name)=="draw" else None
                    if mk=="h2h" and key and price>1 and (key not in best or price>best[key]):
                        best[key]=price;books[key]=title
                        if out.get("link"):links[key]=out["link"]
        if len(best)>=2:output[(home,away)]={"bookmaker":books,"odds":best,"links":links,"markets":sorted(markets),"source":"The Odds API","sport_key":game.get("sport_key"),"sport_title":game.get("sport_title"),"commence_time":game.get("commence_time")}
    return output
def value_layer(prediction,odds):
    if not odds:return None
    model={"home":float(prediction.get("home_probability",0)),"draw":float(prediction.get("draw_probability",0)),"away":float(prediction.get("away_probability",0))};values={}
    for key,price in odds.get("odds",{}).items():
        implied=1/price;edge=model[key]-implied;ev=model[key]*price-1
        values[key]={"odds":round(price,3),"implied_probability":round(implied,4),"model_probability":round(model[key],4),"edge":round(edge,4),"expected_value":round(ev,4),"value":ev>0}
    return values
def analysis_layer(prediction,value):
    if not value:return {"signal":"NO_ODDS","score":0,"reasons":["No bookmaker odds available."]}
    k,v=max(value.items(),key=lambda kv:kv[1].get("expected_value",0));ev=v["expected_value"];score=max(0,min(100,50+v["edge"]*1000+max(0,v["model_probability"]-.5)*100))
    return {"signal":"POSITIVE_VALUE" if ev>0 else "NO_VALUE","selection":k,"score":round(score,1),"confidence":prediction.get("confidence","LOW"),"reasons":[f"Model {v['model_probability']:.1%} vs implied {v['implied_probability']:.1%}.",f"Edge {v['edge']:+.1%}; expected value {ev:+.1%}.",f"Best price {v['odds']:.2f}."]}
