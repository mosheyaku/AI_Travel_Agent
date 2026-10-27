from app.place_matching import names_match, is_likely_office

def test_names_match_ignores_case():
    assert names_match("Elephant Nature Park", "elephant nature park")


def test_names_match_ignores_punctuation():
    assert names_match("Doi Suthep-Pui", "Doi Suthep Pui")


def test_names_match_rejects_different_places():
    assert not names_match(
        "Pongyang Adventure Park",
        "Pong Yang Jungle Coaster & Zipline",
    )

def test_identifies_travel_agency_as_office():
    assert is_likely_office(
        ["tour_agency", "travel_agency", "point_of_interest"]
    )


def test_does_not_classify_nature_preserve_as_office():
    assert not is_likely_office(
        ["wildlife_refuge", "nature_preserve", "park"]
    )