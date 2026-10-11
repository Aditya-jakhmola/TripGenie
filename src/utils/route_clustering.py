"""
Pure-Python k-means style clustering of geocoded points into day groups.

Deliberately simple - this is grouping a handful of attractions (usually
under 8), not building a real routing engine. Good enough to keep nearby
places on the same day without adding a heavy dependency.
"""

import math


def _distance(a: tuple, b: tuple) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def cluster_by_day(points: list[dict], num_days: int) -> list[list[dict]]:
    """Group points (each a dict with 'lat'/'lon') into num_days clusters."""

    if not points:
        return [[] for _ in range(max(1, num_days))]

    num_days = max(1, min(num_days, len(points)))

    coords = [(p["lat"], p["lon"]) for p in points]

    step = max(1, len(coords) // num_days)
    centroids = [coords[min(i * step, len(coords) - 1)] for i in range(num_days)]

    assignments = [0] * len(coords)

    for _ in range(10):
        changed = False

        for i, point in enumerate(coords):
            distances = [_distance(point, c) for c in centroids]
            nearest = distances.index(min(distances))

            if assignments[i] != nearest:
                assignments[i] = nearest
                changed = True

        for k in range(num_days):
            members = [coords[i] for i in range(len(coords)) if assignments[i] == k]

            if members:
                centroids[k] = (
                    sum(m[0] for m in members) / len(members),
                    sum(m[1] for m in members) / len(members),
                )

        if not changed:
            break

    clusters: list[list[dict]] = [[] for _ in range(num_days)]

    for i, point in enumerate(points):
        clusters[assignments[i]].append(point)

    return clusters