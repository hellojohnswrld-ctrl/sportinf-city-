def implied_probability(decimal_odds: float) -> float:
    if decimal_odds <= 1:
        raise ValueError("Decimal odds must be greater than 1.")
    return 1.0 / decimal_odds

def edge(model_probability: float, decimal_odds: float) -> float:
    return model_probability - implied_probability(decimal_odds)

def baseline(home_ppg: float, away_ppg: float, home_gd: float, away_gd: float, odds=None):
    # Transparent baseline, deliberately conservative. Replace/augment with trained models later.
    strength_home = home_ppg + 0.08 * home_gd + 0.25
    strength_away = away_ppg + 0.08 * away_gd
    total = max(strength_home + strength_away, 0.01)
    home = min(max(strength_home / total * 0.72, 0.05), 0.85)
    away = min(max(strength_away / total * 0.72, 0.05), 0.80)
    draw = max(1.0 - home - away, 0.05)
    s = home + draw + away
    probs = {"home": home/s, "draw": draw/s, "away": away/s}
    result = {
        "home_probability": round(probs["home"], 4),
        "draw_probability": round(probs["draw"], 4),
        "away_probability": round(probs["away"], 4),
        "confidence": "HIGH" if max(probs.values()) >= .62 else "MEDIUM" if max(probs.values()) >= .50 else "LOW",
        "reasons": [
            "Home advantage included.",
            "Recent points-per-game and goal-difference inputs included.",
            "This is a baseline model; it must be backtested before real-money use."
        ]
    }
    if odds:
        result["edges"] = {k: round(edge(probs[k], float(v)), 4) for k, v in odds.items() if v}
    return result
