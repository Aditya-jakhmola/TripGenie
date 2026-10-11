"""Formats everything the other agents produced into the user-facing answer."""

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.prompts import FINAL_AGENT_PROMPT, FINAL_SYSTEM_PROMPT
from src.clients.llm import get_llm
from src.graph.state import TravelState
from src.utils.async_utils import bump_llm_calls


def _format_budget_summary(budget: dict) -> str:
    if not budget:
        return "No budget estimate available."

    lines = [
        f"Currency: {budget.get('currency') or 'USD'}",
        f"Flights: {budget.get('flights')}",
        f"Hotels: {budget.get('hotels')}",
        f"Attractions: {budget.get('attractions')}",
        f"Estimated total: {budget.get('total')}",
    ]

    if budget.get("user_budget") is not None:
        lines.append(f"User's stated budget: {budget.get('user_budget')}")

    lines.append(f"Status: {budget.get('status') or 'unknown'}")

    if budget.get("note"):
        lines.append(f"Note: {budget.get('note')}")

    return "\n".join(lines)


def _format_packing_summary(packing: dict) -> str:
    if not packing or not packing.get("categories"):
        return "No packing list available."

    lines = []

    for category in packing["categories"]:
        items = ", ".join(category.get("items", []))
        lines.append(f"{category.get('name')}: {items}")

    if packing.get("note"):
        lines.append(f"Note: {packing.get('note')}")

    return "\n".join(lines)


def final_agent(state: TravelState):
    budget_summary = _format_budget_summary(state.get("budget_estimate") or {})
    packing_summary = _format_packing_summary(state.get("packing_list") or {})

    prompt = FINAL_AGENT_PROMPT.format(
        user_query=state["user_query"],
        flight_results=state["flight_results"],
        hotel_results=state["hotel_results"],
        attraction_results=state["attraction_results"],
        weather_results=state["weather_results"],
        itinerary=state["itinerary"],
        budget_summary=budget_summary,
        packing_summary=packing_summary,
    )

    response = get_llm().invoke([
        SystemMessage(content=FINAL_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    return {
        "messages": [response],
        "llm_calls": bump_llm_calls(state),
    }