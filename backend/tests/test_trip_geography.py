from app.schemas import TravelItinerary
from app.trip_generator import find_geographic_issues


def test_detects_distant_activities_on_same_day():
    trip = TravelItinerary.model_validate({
        "destination": "Chiang Mai",
        "days": [{
            "day": 1,
            "activities": [
                {
                    "name": "Park A",
                    "activity_type": "nature_park",
                    "description": "Nature park",
                    "source_indices": [1],
                    "location_status": "verified",
                    "latitude": 19.1767,
                    "longitude": 99.0319,
                    "google_place_id": "park-a",
                },
                {
                    "name": "Mountain B",
                    "activity_type": "hiking",
                    "description": "Mountain park",
                    "source_indices": [2],
                    "location_status": "verified",
                    "latitude": 18.5356,
                    "longitude": 98.5221,
                    "google_place_id": "mountain-b",
                },
            ],
        }],
    })

    issues = find_geographic_issues(trip)

    assert len(issues) == 1
    assert "Day 1" in issues[0]


def test_accepts_nearby_activities():
    trip = TravelItinerary.model_validate({
        "destination": "Chiang Mai",
        "days": [{
            "day": 1,
            "activities": [
                {
                    "name": "Park A",
                    "activity_type": "nature_park",
                    "description": "Nature park",
                    "source_indices": [1],
                    "location_status": "verified",
                    "latitude": 19.1767,
                    "longitude": 99.0319,
                    "google_place_id": "park-a",
                },
                {
                    "name": "Dam B",
                    "activity_type": "other",
                    "description": "Nearby dam",
                    "source_indices": [2],
                    "location_status": "verified",
                    "latitude": 19.1741,
                    "longitude": 99.0307,
                    "google_place_id": "dam-b",
                },
            ],
        }],
    })

    assert find_geographic_issues(trip) == []