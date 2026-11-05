import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.recommendations import recommend_attractions, merge_recommendation_results
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
    remove_unschedulable_activities,
    count_opening_hours_conflicts,
    count_timing_conflicts,
    fill_empty_days,
)
from datetime import date, timedelta


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
    base_trip: dict
    candidates: list[TravelItinerary]


def get_verified_attractions(result: dict) -> list[dict]:
    """Return recommendations with verified physical locations."""
    return [
        item
        for item in result["recommendations"]
        if item.get("location_status") == LocationStatus.VERIFIED
        and item.get("latitude") is not None
        and item.get("longitude") is not None
        and item.get("google_place_id")
    ]


def get_missing_interests(
    preferences: TravelPreferences,
    recommendations: list[dict],
) -> list[str]:
    """Find requested interests without verified recommendations."""
    covered = {item["category"] for item in recommendations if item.get("category")}

    return [
        interest
        for interest in dict.fromkeys(preferences.interests)
        if interest not in covered
    ]


def needs_additional_search(
    preferences: TravelPreferences,
    recommendations: list[dict],
) -> bool:
    """Determine whether attraction coverage needs expansion."""
    minimum_attractions = min(
        preferences.duration_days * 2,
        get_attraction_search_limit(preferences),
    )

    return len(recommendations) < minimum_attractions or bool(
        get_missing_interests(preferences, recommendations)
    )


async def recommend_node(state: TravelState) -> dict:
    """Discover verified attractions and expand insufficient coverage."""
    preferences = state["preferences"]
    search_limit = get_attraction_search_limit(preferences)

    result = await recommend_attractions(
        build_attraction_queries(preferences),
        destination=preferences.destination,
        max_attractions=search_limit,
    )

    recommendations = get_verified_attractions(result)

    logger.info(
        "Initial attraction discovery: %d candidates, %d verified",
        len(result["recommendations"]),
        len(recommendations),
    )

    if needs_additional_search(preferences, recommendations):
        missing_interests = get_missing_interests(
            preferences,
            recommendations,
        )

        if missing_interests:
            additional_queries = [
                (
                    f"Specific named {interest} attractions and activities "
                    f"in {preferences.destination}, including lesser-known places"
                )
                for interest in missing_interests
            ]
        else:
            additional_queries = [
                (
                    f"Unique named attractions and activities in "
                    f"{preferences.destination} beyond the most popular sites"
                )
            ]

        try:
            additional_result = await recommend_attractions(
                additional_queries,
                destination=preferences.destination,
                max_attractions=search_limit,
            )

            additional_result = {
                **additional_result,
                "recommendations": get_verified_attractions(additional_result),
            }

            result = merge_recommendation_results(
                {
                    **result,
                    "recommendations": recommendations,
                },
                additional_result,
            )

            recommendations = get_verified_attractions(result)

            logger.info(
                "Expanded attraction discovery: %d verified attractions",
                len(recommendations),
            )

        except (ValueError, TimeoutError) as exc:
            if not recommendations:
                raise

            logger.warning(
                "Additional attraction search failed; preserving "
                "%d verified attractions: %s",
                len(recommendations),
                exc,
            )

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
    """Evaluate a candidate and retain invalid plans for possible repair."""
    candidate = state.get("candidate")

    if candidate is None:
        return {"issues": state.get("issues", [])}

    issues = await evaluate_trip_candidate(
        candidate,
        state["preferences"],
    )

    if not issues:
        return {
            "issues": [],
            "trip": candidate.model_dump(mode="json"),
        }

    candidates = list(state.get("candidates", []))
    candidates.append(candidate.model_copy(deep=True))

    logger.info(
        "Itinerary attempt %d failed with %d issues: %s",
        state["attempts"],
        len(issues),
        "; ".join(issues),
    )

    return {
        "issues": issues,
        "candidates": candidates,
    }


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
    """Enrich a valid itinerary without introducing planning violations."""
    trip = TravelItinerary.model_validate(state["trip"])
    base_trip = trip.model_dump(mode="json")

    base_issues = await evaluate_trip_candidate(
        trip,
        state["preferences"],
    )

    if base_issues:
        raise ValueError(
            "The base itinerary violates planning constraints: "
            + "; ".join(base_issues)
        )

    try:
        enriched = await enrich_trip_plan(
            trip.model_copy(deep=True),
            state["preferences"],
            state["recommendations"],
        )

        enriched_issues = await evaluate_trip_candidate(
            enriched,
            state["preferences"],
        )

        if enriched_issues:
            logger.warning(
                "Itinerary enrichment introduced planning issues: %s",
                "; ".join(enriched_issues),
            )
            return {
                "base_trip": base_trip,
                "trip": trip.model_dump(mode="json"),
            }

    except ValueError as exc:
        logger.warning(
            "Itinerary enrichment failed; using base candidate: %s",
            exc,
        )
        return {
            "base_trip": base_trip,
            "trip": trip.model_dump(mode="json"),
        }

    logger.info(
        "Itinerary optimization: %d activities before, %d after",
        sum(len(day.activities) for day in trip.days),
        sum(len(day.activities) for day in enriched.days),
    )

    return {
        "base_trip": base_trip,
        "trip": enriched.model_dump(mode="json"),
    }


