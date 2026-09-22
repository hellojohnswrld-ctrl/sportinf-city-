from backend.prediction_engine.football_model import baseline, implied_probability, edge

def test_probs_sum_to_one():
    p = baseline(1.7, 1.2, .5, -.2)
    total = p["home_probability"] + p["draw_probability"] + p["away_probability"]
    assert abs(total - 1) < 0.01

def test_implied_probability():
    assert abs(implied_probability(2.0) - .5) < 1e-9

def test_positive_edge():
    assert edge(.60, 2.0) > 0
