"""Estimates a structured trip budget by asking the LLM for JSON."""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.prompts import BUDGET_AGENT_PROMPT, BUDGET_SYSTEM_PROMPT
from src.clients.llm import get_llm
from src.graph.state import TravelState
from src.utils.async_utils import bump_llm_calls

logger = logging.getLogger(__name__)


_FALLBACK_BUDGET = {
    "currency": "USD",
    "flights": None,
    "hotels": None,
    "attractions": None,
    "total": None,
    "user_budget": None,
    "status": "unknown",
    "note": "Could not calculate a detailed budget estimate for this trip.",
}


def _parse_budget_json(raw: str) -> dict:
    """
    Best-effort JSON parse.

    The model is small and occasionally wraps its answer in a code fence
    or adds a stray sentence before/after the JSON, so this cleans that
    up before falling back to a safe placeholder.
    """

    text = raw.strip()

    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
        if text.lower().startswith("json"):
            text = text[4:]

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError) as error:
        logger.warning("Could not parse budget JSON: %s", error)
        return dict(_FALLBACK_BUDGET)

    # Valid JSON is not enough: later code calls .get() on this, so a list,
    # number or null from the model must fall back like any other bad output.
    if not isinstance(parsed, dict):
        logger.warning("Budget JSON was a %s, not an object", type(parsed).__name__)
        return dict(_FALLBACK_BUDGET)

    return parsed


def budget_agent(state: TravelState):
    prompt = BUDGET_AGENT_PROMPT.format(
        user_query=state["user_query"],
        flight_results=state["flight_results"],
        hotel_results=state["hotel_results"],
        attraction_results=state["attraction_results"],
    )

    try:
        response = get_llm().invoke([
            SystemMessage(content=BUDGET_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        budget_estimate = _parse_budget_json(response.content)
    except Exception as e:
        logger.warning("budget_agent failed: %s", e)
        budget_estimate = dict(_FALLBACK_BUDGET)
        budget_estimate["note"] = f"Budget estimate unavailable: {str(e)}"

    return {
        "budget_estimate": budget_estimate,
        "llm_calls": bump_llm_calls(state),
    }