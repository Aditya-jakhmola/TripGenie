"""Every prompt template used by the travel agents."""

FLIGHT_SYSTEM_PROMPT = "You are an expert travel flight planner."

FLIGHT_AGENT_PROMPT = """
You are a travel flight expert.

User Query:
{query}

Airport Information:
{airport_data}

Airline Information:
{airline_data}

Generate:

1. Likely departure airport
2. Likely arrival airport
3. Airlines serving this route
4. Typical flight duration
5. Estimated airfare range
6. Peak season pricing warning
7. Booking advice

Return concise travel guidance.
"""


ITINERARY_SYSTEM_PROMPT = "You are an expert travel planner."

ITINERARY_AGENT_PROMPT = """
Create a complete travel itinerary.

User Query:
{user_query}

Flight Results:
{flight_results}

Hotel Results:
{hotel_results}

Attraction and Activity Results:
{attraction_results}

Weather Results:
{weather_results}

Suggested Day Groupings (based on real geographic proximity - follow this
grouping rather than inventing your own order, when it's available):
{route_summary}

Use the attractions and activities above to build a realistic day-by-day
plan. Group nearby or similar activities on the same day where possible.
Make the itinerary practical, budget-aware, and easy to follow.
"""


FINAL_SYSTEM_PROMPT = "You are a professional AI travel booking assistant."

FINAL_AGENT_PROMPT = """
Generate the final travel response for the user.

User Request:
{user_query}

Flights:
{flight_results}

Hotels:
{hotel_results}

Attractions and Activities:
{attraction_results}

Weather:
{weather_results}

Itinerary:
{itinerary}

Budget Estimate (use these exact figures - do not invent different numbers):
{budget_summary}

Packing Suggestions (use this list - do not invent a different one):
{packing_summary}

Format the final answer beautifully using these sections:

1. Trip Summary
2. Flight Information
3. Hotel Suggestions
4. Attractions and Activities
5. Weather Information
6. Day-by-Day Itinerary
7. Estimated Budget
8. Packing Suggestions
9. Final Recommendations


Important:
- Be clear and practical.
- Mention that live flight API may not provide ticket prices if pricing is unavailable.
- Include weather-based travel advice.
- In the Estimated Budget section, present the figures given above clearly, and say
  whether the trip fits the user's stated budget if one was given.
- Keep the response useful for real travel planning.
"""


HOTEL_SEARCH_QUERY = "Best hotels for {user_query}"

ATTRACTION_SEARCH_QUERY = "Top tourist attractions and things to do for {user_query}"

PLACE_EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured data. You always respond with valid JSON only - "
    "no markdown, no code fences, no commentary."
)

PLACE_EXTRACTION_PROMPT = """
From the attraction and activity information below, extract up to 8 distinct,
specific, real-world place names (attractions, landmarks, neighborhoods) that
could be located on a map. Do not include vague categories like "local food"
or "shopping" - only actual named places.

Attraction and Activity Information:
{attraction_results}

Respond with ONLY a JSON array of strings, nothing else, for example:
["Tanah Lot Temple", "Ubud Palace", "Tegallalang Rice Terrace"]
"""

BUDGET_SYSTEM_PROMPT = (
    "You are a precise travel budgeting assistant. "
    "You always respond with valid JSON only - no markdown, no code fences, no commentary."
)

BUDGET_AGENT_PROMPT = """
Estimate the cost of this trip based only on the information given below.
If exact prices aren't available, make a reasonable real-world estimate
rather than leaving a field empty.

User Request:
{user_query}

Flight Information:
{flight_results}

Hotel Information:
{hotel_results}

Attraction and Activity Information:
{attraction_results}

Respond with ONLY a JSON object in exactly this shape, nothing else:

{{
  "currency": "<3-letter ISO currency code, e.g. USD, INR, EUR>",
  "flights": <number, estimated total flight cost for all travellers>,
  "hotels": <number, estimated total hotel cost for the whole stay>,
  "attractions": <number, estimated total cost of attractions/activities>,
  "total": <number, sum of the three above>,
  "user_budget": <number or null - the budget the user mentioned, or null if they did not mention one>,
  "status": "<one of: within_budget, over_budget, unknown>",
  "note": "<one short, practical sentence of budget advice>"
}}
"""


WEATHER_RESULTS_TEMPLATE = """
Current Weather:
{weather_data}

Forecast:
{forecast_data}
"""


DESTINATION_EXTRACTION_PROMPT = """
    Extract only the destination city or country.

    Query:
    {query}

    Return only destination name.
    """