async def _try_schedule_trip_for_date(
    trip_data: dict,
    preferences: TravelPreferences,
) -> TravelItinerary:
    """Schedule one itinerary candidate."""
    trip = TravelItinerary.model_validate(trip_data)
    logger.info(
        "Initial itinerary activity counts: %s",
        [len(day.activities) for day in trip.days],
    )
    selected_start_time = "09:00"

    add_itinerary_dates(trip, preferences.start_date)
    origin = await resolve_trip_origin(preferences)

    await add_itinerary_schedule(trip, start_time=selected_start_time, origin=origin)
    await validate_itinerary_opening_hours(trip)

    trip = await repair_opening_hours_conflicts(
        trip, origin=origin, start_time=selected_start_time
    )

    if count_opening_hours_conflicts(trip) or count_timing_conflicts(trip):
        earlier = TravelItinerary.model_validate(trip_data)
        add_itinerary_dates(earlier, preferences.start_date)

        await add_itinerary_schedule(earlier, start_time="08:00", origin=origin)
        await validate_itinerary_opening_hours(earlier)

        earlier = await repair_opening_hours_conflicts(
            earlier, origin=origin, start_time="08:00"
        )

        if count_opening_hours_conflicts(earlier) + count_timing_conflicts(
            earlier
        ) < count_opening_hours_conflicts(trip) + count_timing_conflicts(trip):
            trip = earlier
            selected_start_time = "08:00"

    if count_opening_hours_conflicts(trip) or count_timing_conflicts(trip):
        trip = await remove_unschedulable_activities(
            trip, origin=origin, start_time=selected_start_time
        )
        logger.info(
            "Activity counts after schedule repair: %s",
            [len(day.activities) for day in trip.days],
        )

    if any(not day.activities for day in trip.days):
        raise ValueError("The itinerary contains empty days.")

    if count_opening_hours_conflicts(trip) or count_timing_conflicts(trip):
        raise ValueError("Unresolved scheduling conflicts.")

    unscheduled_activities = [
        activity.name
        for day in trip.days
        for activity in day.activities
        if (
            activity.start_time is None
            or activity.end_time is None
            or activity.schedule_status == "unknown"
        )
    ]

    if unscheduled_activities:
        raise ValueError(
            "The itinerary contains unscheduled activities: "
            + ", ".join(unscheduled_activities)
        )

    if count_opening_hours_conflicts(trip) or count_timing_conflicts(trip):
        raise ValueError("Unresolved scheduling conflicts.")

    driving_issues = find_driving_issues(trip)

    if driving_issues:
        raise ValueError(
            "The itinerary exceeds driving limits: " + "; ".join(driving_issues)
        )

    total_driving_issues = find_total_driving_issues(trip)

    if total_driving_issues:
        logger.warning(
            "Itinerary exceeds recommended round-trip driving time: %s",
            total_driving_issues,
        )

    logger.info(
        "Final itinerary activity counts: %s",
        [len(day.activities) for day in trip.days],
    )

    return trip


