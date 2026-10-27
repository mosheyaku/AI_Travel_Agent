from app.place_matching import is_suspicious_activity_location, names_match, is_likely_office, names_match_or_alias

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


def test_matches_known_grand_canyon_alias():
    assert names_match_or_alias(
        "Grand Canyon Chiang Mai",
        "Grand Canyon Water Park",
    )


def test_matches_known_sticky_waterfall_alias():
    assert names_match_or_alias(
        "Sticky Waterfall",
        "Buatong Waterfall-Chet Si Fountain National Park",
    )


def test_rejects_unapproved_cave_match():
    assert not names_match_or_alias(
        "Chiang Dao Caves",
        "Chiang Dao Cave",
    )


def test_flags_suspicious_zipline_location():
    assert is_suspicious_activity_location(
        "Eagle Track Zipline",
        "adventure",
        1.6,
    )


def test_flags_suspicious_elephant_sanctuary_location():
    assert is_suspicious_activity_location(
        "Chiang Mai Elephant Sanctuary",
        "wildlife",
        0.5,
    )


def test_accepts_distant_elephant_park():
    assert not is_suspicious_activity_location(
        "Elephant Nature Park",
        "wildlife",
        49.5,
    )


def test_does_not_flag_urban_cultural_attraction():
    assert not is_suspicious_activity_location(
        "City Museum",
        "culture",
        0.5,
    )