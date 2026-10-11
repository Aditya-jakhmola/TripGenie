"""Finds attractions and activities for the destination through the Tavily MCP server."""

from langchain_core.messages import AIMessage

from src.agents.prompts import ATTRACTION_SEARCH_QUERY
from src.config.settings import TAVILY_RESULT_CHAR_LIMIT
from src.graph.state import TravelState
from src.mcp_servers.remote import tavily_mcp_search
from src.utils.async_utils import bump_llm_calls, run_async, truncate


def attraction_agent(state: TravelState):
    query = ATTRACTION_SEARCH_QUERY.format(user_query=state["user_query"])

    try:
        attraction_results = truncate(
            run_async(tavily_mcp_search(query)), TAVILY_RESULT_CHAR_LIMIT
        )
    except Exception as e:
        attraction_results = f"Attraction information unavailable: {str(e)}"

    return {
        "attraction_results": attraction_results,
        "messages": [
            AIMessage(content="Attraction information fetched.")
        ],
        "llm_calls": bump_llm_calls(state),
    }