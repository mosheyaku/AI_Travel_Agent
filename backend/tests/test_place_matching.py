from app.place_matching import names_match


def test_names_match_ignores_case():
    assert names_match("Elephant Nature Park", "elephant nature park")


def test_names_match_ignores_punctuation():
    assert names_match("Doi Suthep-Pui", "Doi Suthep Pui")


def test_names_match_rejects_different_places():
    assert not names_match(
        "Pongyang Adventure Park",
        "Pong Yang Jungle Coaster & Zipline",
    )
