import unittest

from src.agents.packing_agent import packing_agent


def make_state(**overrides):
    state = {
        "weather_results": "",
        "itinerary": "",
        "attraction_results": "",
        "user_query": "",
        "trip_days": 0,
    }
    state.update(overrides)
    return state


def categories_of(state):
    packing = packing_agent(state)["packing_list"]
    return {c["name"]: c["items"] for c in packing["categories"]}


class PackingListTests(unittest.TestCase):
    def test_baseline_has_clothing_and_essentials_only(self):
        self.assertEqual(list(categories_of(make_state())), ["Clothing", "Essentials"])

    def test_essentials_always_include_the_basics(self):
        items = categories_of(make_state())["Essentials"]
        for needed in ["Passport / ID", "Phone and charger", "Travel adapter"]:
            self.assertIn(needed, items)

    def test_rain_adds_rain_gear(self):
        items = categories_of(make_state(weather_results="Light rain expected"))["Weather"]
        self.assertIn("Rain jacket", items)
        self.assertIn("Compact umbrella", items)

    def test_cold_adds_warm_clothing(self):
        items = categories_of(make_state(weather_results="Freezing and snow"))["Weather"]
        self.assertIn("Warm jacket", items)

    def test_hot_adds_sun_protection(self):
        items = categories_of(make_state(weather_results="Hot and sunny"))["Weather"]
        self.assertIn("Sunscreen", items)

    def test_beach_adds_swimwear(self):
        items = categories_of(make_state(itinerary="Relax on the beach"))["Activities"]
        self.assertIn("Swimwear", items)

    def test_hiking_adds_hiking_shoes(self):
        items = categories_of(make_state(itinerary="Hike to the waterfall"))["Activities"]
        self.assertIn("Hiking shoes", items)

    def test_temples_add_modest_clothing(self):
        items = categories_of(make_state(attraction_results="Visit the temple"))["Activities"]
        self.assertTrue(any("Modest" in item for item in items))

    def test_every_signal_source_is_read(self):
        for source in ["weather_results", "itinerary", "attraction_results", "user_query"]:
            with self.subTest(source=source):
                cats = categories_of(make_state(**{source: "heavy rain"}))
                self.assertIn("Weather", cats)

    def test_repeated_keywords_do_not_duplicate_items(self):
        items = categories_of(make_state(weather_results="rain shower drizzle monsoon"))["Weather"]
        self.assertEqual(items.count("Rain jacket"), 1)

    def test_matching_is_case_insensitive(self):
        self.assertIn("Weather", categories_of(make_state(weather_results="RAIN")))

    def test_keywords_must_be_whole_words(self):
        # The default prompt says "Find flights, hotels..." - "hotels" must not
        # be mistaken for "hot", and "rainforest" is not rain.
        cats = categories_of(make_state(user_query="Find flights, hotels and a rainforest tour"))
        self.assertNotIn("Weather", cats)

    def test_clothing_scales_with_trip_length(self):
        items = categories_of(make_state(trip_days=3))["Clothing"]
        self.assertIn("3 sets of everyday clothing", items)
        self.assertIn("3 pairs of socks and underwear", items)

    def test_clothing_is_capped_at_a_week_and_laundry_is_suggested(self):
        packing = packing_agent(make_state(trip_days=14))["packing_list"]
        clothing = packing["categories"][0]["items"]
        self.assertIn("7 sets of everyday clothing", clothing)
        self.assertIn("laundry", packing["note"])

    def test_note_appears_only_beyond_seven_days(self):
        self.assertIsNone(packing_agent(make_state(trip_days=7))["packing_list"]["note"])
        self.assertIsNotNone(packing_agent(make_state(trip_days=8))["packing_list"]["note"])

    def test_unknown_trip_length_defaults_to_five_days(self):
        for days in [0, None]:
            with self.subTest(days=days):
                packing = packing_agent(make_state(trip_days=days))["packing_list"]
                self.assertIn("5 sets of everyday clothing", packing["categories"][0]["items"])
                self.assertIsNone(packing["note"])

    def test_missing_state_keys_do_not_crash(self):
        packing = packing_agent({})["packing_list"]
        self.assertEqual([c["name"] for c in packing["categories"]], ["Clothing", "Essentials"])

    def test_essentials_list_is_not_shared_between_calls(self):
        first = packing_agent(make_state())["packing_list"]["categories"][-1]["items"]
        first.append("MUTATED")
        second = packing_agent(make_state())["packing_list"]["categories"][-1]["items"]
        self.assertNotIn("MUTATED", second)


if __name__ == "__main__":
    unittest.main()
