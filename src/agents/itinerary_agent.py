"""Combines flight, hotel and weather results into a day-by-day itinerary."""

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.prompts import ITINERARY_AGENT_PROMPT, ITINERARY_SYSTEM_PROMPT
from src.clients.llm import get_llm
from src.graph.state import TravelState
from src.utils.async_utils import bump_llm_calls


def itinerary_agent(state: TravelState):
    route_plan = state.get("route_plan") or {}
    route_summary = route_plan.get("summary", "No route grouping available.")

    prompt = ITINERARY_AGENT_PROMPT.format(
        user_query=state["user_query"],
        flight_results=state["flight_results"],
        hotel_results=state["hotel_results"],
        attraction_results=state["attraction_results"],
        weather_results=state["weather_results"],
        route_summary=route_summary,
    )

    response = get_llm().invoke([
        SystemMessage(content=ITINERARY_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": bump_llm_calls(state),
    }