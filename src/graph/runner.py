"""Entry point the API layer calls to run one travel planning request."""

import uuid
import logging
logger = logging.getLogger(__name__)


from src.config.session import require
from src.graph.graph import get_travel_graph
from src.graph.state import initial_state


def run_travel_agent(user_input: str, thread_id: str | None = None) -> dict:
    # Check everything up front so the caller learns about every missing key
    # at once, rather than one per failed attempt.
    require("GROQ_API_KEY", "DATABASE_URL")

    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = get_travel_graph().invoke(
        initial_state(user_input),
        config=config,
    )

    final_answer = result["messages"][-1].content

    return {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "attraction_results": result.get("attraction_results", ""),
        "weather_results": result.get("weather_results", ""),
        "itinerary": result.get("itinerary", ""),
        "budget_estimate": result.get("budget_estimate", {}),
        "trip_days": result.get("trip_days", 0),
        "route_plan": result.get("route_plan", {}),
        "packing_list": result.get("packing_list", {}),
        "llm_calls": result.get("llm_calls", 0),
    }


def stream_travel_agent(user_input: str, thread_id: str | None = None):
    """
    Same work as run_travel_agent, but yields ("step", node_name) after
    each node finishes, then a final ("done", result_dict) with the same
    shape run_travel_agent returns. Lets the API layer turn a single long
    silent wait into a live, honest progress stream.
    """

    require("GROQ_API_KEY", "DATABASE_URL")

    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    accumulated_state: dict = {}

    for update in get_travel_graph().stream(
        initial_state(user_input),
        config=config,
        stream_mode="updates",
    ):
        for node_name, node_output in update.items():
            if node_output:
                for key, value in node_output.items():
                    if key == "messages":
                        accumulated_state["messages"] = (
                            accumulated_state.get("messages", []) + list(value)
                        )
                    else:
                        accumulated_state[key] = value

            yield "step", node_name

    messages_so_far = accumulated_state.get("messages", [])
    final_answer = messages_so_far[-1].content if messages_so_far else ""

    result = {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": accumulated_state.get("flight_results", ""),
        "hotel_results": accumulated_state.get("hotel_results", ""),
        "attraction_results": accumulated_state.get("attraction_results", ""),
        "weather_results": accumulated_state.get("weather_results", ""),
        "itinerary": accumulated_state.get("itinerary", ""),
        "budget_estimate": accumulated_state.get("budget_estimate", {}),
        "trip_days": accumulated_state.get("trip_days", 0),
        "route_plan": accumulated_state.get("route_plan", {}),
        "packing_list": accumulated_state.get("packing_list", {}),
        "llm_calls": accumulated_state.get("llm_calls", 0),
    }

    yield "done", result


if __name__ == "__main__":
    # Run with:  python -m src.graph.runner
    user_query = (
        "I want to plan a trip to Paris in July. "
        "Can you help me find flights, hotels, and an itinerary?"
    )

    output = run_travel_agent(user_query, thread_id="test_thread_001")
    logger.debug("final answer length=%d chars", len(output["answer"]))
