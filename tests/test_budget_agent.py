import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.agents import budget_agent
from src.agents.budget_agent import _FALLBACK_BUDGET, _parse_budget_json


class FakeLLM:
    """Stands in for the Groq client so no network call is made."""

    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error

    def invoke(self, messages):
        if self.error:
            raise self.error
        return SimpleNamespace(content=self.content)


GOOD = (
    '{"currency": "USD", "flights": 1000, "hotels": 800, "attractions": 200, '
    '"total": 2000, "user_budget": null, "status": "unknown", "note": "ok"}'
)


class ParseBudgetJsonTests(unittest.TestCase):
    def test_clean_json(self):
        result = _parse_budget_json(GOOD)
        self.assertEqual(result["total"], 2000)
        self.assertEqual(result["currency"], "USD")

    def test_json_in_a_labelled_code_fence(self):
        self.assertEqual(_parse_budget_json(f"```json\n{GOOD}\n```")["total"], 2000)

    def test_json_in_an_unlabelled_code_fence(self):
        self.assertEqual(_parse_budget_json(f"```\n{GOOD}\n```")["total"], 2000)

    def test_json_surrounded_by_chatter(self):
        raw = f"Sure! Here is your budget:\n{GOOD}\nHope that helps."
        self.assertEqual(_parse_budget_json(raw)["total"], 2000)

    def test_surrounding_whitespace_is_ignored(self):
        self.assertEqual(_parse_budget_json(f"\n\n   {GOOD}   \n")["total"], 2000)

    def test_unparseable_text_gives_the_fallback(self):
        self.assertEqual(_parse_budget_json("I cannot do that."), _FALLBACK_BUDGET)

    def test_empty_string_gives_the_fallback(self):
        self.assertEqual(_parse_budget_json(""), _FALLBACK_BUDGET)

    def test_truncated_json_gives_the_fallback(self):
        self.assertEqual(_parse_budget_json('{"currency": "USD", "flights": 10'), _FALLBACK_BUDGET)

    def test_fallback_is_a_copy_so_callers_cannot_corrupt_it(self):
        result = _parse_budget_json("nonsense")
        result["note"] = "changed"
        self.assertNotEqual(_FALLBACK_BUDGET["note"], "changed")

    def test_valid_json_that_is_not_an_object_gives_the_fallback(self):
        # Downstream code calls .get() on the result, so a list, number or
        # null must never get through.
        for raw in ["[1, 2, 3]", "42", "null", '"text"', "true"]:
            with self.subTest(raw=raw):
                self.assertEqual(_parse_budget_json(raw), _FALLBACK_BUDGET)


class BudgetAgentTests(unittest.TestCase):
    STATE = {
        "user_query": "Plan a trip to Bali",
        "flight_results": "flights",
        "hotel_results": "hotels",
        "attraction_results": "attractions",
        "llm_calls": 2,
    }

    def run_agent(self, fake):
        with patch.object(budget_agent, "get_llm", lambda: fake):
            return budget_agent.budget_agent(dict(self.STATE))

    def test_returns_the_parsed_estimate_and_counts_the_call(self):
        result = self.run_agent(FakeLLM(content=GOOD))
        self.assertEqual(result["budget_estimate"]["total"], 2000)
        self.assertEqual(result["llm_calls"], 3)

    def test_unparseable_model_output_degrades_gracefully(self):
        result = self.run_agent(FakeLLM(content="no json here"))
        self.assertEqual(result["budget_estimate"], _FALLBACK_BUDGET)
        self.assertEqual(result["llm_calls"], 3)

    def test_llm_failure_degrades_gracefully_with_the_reason(self):
        result = self.run_agent(FakeLLM(error=RuntimeError("rate limited")))
        self.assertIsNone(result["budget_estimate"]["total"])
        self.assertIn("rate limited", result["budget_estimate"]["note"])
        self.assertEqual(result["llm_calls"], 3)

    def test_failure_note_does_not_leak_into_the_shared_fallback(self):
        self.run_agent(FakeLLM(error=RuntimeError("boom")))
        self.assertNotIn("boom", _FALLBACK_BUDGET["note"])


if __name__ == "__main__":
    unittest.main()
