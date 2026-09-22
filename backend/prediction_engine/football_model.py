import math

def implied_probability(decimal_odds: float) -> float:
    if decimal_odds <= 1:
        raise ValueError("Decimal odds must be greater than 1.")
    return 1.0 / decimal_odds

def edge(model_probability: float, decimal_odds: float) -> float:
    return model_probability - implied_probability(decimal_odds)

def _poisson(k, lam):
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def _poisson_1x2(home_xg, away_xg, max_goals=8):
    home = draw = away = 0.0
    for h in range(max_goals):
        for a in range(max_goals):
            p = _poisson(h, home_xg) * _poisson(a, away_xg)
            if h > a:
                home += p
            elif h == a:
                draw += p
            else:
                away += p
    total = home + draw + away
    return {"home": home / total, "draw": draw / total, "away": away / total}

def advanced_model(
    home_ppg, away_ppg, home_gd, away_gd,
    home_gf=1.4, home_ga=1.4, away_gf=1.2, away_ga=1.4,
    sample_home=0, sample_away=0, market=None,
):
    """
    Conservative football probability model.

    Uses recent points rate, goal difference and scoring/conceding rates,
    with sample-size shrinkage and optional market calibration. The model
    deliberately avoids presenting probability as certainty.
    """
    n_home = max(0, int(sample_home or 0))
    n_away = max(0, int(sample_away or 0))

    # Shrink tiny samples toward league-neutral rates instead of allowing
    # one or two unusual results to dominate the forecast.
    home_weight = min(1.0, n_home / 8.0)
    away_weight = min(1.0, n_away / 8.0)
    home_ppg = 1.5 + (float(home_ppg) - 1.5) * home_weight
    away_ppg = 1.5 + (float(away_ppg) - 1.5) * away_weight
    home_gf = 1.45 + (float(home_gf) - 1.45) * home_weight
    home_ga = 1.45 + (float(home_ga) - 1.45) * home_weight
    away_gf = 1.20 + (float(away_gf) - 1.20) * away_weight
    away_ga = 1.45 + (float(away_ga) - 1.45) * away_weight
    home_gd = float(home_gd) * home_weight
    away_gd = float(away_gd) * away_weight

    home_xg = 0.55 * home_gf + 0.45 * away_ga + 0.18
    away_xg = 0.55 * away_gf + 0.45 * home_ga

    strength_delta = (home_ppg - away_ppg) * 0.12 + (home_gd - away_gd) * 0.025
    home_xg = max(0.20, home_xg + strength_delta)
    away_xg = max(0.15, away_xg - strength_delta * 0.45)

    probs = _poisson_1x2(home_xg, away_xg)

    # Only use a market as a modest calibration signal when explicitly supplied.
    if market:
        clean = {k: float(v) for k, v in market.items() if k in probs and float(v) > 0}
        z = sum(clean.values())
        if z:
            clean = {k: v / z for k, v in clean.items()}
            weight = 0.15
            for k in probs:
                if k in clean:
                    probs[k] = (1 - weight) * probs[k] + weight * clean[k]
            z = sum(probs.values())
            probs = {k: v / z for k, v in probs.items()}

    n = min(n_home, n_away)
    top = max(probs.values())
    if n < 3:
        confidence = "LOW"
    elif n < 6:
        confidence = "MEDIUM"
    elif top >= 0.62:
        confidence = "HIGH"
    else:
        confidence = "MEDIUM"

    return {
        "home_probability": round(probs["home"], 4),
        "draw_probability": round(probs["draw"], 4),
        "away_probability": round(probs["away"], 4),
        "confidence": confidence,
        "expected_goals": {"home": round(home_xg, 2), "away": round(away_xg, 2)},
        "model_inputs": {
            "home_ppg": round(home_ppg, 3), "away_ppg": round(away_ppg, 3),
            "home_gd": round(home_gd, 3), "away_gd": round(away_gd, 3),
            "home_gf": round(home_gf, 3), "home_ga": round(home_ga, 3),
            "away_gf": round(away_gf, 3), "away_ga": round(away_ga, 3),
            "sample_home": n_home, "sample_away": n_away,
        },
        "reasons": [
            "Recent scoring and conceding rates included.",
            "Points-per-game and goal difference included.",
            "Home advantage included.",
            "Poisson scoreline distribution used.",
            "Small samples are shrunk toward neutral rates.",
            "Probabilities are estimates and should be backtested and calibrated over time.",
        ],
    }

def baseline(home_ppg, away_ppg, home_gd, away_gd, odds=None, **kwargs):
    return advanced_model(
        home_ppg, away_ppg, home_gd, away_gd, market=kwargs.get("market"), 
        home_gf=kwargs.get("home_gf", 1.4), home_ga=kwargs.get("home_ga", 1.4),
        away_gf=kwargs.get("away_gf", 1.2), away_ga=kwargs.get("away_ga", 1.4),
        sample_home=kwargs.get("sample_home", 0), sample_away=kwargs.get("sample_away", 0),
    )
