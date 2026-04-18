from app.services.scoring import calculate_risk_score


def test_risk_score_bounds():
    assert calculate_risk_score(-10) == 0.0
    assert calculate_risk_score(1000) == 100.0
