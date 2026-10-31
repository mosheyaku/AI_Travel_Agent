from datetime import datetime
from app.google_places import OpeningHoursPeriod
from app.opening_hours_validation import is_within_opening_hours, find_next_opening_slot


def make_period(open_day, open_hour, close_day, close_hour):
    return OpeningHoursPeriod.model_validate(
        {
            "open": {"day": open_day, "hour": open_hour},
            "close": {"day": close_day, "hour": close_hour},
        }
    )


def test_visit_within_opening_hours():
    periods = [make_period(2, 9, 2, 17)]

    assert is_within_opening_hours(
        datetime(2026, 12, 15, 10),
        datetime(2026, 12, 15, 12),
        periods,
    )


def test_visit_after_closing():
    periods = [make_period(2, 9, 2, 17)]

    assert not is_within_opening_hours(
        datetime(2026, 12, 15, 16),
        datetime(2026, 12, 15, 18),
        periods,
    )


def test_overnight_opening_hours():
    periods = [make_period(5, 20, 6, 2)]

    assert is_within_opening_hours(
        datetime(2026, 12, 18, 23),
        datetime(2026, 12, 19, 1),
        periods,
    )


def test_always_open():
    periods = [
        OpeningHoursPeriod.model_validate(
            {
                "open": {"day": 0, "hour": 0},
            }
        )
    ]

    assert is_within_opening_hours(
        datetime(2026, 12, 15, 9),
        datetime(2026, 12, 15, 17),
        periods,
    )


def test_find_next_opening_slot_when_place_opens_later():
    # Tuesday, December 15, 2026
    periods = [make_period(2, 11, 2, 17)]

    result = find_next_opening_slot(
        datetime(2026, 12, 15, 9),
        90,
        periods,
    )

    assert result == datetime(2026, 12, 15, 11)


def test_find_next_opening_slot_with_split_hours():
    periods = [
        make_period(2, 9, 2, 12),
        make_period(2, 14, 2, 18),
    ]

    result = find_next_opening_slot(
        datetime(2026, 12, 15, 11),
        120,
        periods,
    )

    assert result == datetime(2026, 12, 15, 14)


def test_find_next_opening_slot_when_no_slot_exists():
    periods = [make_period(2, 9, 2, 12)]

    result = find_next_opening_slot(
        datetime(2026, 12, 15, 11),
        240,
        periods,
    )

    assert result is None


def test_find_next_opening_slot_when_closed():
    result = find_next_opening_slot(
        datetime(2026, 12, 15, 9),
        90,
        [],
    )

    assert result is None
