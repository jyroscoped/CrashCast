from app.services.anti_gaming import haversine_meters, validate_reporter_proximity


def test_haversine_zero_distance():
    assert haversine_meters(40.0, -79.0, 40.0, -79.0) == 0.0


def test_proximity_validation_true_for_nearby_points():
    assert validate_reporter_proximity(40.4406, -79.9959, 40.4408, -79.9957)