async def try_schedule_trip(
    trip_data: dict,
    preferences: TravelPreferences,
) -> TravelItinerary:
    """Schedule an itinerary using consecutive weekdays."""
    if preferences.start_date is not None:
        return await _try_schedule_trip_for_date(
            trip_data,
            preferences,
        )

    reference_sunday = date(2026, 11, 1)
    errors = []

    for offset in range(7):
        reference_start_date = reference_sunday + timedelta(days=offset)

        candidate_preferences = preferences.model_copy(
            update={"start_date": reference_start_date}
        )

        try:
            trip = await _try_schedule_trip_for_date(
                trip_data,
                candidate_preferences,
            )
        except ValueError as exc:
            errors.append(str(exc))
            continue

        for day in trip.days:
            day.date = None

            for activity in day.activities:
                if activity.opening_hours_status == "verified":
                    activity.opening_hours_status = "unknown"

        return trip

    raise ValueError(
        "Could not schedule the itinerary for any consecutive weekday "
        "combination. Last error: "
        + (errors[-1] if errors else "Unknown scheduling error.")
    )


async def schedule_node(state: TravelState) -> dict:
    """Try the optimized itinerary, then fall back to the base itinerary."""
    preferences = state["preferences"]

    for label, trip_data in (
        ("optimized", state["trip"]),
        ("base", state.get("base_trip")),
    ):
        if trip_data is None:
            continue

        try:
            trip = await try_schedule_trip(trip_data, preferences)

            logger.info("Successfully scheduled %s itinerary", label)
            return {"trip": trip.model_dump(mode="json")}

        except ValueError as exc:
            logger.warning("Scheduling %s itinerary failed: %s", label, exc)

    raise ValueError("Could not schedule either itinerary.")


async def repair_node(state: TravelState) -> dict:
    """Try repairing generated candidates without accepting invalid plans."""
    candidates = list(state.get("candidates", []))

    if not candidates:
        raise ValueError("No valid itinerary candidates are available for repair.")

    preferences = state["preferences"]
    recommendations = state["recommendations"]

    def candidate_score(candidate: TravelItinerary) -> tuple:
        planning_issues = find_planning_issues(candidate, preferences.pace)
        driving_issues = find_driving_issues(candidate)
        total_driving_issues = find_total_driving_issues(candidate)

        return (
            len(planning_issues) + len(driving_issues),
            len(total_driving_issues),
            total_driving_excess_minutes(candidate),
            -sum(len(day.activities) for day in candidate.days),
        )

    candidates.sort(key=candidate_score)

    for index, candidate in enumerate(candidates, start=1):
        logger.info(
            "Repairing itinerary candidate %d/%d",
            index,
            len(candidates),
        )

        repaired = await repair_trip_plan(
            candidate,
            preferences,
            recommendations,
        )

        if repaired is None:
            continue

        issues = await evaluate_trip_candidate(
            repaired,
            preferences,
        )

        if issues:
            logger.warning(
                "Repaired itinerary still has issues: %s",
                "; ".join(issues),
            )
            continue

        return {"trip": repaired.model_dump(mode="json")}

    raise ValueError(
        "None of the generated itineraries could be repaired "
        "within the planning constraints."
    )


def timed_node(name: str, node):
    """Measure and log the execution time of a graph node."""

    @wraps(node)
    async def async_wrapper(state: TravelState) -> dict:
        start = time.perf_counter()

        try:
            return await node(state)
        finally:
            logger.warning(
                "PERFORMANCE | %s | %.2f seconds",
                name,
                time.perf_counter() - start,
            )

    def sync_wrapper(state: TravelState) -> dict:
        start = time.perf_counter()

        try:
            return node(state)
        finally:
            logger.warning(
                "PERFORMANCE | %s | %.2f seconds",
                name,
                time.perf_counter() - start,
            )

    import inspect

    return async_wrapper if inspect.iscoroutinefunction(node) else sync_wrapper


builder = StateGraph(TravelState)

builder.add_node("recommend", timed_node("recommend", recommend_node))
builder.add_node("generate", timed_node("generate", generate_node))
builder.add_node("evaluate", timed_node("evaluate", evaluate_node))
builder.add_node("feedback", timed_node("feedback", append_feedback_node))
builder.add_node("repair", timed_node("repair", repair_node))
builder.add_node("schedule", timed_node("schedule", schedule_node))
builder.add_node("optimize", timed_node("optimize", optimize_node))

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
builder.add_edge("optimize", END)

travel_graph = builder.compile()
