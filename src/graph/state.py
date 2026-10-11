"""Shared state passed between every node of the travel graph."""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage


class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    flight_results: str
    hotel_results: str
    attraction_results: str
    itinerary: str
    budget_estimate: dict
    trip_days: int
    route_plan: dict
    packing_list: dict
    llm_calls: int
    weather_results: str


def initial_state(user_query: str) -> TravelState:
    """Build the empty state the graph starts from."""

    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content=user_query)],
        "user_query": user_query,
        "flight_results": "",
        "hotel_results": "",
        "attraction_results": "",
        "weather_results": "",
        "itinerary": "",
        "budget_estimate": {},
        "trip_days": 0,
        "route_plan": {},
        "packing_list": {},
        "llm_calls": 0,
    }
