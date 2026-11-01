from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.recommendations import recommend_attractions
from app.schemas import TravelItinerary, TravelPreferences
from app.trip_generator import (
    MAX_GENERATION_ATTEMPTS,
    build_trip_prompt,
    enrich_trip_plan,
    evaluate_trip_candidate,
    find_driving_issues,
    find_planning_issues,
    find_total_driving_issues,
    resolve_trip_origin,
    generate_trip_candidate,
    repair_trip_plan,
    total_driving_excess_minutes,
    total_trip_driving_minutes,
)
from app.itinerary_routes import add_total_driving_routes
from app.location_validation import LocationStatus
from app.trip_planning import (
    build_attraction_queries,
    get_attraction_search_limit,
)
from app.itinerary_schedule import add_itinerary_schedule, add_itinerary_dates
from app.opening_hours_validation import validate_itinerary_opening_hours
from app.schedule_repair import (
    repair_opening_hours_conflicts,
    count_opening_hours_conflicts,
    count_timing_conflicts,
)


class TravelState(TypedDict, total=False):
    preferences: TravelPreferences
    recommendations: list[dict]
    sources: list[dict]
    prompt: str
    candidate: TravelItinerary | None
    trip: dict
    issues: list[str]
    attempts: int
    fallback: TravelItinerary | None
    last_error: str


async def recommend_node(state: TravelState) -> dict:
    """Search for and verify attractions."""
    preferences = state["preferences"]

    result = await recommend_attractions(
        build_attraction_queries(preferences),
        destination=preferences.destination,
        max_attractions=get_attraction_search_limit(preferences),
    )

    recommendations = [
        item
        for item in result["recommendations"]
        if item.get("location_status") == LocationStatus.VERIFIED
        and item.get("latitude") is not None
        and item.get("longitude") is not None
        and item.get("google_place_id")
    ]

    if not recommendations:
        raise ValueError("No attractions with verified locations are available.")

    return {
        "recommendations": recommendations,
        "sources": result["sources"],
        "prompt": build_trip_prompt(preferences, recommendations),
        "attempts": 0,
    }


async def generate_node(state: TravelState) -> dict:
    """Generate one itinerary candidate."""
    attempts = state["attempts"] + 1

    try:
        candidate = await generate_trip_candidate(
            state["prompt"],
            state["preferences"],
            state["recommendations"],
        )
    except ValueError as exc:
        return {
            "attempts": attempts,
            "candidate": None,
            "issues": [str(exc)],
            "last_error": str(exc),
        }

    return {
        "attempts": attempts,
        "candidate": candidate,
        "issues": [],
        "last_error": "",
    }


async def evaluate_node(state: TravelState) -> dict:
    """Evaluate the candidate and retain useful fallback plans."""
    candidate = state["candidate"]

    if candidate is None:
        return {"issues": state["issues"]}

    issues = await evaluate_trip_candidate(
        candidate,
        state["preferences"],
    )

    updates = {"issues": issues}

    if not issues:
        updates["trip"] = candidate.model_dump()
        return updates

    planning_issues = find_planning_issues(
        candidate,
        state["preferences"].pace,
    )

    if (
        not planning_issues
        and not find_driving_issues(candidate)
        and find_total_driving_issues(candidate)
    ):
        previous = state.get("fallback")

        score = (
            total_driving_excess_minutes(candidate),
            total_trip_driving_minutes(candidate),
        )

        if previous is None or score < (
            total_driving_excess_minutes(previous),
            total_trip_driving_minutes(previous),
        ):
            updates["fallback"] = candidate.model_copy(deep=True)

    return updates


def decide_next(state: TravelState) -> Literal["finish", "retry", "repair"]:
    """Choose the next action based on validation results."""
    if state.get("trip") is not None:
        return "finish"

    if state["attempts"] < MAX_GENERATION_ATTEMPTS:
        return "retry"

    return "repair"


def append_feedback_node(state: TravelState) -> dict:
    """Include validation feedback in the next generation prompt."""
    issues = state.get("issues", [])

    feedback = "\n".join(issues) or "The itinerary was invalid."

    return {
        "prompt": (
            state["prompt"]
            + "\n\nThe previous itinerary had planning problems:\n"
            + feedback
            + "\nGenerate a corrected itinerary."
            + "\nFix the reported problems by changing the selected attractions, "
            + "their grouping, or their order as needed."
            + "\nDo not introduce repetitive experiences just to fill a day."
            + "\nUse only the provided attractions and preserve their "
            + "source indices."
            + "\nReturn the complete corrected JSON itinerary."
        )
    }


