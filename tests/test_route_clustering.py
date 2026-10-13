import itertools
import unittest

from src.utils.route_clustering import cluster_by_day


def pt(name, lat, lon):
    return {"name": name, "lat": lat, "lon": lon}


def names(cluster):
    return frozenset(p["name"] for p in cluster)


# Three well separated neighbourhoods, two attractions each.
UBUD = [pt("Ubud Palace", -8.5069, 115.2625), pt("Monkey Forest", -8.5188, 115.2589)]
SEMINYAK = [pt("Seminyak Beach", -8.6913, 115.1578), pt("Potato Head", -8.6841, 115.1560)]
ULUWATU = [pt("Uluwatu Temple", -8.8291, 115.0849), pt("Padang Padang", -8.8113, 115.1010)]


class ClusterByDayTests(unittest.TestCase):
    def test_no_points_gives_one_empty_group_per_day(self):
        self.assertEqual(cluster_by_day([], 3), [[], [], []])

    def test_no_points_and_zero_days_still_returns_one_group(self):
        self.assertEqual(cluster_by_day([], 0), [[]])

    def test_single_point(self):
        result = cluster_by_day([pt("A", 0, 0)], 3)
        self.assertEqual(sum(len(c) for c in result), 1)

    def test_never_more_groups_than_points(self):
        result = cluster_by_day([pt("A", 0, 0), pt("B", 5, 5)], 5)
        self.assertEqual(len(result), 2)

    def test_never_more_groups_than_requested_days(self):
        points = UBUD + SEMINYAK + ULUWATU
        self.assertLessEqual(len(cluster_by_day(points, 2)), 2)

    def test_one_day_puts_everything_together(self):
        result = cluster_by_day(UBUD + SEMINYAK, 1)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]), 4)

    def test_every_point_is_assigned_exactly_once(self):
        points = UBUD + SEMINYAK + ULUWATU
        result = cluster_by_day(points, 3)
        flat = [p["name"] for cluster in result for p in cluster]
        self.assertEqual(sorted(flat), sorted(p["name"] for p in points))

    def test_does_not_modify_the_input(self):
        points = [dict(p) for p in UBUD + SEMINYAK]
        snapshot = [dict(p) for p in points]
        cluster_by_day(points, 2)
        self.assertEqual(points, snapshot)

    def test_identical_points_do_not_crash(self):
        points = [pt(f"P{i}", 1.0, 1.0) for i in range(4)]
        result = cluster_by_day(points, 2)
        self.assertEqual(sum(len(c) for c in result), 4)

    def test_separates_two_distant_areas(self):
        result = cluster_by_day(UBUD + SEMINYAK, 2)
        self.assertCountEqual(
            [names(c) for c in result],
            [names(UBUD), names(SEMINYAK)],
        )

    def test_grouping_does_not_depend_on_input_order(self):
        # The places arrive in whatever order the LLM listed them, so a
        # correct grouping must come out the same for every ordering.
        points = UBUD + SEMINYAK + ULUWATU
        expected = {names(UBUD), names(SEMINYAK), names(ULUWATU)}

        for ordering in itertools.permutations(points):
            with self.subTest(order=[p["name"] for p in ordering]):
                result = cluster_by_day(list(ordering), 3)
                self.assertEqual({names(c) for c in result}, expected)


if __name__ == "__main__":
    unittest.main()
