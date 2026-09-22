import math

def implied_probability(decimal_odds: float) -> float:
    if decimal_odds <= 1:
        raise ValueError("Decimal odds must be greater than 1.")
    return 1.0 / decimal_odds

def edge(model_probability: float, decimal_odds: float) -> float:
    return model_probability - implied_probability(decimal_odds)

def _poisson(k, lam):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def _poisson_1x2(home_xg, away_xg, max_goals=7):
    home=draw=away=0.0
    for h in range(max_goals):
        for a in range(max_goals):
            p=_poisson(h,home_xg)*_poisson(a,away_xg)
            if h>a: home+=p
            elif h==a: draw+=p
            else: away+=p
    total=home+draw+away
    return {"home":home/total,"draw":draw/total,"away":away/total}

def advanced_model(home_ppg, away_ppg, home_gd, away_gd,
                   home_gf=1.4, home_ga=1.4, away_gf=1.2, away_ga=1.4,
                   sample_home=0, sample_away=0, market=None):
    """
    Form + goal-rate Poisson model. Uses goals for/against, points rate,
    goal difference and home advantage. If bookmaker probabilities exist,
    a small market-calibration weight is applied to reduce overconfidence.
    """
    home_xg=(0.55*home_gf + 0.45*away_ga) + 0.18
    away_xg=(0.55*away_gf + 0.45*home_ga)
    strength_delta=(home_ppg-away_ppg)*0.12 + (home_gd-away_gd)*0.025
    home_xg=max(0.20,home_xg + strength_delta)
    away_xg=max(0.15,away_xg - strength_delta*0.45)
    probs=_poisson_1x2(home_xg,away_xg)
    model_probs=probs.copy()

    if market:
        market_clean={k:float(v) for k,v in market.items() if k in probs and float(v)>0}
        z=sum(market_clean.values())
        if z:
            market_clean={k:v/z for k,v in market_clean.items()}
            weight=0.20
            for k in probs:
                if k in market_clean:
                    probs[k]=(1-weight)*probs[k]+weight*market_clean[k]
            z=sum(probs.values()); probs={k:v/z for k,v in probs.items()}

    n=min(sample_home,sample_away)
    confidence="LOW" if n<4 else "MEDIUM" if n<8 else "HIGH" if max(probs.values())>=0.58 else "MEDIUM"
    return {
        "home_probability":round(probs["home"],4),
        "draw_probability":round(probs["draw"],4),
        "away_probability":round(probs["away"],4),
        "confidence":confidence,
        "expected_goals":{"home":round(home_xg,2),"away":round(away_xg,2)},
        "model_inputs":{
            "home_ppg":round(home_ppg,3),"away_ppg":round(away_ppg,3),
            "home_gd":round(home_gd,3),"away_gd":round(away_gd,3),
            "home_gf":round(home_gf,3),"home_ga":round(home_ga,3),
            "away_gf":round(away_gf,3),"away_ga":round(away_ga,3),
            "sample_home":sample_home,"sample_away":sample_away
        },
        "reasons":[
            "Recent goals for/against included.",
            "Points-per-game and goal difference included.",
            "Home advantage included.",
            "Poisson scoreline model used.",
            "Small market calibration applied only when bookmaker probabilities are available.",
            "Model should be backtested before real-money use."
        ]
    }

def baseline(home_ppg, away_ppg, home_gd, away_gd, odds=None):
    return advanced_model(home_ppg,away_ppg,home_gd,away_gd)
