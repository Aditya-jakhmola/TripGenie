"""Wires the agents together into the LangGraph workflow."""

from langgraph.graph import END, START, StateGraph

from src.agents.attraction_agent import attraction_agent
from src.agents.budget_agent import budget_agent
from src.agents.final_agent import final_agent
from src.agents.flight_agent import flight_agent
from src.agents.hotel_agent import hotel_agent
from src.agents.itinerary_agent import itinerary_agent
from src.agents.packing_agent import packing_agent
from src.agents.route_agent import route_agent
from src.agents.weather_agent import weather_agent
from src.clients.checkpointer import get_checkpointer
from src.config.session import require, resolve_database_url
from src.graph.state import TravelState


def build_graph() -> StateGraph:
    """Build the uncompiled graph. Useful for tests and for visualisation."""

    graph = StateGraph(TravelState)

    graph.add_node("flight_agent", flight_agent)
    graph.add_node("hotel_agent", hotel_agent)
    graph.add_node("attraction_agent", attraction_agent)
    graph.add_node("route_agent", route_agent)
    graph.add_node("weather_agent", weather_agent)
    graph.add_node("itinerary_agent", itinerary_agent)
    graph.add_node("packing_agent", packing_agent)
    graph.add_node("budget_agent", budget_agent)
    graph.add_node("final_agent", final_agent)

    graph.add_edge(START, "flight_agent")
    graph.add_edge("flight_agent", "hotel_agent")
    graph.add_edge("hotel_agent", "attraction_agent")
    graph.add_edge("attraction_agent", "route_agent")
    graph.add_edge("route_agent", "weather_agent")
    graph.add_edge("weather_agent", "itinerary_agent")
    graph.add_edge("itinerary_agent", "packing_agent")
    graph.add_edge("packing_agent", "budget_agent")
    graph.add_edge("budget_agent", "final_agent")
    graph.add_edge("final_agent", END)

    return graph


def get_travel_graph():
    """
    Compile the graph against whichever database the current session
    resolves to.

    Deliberately NOT cached. Compiling takes milliseconds, but a cached
    compiled graph holds on to its checkpointer, and so to one specific
    database connection, for the life of the process. When a managed
    database drops that connection while idle, every later request would
    then fail until the server was restarted. get_checkpointer() instead
    returns a checkpointer bound to a connection it has just verified.
    """

    require("DATABASE_URL")

    return build_graph().compile(
        checkpointer=get_checkpointer(resolve_database_url())
    )
