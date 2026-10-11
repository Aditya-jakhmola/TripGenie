"""Fetches current weather and forecast for the extracted destination."""

from langchain_core.messages import AIMessage

from src.agents.prompts import WEATHER_RESULTS_TEMPLATE
from src.graph.state import TravelState
from src.agents.destination import extract_destination
from src.mcp_servers.local import forecast_mcp_search, weather_mcp_search
from src.utils.async_utils import run_async


def weather_agent(state: TravelState):
    city = extract_destination(state["user_query"])

    try:
        weather_data = run_async(weather_mcp_search(city))
        forecast_data = run_async(forecast_mcp_search(city))

        weather_results = WEATHER_RESULTS_TEMPLATE.format(
            weather_data=weather_data,
            forecast_data=forecast_data,
        )
    except Exception as e:
        weather_results = f"Weather information unavailable: {str(e)}"

    return {
        "weather_results": weather_results,
        "messages": [
            AIMessage(content="Weather information fetched")
        ],
    }