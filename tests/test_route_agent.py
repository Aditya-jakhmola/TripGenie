import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.agents import route_agent
from src.agents.route_agent import (
    DEFAULT_TRIP_DAYS,
    MAX_PLACES,
    _extract_place_names,
    _extract_trip_days,
    _format_route_summary,
)


class FakeLLM:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error

    def invoke(self, messages):
        if self.error:
            raise self.error
        return SimpleNamespace(content=self.content)


class ExtractTripDaysTests(unittest.TestCase):
    def test_common_phrasings(self):
        cases = {
            "Plan a 7 day trip to Bali": 7,
            "Plan a 7-day trip to Bali": 7,
            "10 days in Rome": 10,
            "Plan a 3 DAY trip": 3,
            "1 day in Paris": 1,
            "a trip for 2 travellers over 4 days": 4,
            "60 days across Asia": 60,
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(_extract_trip_days(query), expected)

    def test_falls_back_to_the_default_when_no_number_is_given(self):
        for query in [
            "Plan a trip to Bali",
            "Find flights, hotels, the weather outlook and a day-by-day itinerary.",
            "",
        ]:
            with self.subTest(query=query):
                self.assertEqual(_extract_trip_days(query), DEFAULT_TRIP_DAYS)

    def test_out_of_range_values_fall_back_to_the_default(self):
        for query in ["0 day trip", "61 days away", "500 day voyage"]:
            with self.subTest(query=query):
                self.assertEqual(_extract_trip_days(query), DEFAULT_TRIP_DAYS)


class FormatRouteSummaryTests(unittest.TestCase):
    def test_lists_each_day_and_skips_empty_ones(self):
        clusters = [[{"name": "A"}, {"name": "B"}], [], [{"name": "C"}]]
        self.assertEqual(
            _format_route_summary(clusters, []),
            "Day 1 area: A, B\nDay 3 area: C",
        )

    def test_mentions_places_that_could_not_be_located(self):
        summary = _format_route_summary([[{"name": "A"}]], ["Hidden Cafe", "Secret Beach"])
        self.assertIn("Day 1 area: A", summary)
        self.assertIn("Could not confirm location for: Hidden Cafe, Secret Beach", summary)

    def test_nothing_to_show_gives_a_clear_message(self):
        self.assertIn("No specific attraction locations", _format_route_summary([[], []], []))


class ExtractPlaceNamesTests(unittest.TestCase):
    def extract(self, content):
        with patch.object(route_agent, "get_llm", lambda: FakeLLM(content=content)):
            return _extract_place_names("some attraction text")

    def test_plain_json_array(self):
        self.assertEqual(self.extract('["Tanah Lot", "Ubud Palace"]'), ["Tanah Lot", "Ubud Palace"])

    def test_array_in_a_code_fence(self):
        self.assertEqual(self.extract('```json\n["A", "B"]\n```'), ["A", "B"])

    def test_array_surrounded_by_chatter(self):
        self.assertEqual(self.extract('Here you go: ["A", "B"] enjoy!'), ["A", "B"])

    def test_non_string_entries_are_dropped(self):
        self.assertEqual(self.extract('["A", 5, null, "B", ["nested"]]'), ["A", "B"])

    def test_result_is_capped(self):
        names = [f"Place {i}" for i in range(MAX_PLACES + 5)]
        raw = "[" + ", ".join(f'"{n}"' for n in names) + "]"
        self.assertEqual(self.extract(raw), names[:MAX_PLACES])

    def test_unparseable_output_gives_an_empty_list(self):
        self.assertEqual(self.extract("no places found"), [])

    def test_valid_json_that_is_not_a_list_gives_an_empty_list(self):
        for raw in ["5", "null", "true", '"just text"']:
            with self.subTest(raw=raw):
                self.assertEqual(self.extract(raw), [])


class RouteAgentTests(unittest.TestCase):
    COORDS = {
        "Tanah Lot, Bali": {"lat": -8.62, "lon": 115.09},
        "Ubud Palace, Bali": {"lat": -8.50, "lon": 115.26},
    }

    def state(self, **overrides):
        base = {
            "user_query": "Plan a 2 day trip to Bali",
            "attraction_results": "text about places",
            "llm_calls": 0,
        }
        base.update(overrides)
        return base

    def run_agent(self, llm, geocode=None, state=None):
        geocode = geocode or (lambda query: self.COORDS.get(query))
        with patch.object(route_agent, "get_llm", lambda: llm), \
             patch.object(route_agent, "geocode_place", geocode), \
             patch.object(route_agent, "extract_destination", lambda q: "Bali"):
            return route_agent.route_agent(state or self.state())

    def test_builds_a_route_plan_from_located_places(self):
        llm = FakeLLM(content='["Tanah Lot", "Ubud Palace", "Mystery Place"]')
        result = self.run_agent(llm)

        plan = result["route_plan"]
        located = [p["name"] for day in plan["days"] for p in day["places"]]

        self.assertEqual(result["trip_days"], 2)
        self.assertCountEqual(located, ["Tanah Lot", "Ubud Palace"])
        self.assertEqual(plan["unplaced"], ["Mystery Place"])
        self.assertIn("Mystery Place", plan["summary"])
        self.assertEqual(result["llm_calls"], 1)

    def test_geocoding_queries_include_the_destination(self):
        seen = []

        def geocode(query):
            seen.append(query)
            return None

        self.run_agent(FakeLLM(content='["Tanah Lot"]'), geocode=geocode)
        self.assertEqual(seen, ["Tanah Lot, Bali"])

    def test_every_place_failing_to_geocode_is_reported_not_fatal(self):
        result = self.run_agent(FakeLLM(content='["A", "B"]'), geocode=lambda q: None)
        plan = result["route_plan"]

        self.assertEqual(plan["unplaced"], ["A", "B"])
        self.assertTrue(all(day["places"] == [] for day in plan["days"]))

    def test_llm_failure_is_survived(self):
        result = self.run_agent(FakeLLM(error=RuntimeError("rate limited")))

        self.assertEqual(result["route_plan"]["unplaced"], [])
        self.assertIn("No specific attraction locations", result["route_plan"]["summary"])
        self.assertEqual(result["llm_calls"], 1)

    def test_trip_length_comes_from_the_request(self):
        result = self.run_agent(
            FakeLLM(content="[]"),
            state=self.state(user_query="Plan a 4 day trip to Bali"),
        )
        self.assertEqual(result["trip_days"], 4)
        self.assertEqual(len(result["route_plan"]["days"]), 4)

    def test_day_numbers_start_at_one(self):
        result = self.run_agent(FakeLLM(content="[]"))
        self.assertEqual([d["day"] for d in result["route_plan"]["days"]], [1, 2])


if __name__ == "__main__":
    unittest.main()
