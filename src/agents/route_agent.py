"""
Groups attractions into day-by-day clusters using real geocoded locations.

Turns the free-text attraction results into a small set of named places,
looks up real coordinates for each through OpenStreetMap (no API key
needed), and clusters them by day so nearby attractions land on the same
day of the itinerary instead of a random order.
"""

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.destination import extract_destination
from src.agents.prompts import PLACE_EXTRACTION_PROMPT, PLACE_EXTRACTION_SYSTEM_PROMPT
from src.clients.llm import get_llm
from src.graph.state import TravelState
from src.utils.async_utils import bump_llm_calls
from src.utils.geocode import geocode_place
from src.utils.route_clustering import cluster_by_day

logger = logging.getLogger(__name__)

MAX_PLACES = 8
DEFAULT_TRIP_DAYS = 5


def _extract_trip_days(user_query: str) -> int:
    match = re.search(r"(\d+)\s*[- ]?\s*day", user_query, re.IGNORECASE)

    if match:
        try:
            days = int(match.group(1))
            if 1 <= days <= 60:
                return days
        except ValueError:
            pass

    return DEFAULT_TRIP_DAYS


def _extract_place_names(attraction_results: str) -> list:
    prompt = PLACE_EXTRACTION_PROMPT.format(attraction_results=attraction_results)

    response = get_llm().invoke([
        SystemMessage(content=PLACE_EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    text = response.content.strip()

    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]

    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    try:
        names = json.loads(text)
    except (json.JSONDecodeError, ValueError) as error:
        logger.warning("Could not parse extracted place names: %s", error)
        return []

    # A bare string would otherwise be iterated letter by letter, and a
    # number or null would raise, so anything but a list is rejected.
    if not isinstance(names, list):
        logger.warning("Place names were a %s, not a list", type(names).__name__)
        return []

    return [n for n in names if isinstance(n, str)][:MAX_PLACES]


def _format_route_summary(clusters: list, unplaced: list) -> str:
    lines = []

    for i, day_places in enumerate(clusters, start=1):
        if not day_places:
            continue

        names = ", ".join(p["name"] for p in day_places)
        lines.append(f"Day {i} area: {names}")

    if unplaced:
        lines.append(f"Could not confirm location for: {', '.join(unplaced)}")

    if not lines:
        return "No specific attraction locations could be identified for grouping."

    return "\n".join(lines)


def route_agent(state: TravelState):
    trip_days = _extract_trip_days(state["user_query"])
    destination = extract_destination(state["user_query"])

    try:
        place_names = _extract_place_names(state["attraction_results"])
    except Exception as e:
        logger.warning("route_agent place extraction failed: %s", e)
        place_names = []

    geocoded = []
    unplaced = []

    for name in place_names:
        result = geocode_place(f"{name}, {destination}")

        if result:
            geocoded.append({
                "name": name,
                "lat": result["lat"],
                "lon": result["lon"],
            })
        else:
            unplaced.append(name)

    clusters = cluster_by_day(geocoded, trip_days)
    route_summary = _format_route_summary(clusters, unplaced)

    route_plan = {
        "trip_days": trip_days,
        "days": [
            {"day": i + 1, "places": day_places}
            for i, day_places in enumerate(clusters)
        ],
        "unplaced": unplaced,
        "summary": route_summary,
    }

    return {
        "trip_days": trip_days,
        "route_plan": route_plan,
        "llm_calls": bump_llm_calls(state),
    }