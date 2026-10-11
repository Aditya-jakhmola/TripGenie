"""Free geocoding via OpenStreetMap's Nominatim - no API key required."""

import logging
import time

import requests

from src.clients.cache import cached
from src.config.settings import CACHE_TTL_GEOCODE, GEOCODE_USER_AGENT

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Nominatim's usage policy caps free use at roughly 1 request/second.
_MIN_INTERVAL_SECONDS = 1.1
_last_call = 0.0


def _respect_rate_limit() -> None:
    global _last_call

    elapsed = time.monotonic() - _last_call
    wait = _MIN_INTERVAL_SECONDS - elapsed

    if wait > 0:
        time.sleep(wait)

    _last_call = time.monotonic()


@cached(prefix="geocode:place", ttl=CACHE_TTL_GEOCODE)
def geocode_place(query: str) -> dict | None:
    """
    Look up a place name and return {"lat": float, "lon": float, "display_name": str},
    or None if nothing was found or the lookup failed. Cached, since place
    names rarely move and repeated lookups would just waste the rate limit.
    """

    _respect_rate_limit()

    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1, "accept-language": "en"},
            headers={"User-Agent": GEOCODE_USER_AGENT, "Accept-Language": "en"},
            timeout=5,
        )
        response.raise_for_status()

        results = response.json()

        if not results:
            return None

        top = results[0]

        return {
            "lat": float(top["lat"]),
            "lon": float(top["lon"]),
            "display_name": top.get("display_name", query),
        }

    except Exception as error:
        logger.warning("Geocoding failed for %r: %s", query, error)
        return None


@cached(prefix="geocode:search", ttl=CACHE_TTL_GEOCODE)
def search_places(query: str, limit: int = 6) -> list:
    """
    Search for places matching free text (city, state, country...).
    Returns a list of {name, display_name, lat, lon, country} dicts,
    or an empty list if nothing matched or the lookup failed.
    """

    _respect_rate_limit()

    try:
        response = requests.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "json",
                # Over-fetch, since de-duplicating below (city proper,
                # metro area, state-level entries for the same place
                # are all common from Nominatim) can remove more than
                # half the raw results.
                "limit": limit * 3,
                "addressdetails": 1,
                "accept-language": "en",
            },
            headers={"User-Agent": GEOCODE_USER_AGENT, "Accept-Language": "en"},
            timeout=6,
        )
        response.raise_for_status()

        results = response.json()

    except Exception as error:
        logger.warning("Place search failed for %r: %s", query, error)
        return []

    places = []
    seen = set()

    for item in results:
        address = item.get("address", {}) or {}

        name = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("state")
            or (item.get("display_name", "").split(",")[0])
        )

        country = address.get("country", "")
        dedup_key = (name.lower(), country.lower())

        if dedup_key in seen:
            continue

        seen.add(dedup_key)

        try:
            places.append({
                "name": name,
                "display_name": item.get("display_name", name),
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "country": country,
            })
        except (KeyError, ValueError):
            continue

        if len(places) >= limit:
            break

    return places


WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"


@cached(prefix="wiki:thumbnail", ttl=CACHE_TTL_GEOCODE)
def wikipedia_thumbnail(title: str):
    """Best-effort real photo for a place name, or None if unavailable."""

    try:
        response = requests.get(
            WIKIPEDIA_SUMMARY_URL.format(title=requests.utils.quote(title)),
            headers={"User-Agent": GEOCODE_USER_AGENT},
            timeout=5,
        )

        if response.status_code != 200:
            return None

        data = response.json()
        thumbnail = data.get("thumbnail", {}) or {}

        return thumbnail.get("source")

    except Exception as error:
        logger.warning("Wikipedia thumbnail lookup failed for %r: %s", title, error)
        return None