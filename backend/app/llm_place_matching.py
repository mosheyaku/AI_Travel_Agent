import json

from app.google_places import GooglePlace
from app.llm import generate_text


async def match_place_with_llm(
    attraction_name: str,
    destination: str,
    places: list[GooglePlace],
) -> GooglePlace | None:
    """Identify an unambiguous place match from Google Places candidates."""
    if not places:
        return None

    candidates = [
        {
            "place_id": place.place_id,
            "name": place.name,
            "types": place.types,
        }
        for place in places
    ]

    prompt = f"""
You are a strict geographic place-matching assistant.

Requested attraction: {attraction_name}
Destination: {destination}

Google Places candidates:
{json.dumps(candidates, ensure_ascii=False)}

Choose a candidate only if it clearly refers to the same physical
attraction or a clearly identified entrance or trailhead.

Requirements:
- Match the requested attraction, not just a similar activity.
- Accept spelling variations, translations, and established aliases.
- Do not match a generic activity to an unrelated activity provider.
- Do not confuse a booking office with the actual activity location.
- Do not select a candidate if multiple locations remain plausible.
- If the attraction describes several activities or locations,
  return null.
- Use only the candidates provided.
- If uncertain, return null.
- A general activity or geographic area is not the same as a specific provider.
- For activities such as rafting, ATV tours, and guided excursions,
  select a provider only if that provider is explicitly named in
  the requested attraction.
- Do not assign an arbitrary provider, meeting point, or river location
  to a general activity.
- A trailhead may match a named hiking trail only when it clearly
  identifies that same trail.

Return valid JSON only:
{{"place_id": null}}
"""

    response = await generate_text(prompt)

    try:
        selected_id = json.loads(response)["place_id"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None

    if not isinstance(selected_id, str):
        return None

    matches = [
        place
        for place in places
        if place.place_id == selected_id
    ]

    if len(matches) != 1:
        return None

    print(
    f"LLM place match: {attraction_name!r} -> "
    f"{matches[0].name!r} "
    f"(place_id={matches[0].place_id})",
    flush=True,
    )
    return matches[0]