"""
Deterministic packing list based on weather, activities and trip length.

No LLM call here on purpose - weather and activity signals are already
available as plain text from earlier agents, and a rules-based checklist
is fast, free, and predictable rather than adding another Groq call to
an already rate-limit-sensitive pipeline.
"""

import re

from src.graph.state import TravelState

_ALWAYS_ITEMS = [
    "Passport / ID",
    "Phone and charger",
    "Travel adapter",
    "Any regular medications",
    "Toiletries",
    "Reusable water bottle",
    "Cash and cards",
]

_WEATHER_RULES = [
    (r"\b(rain|shower|drizzle|monsoon)\b", ["Rain jacket", "Compact umbrella"]),
    (r"\b(cold|chilly|snow|frost|freezing)\b", ["Warm jacket", "Thermal layers", "Gloves and beanie"]),
    (r"\b(hot|sunny|heat|humid)\b", ["Sunscreen", "Sunglasses", "Hat", "Light breathable clothing"]),
    (r"\b(wind|windy)\b", ["Windbreaker"]),
]

_ACTIVITY_RULES = [
    (r"\b(beach|swim|snorkel|dive|coast|island)\b", ["Swimwear", "Beach towel", "Flip-flops"]),
    (r"\b(hike|trek|trail|mountain|waterfall)\b", ["Hiking shoes", "Daypack", "Insect repellent"]),
    (r"\b(temple|shrine|mosque|religious|palace)\b", ["Modest, shoulder/knee-covering outfit"]),
    (r"\b(fine.?dining|formal|dinner reservation|rooftop)\b", ["One smart-casual outfit"]),
]


def _collect(text: str, rules: list) -> list:
    text_lower = (text or "").lower()
    items: list = []

    for pattern, rule_items in rules:
        if re.search(pattern, text_lower):
            for item in rule_items:
                if item not in items:
                    items.append(item)

    return items


def packing_agent(state: TravelState):
    trip_days = state.get("trip_days") or 0

    signal_text = " ".join([
        state.get("weather_results", ""),
        state.get("itinerary", ""),
        state.get("attraction_results", ""),
        state.get("user_query", ""),
    ])

    weather_items = _collect(signal_text, _WEATHER_RULES)
    activity_items = _collect(signal_text, _ACTIVITY_RULES)

    clothing_days = min(trip_days, 7) if trip_days else 5

    clothing_items = [
        f"{clothing_days} sets of everyday clothing",
        f"{clothing_days} pairs of socks and underwear",
        "Comfortable walking shoes",
        "Sleepwear",
    ]

    categories = [{"name": "Clothing", "items": clothing_items}]

    if weather_items:
        categories.append({"name": "Weather", "items": weather_items})

    if activity_items:
        categories.append({"name": "Activities", "items": activity_items})

    categories.append({"name": "Essentials", "items": list(_ALWAYS_ITEMS)})

    note = None

    if trip_days and trip_days > 7:
        note = "Trip is longer than a week - plan on doing laundry rather than packing for every day."

    packing_list = {
        "trip_days": trip_days,
        "categories": categories,
        "note": note,
    }

    return {
        "packing_list": packing_list,
    }