async def optimize_node(state: TravelState) -> dict:
    """Enrich a validated itinerary before scheduling."""
    trip = TravelItinerary.model_validate(state["trip"])

    enriched = await enrich_trip_plan(
        trip,
        state["preferences"],
        state["recommendations"],
    )

    return {"trip": enriched.model_dump(mode="json")}


async def schedule_node(state: TravelState) -> dict:
    """Add dates, accommodation travel times, and opening-hours validation."""
    trip = TravelItinerary.model_validate(state["trip"])
    preferences = state["preferences"]

    add_itinerary_dates(trip, preferences.start_date)

    origin = await resolve_trip_origin(preferences)

    await add_itinerary_schedule(
        trip,
        origin=origin,
    )

    await validate_itinerary_opening_hours(trip)

    trip = await repair_opening_hours_conflicts(
        trip,
        origin=origin,
    )

    # Some attractions close too early for a 09:00 departure. Try an
    # earlier day start before accepting a schedule with known conflicts.
    if count_opening_hours_conflicts(trip):
        earlier = TravelItinerary.model_validate(state["trip"])
        add_itinerary_dates(earlier, preferences.start_date)
        await add_itinerary_schedule(earlier, start_time="08:00", origin=origin)
        await validate_itinerary_opening_hours(earlier)
        earlier = await repair_opening_hours_conflicts(earlier, origin=origin)
        if count_opening_hours_conflicts(earlier) < count_opening_hours_conflicts(trip):
            trip = earlier

    remaining_conflicts = [
        f"Day {day.day}: {activity.name}"
        for day in trip.days
        for activity in day.activities
        if activity.opening_hours_status == "conflict"
    ]

    if remaining_conflicts:
        raise ValueError(
            "Could not create an itinerary without opening-hours "
            "conflicts: " + "; ".join(remaining_conflicts)
        )

    timing_conflicts = [
        f"Day {day.day}: {activity.name}"
        for day in trip.days
        for activity in day.activities
        if activity.timing_status == "conflict"
    ]

    if timing_conflicts:
        raise ValueError(
            "Could not schedule activities within their experience windows: "
            + "; ".join(timing_conflicts)
        )

    return {"trip": trip.model_dump(mode="json")}


async def repair_node(state: TravelState) -> dict:
    """Repair the final candidate or return the best soft fallback."""
    fallback = state.get("fallback")

    if fallback is not None:
        return {"trip": fallback.model_dump()}

    candidate = state.get("candidate")

    if candidate is None:
        raise ValueError("The model returned no valid itinerary after retries.")

    repaired = await repair_trip_plan(
        candidate,
        state["preferences"],
        state["recommendations"],
    )

    if repaired is None:
        raise ValueError(
            "The trip plan failed route validation: "
            + "; ".join(state.get("issues", []))
        )

    origin = await resolve_trip_origin(state["preferences"])

    if origin is not None:
        repaired = await add_total_driving_routes(
            repaired,
            origin_latitude=origin[0],
            origin_longitude=origin[1],
        )

    return {"trip": repaired.model_dump()}


builder = StateGraph(TravelState)

builder.add_node("recommend", recommend_node)
builder.add_node("generate", generate_node)
builder.add_node("evaluate", evaluate_node)
builder.add_node("feedback", append_feedback_node)
builder.add_node("repair", repair_node)
builder.add_node("schedule", schedule_node)
builder.add_node("optimize", optimize_node)

builder.add_edge(START, "recommend")
builder.add_edge("recommend", "generate")
builder.add_edge("generate", "evaluate")

builder.add_conditional_edges(
    "evaluate",
    decide_next,
    {
        "finish": "optimize",
        "retry": "feedback",
        "repair": "repair",
    },
)

builder.add_edge("feedback", "generate")
builder.add_edge("repair", "optimize")
builder.add_edge("optimize", "schedule")
builder.add_edge("schedule", END)

travel_graph = builder.compile()
