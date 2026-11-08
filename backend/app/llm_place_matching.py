import json

from app.google_places import GooglePlace
from app.llm import generate_text


async def match_place_with_llm(
    attraction_name: str,
    destination: str,
    places: list[GooglePlace],
    description: str = "",
    booking_type: str = "unknown",
) -> GooglePlace | None:
    """Match a visitor experience to a relevant physical location."""
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
Verified attraction description: {description}
Booking type: {booking_type}
Destination: {destination}

Google Places candidates:
{json.dumps(candidates, ensure_ascii=False)}

Select a candidate only when it represents the correct physical
location for the recommended visitor experience.

General rules:
- Match the exact attraction or provider, not merely a similar activity.
- Accept established aliases, translations, and spelling variations.
- Never select a booking office as an activity location.
- Never select an arbitrary provider for a generic activity.
- For activities such as rafting, ATV tours, and guided excursions,
  select a provider only if that provider is explicitly named
  in the requested attraction.
- Never use a nearby attraction as a substitute for the requested one.
- A trailhead is valid only when it clearly belongs to the named trail.
- If multiple locations remain plausible, return null.

Guided tour rules:
- A guided tour may visit multiple locations.
- Do not treat one tour stop as the meeting point for the entire tour.
- Do not assume a national park's coordinates are the tour departure point.
- Select a location only when the provided description explicitly
  identifies it as the tour's meeting point, departure point, or
  the physical venue where the guided experience takes place.
- A provider's name matching a Google Places name is not sufficient
  by itself to establish the meeting point.
- If the meeting or departure location cannot be established
  from the provided information, return null.

Use only the supplied candidates.
Do not invent locations or missing facts.
If uncertain, return null.

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

    matches = [place for place in places if place.place_id == selected_id]

    if len(matches) != 1:
        return None

    return matches[0]
