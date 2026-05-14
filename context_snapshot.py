# context_snapshot.py
# Phase 4: Automatic environmental context snapshot on high-severity flares.
#
# Weather + air quality: Open-Meteo Forecast and Air Quality APIs (free, no key).
# Pollen (tree/grass/weed index): Tomorrow.io /v4/weather/realtime (free tier,
#   API key required — set TOMORROW_API_KEY env var or add to data/config.json).
#
# All results are cached locally in data/snapshot_cache/ with a 1-hour TTL.
# No patient health data leaves the device; only lat/lon coordinates are sent,
# identical to a standard weather app lookup.

import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from models import EnvironmentalEntry, Patient
from storage import StorageManager

WEATHER_API     = "https://api.open-meteo.com/v1/forecast"
AQI_API         = "https://air-quality-api.open-meteo.com/v1/air-quality"
TOMORROW_API    = "https://api.tomorrow.io/v4/weather/realtime"
CACHE_TTL_H     = 1      # re-fetch if snapshot is older than this
REQUEST_DELAY   = 0.5    # seconds between successive API calls
FLARE_THRESHOLD = 7      # severity >= this auto-triggers a snapshot


def _load_api_key(env_var: str, config_path: str = "data/config.json") -> str:
    """Return an API key by checking (in order):
    1. The named environment variable.
    2. The ``env_var`` key inside ``data/config.json``.
    Returns an empty string if neither source has the key.
    """
    val = os.environ.get(env_var, "")
    if val:
        return val
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f).get(env_var, "")
    except (OSError, json.JSONDecodeError):
        return ""


# Resolved once at import time; re-checked lazily inside _fetch_pollen_tomorrow
# so a config file created in the same session is still picked up.
TOMORROW_API_KEY: str = _load_api_key("TOMORROW_API_KEY")

# WMO weather interpretation codes → human-readable label
_WMO: Dict[int, str] = {
    0:  "Clear sky",
    1:  "Mainly clear",  2:  "Partly cloudy",  3:  "Overcast",
    45: "Foggy",         48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain",   63: "Moderate rain",    65: "Heavy rain",
    71: "Slight snow",   73: "Moderate snow",    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight showers", 81: "Moderate showers", 82: "Heavy showers",
    85: "Light snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


class ContextSnapshot:
    """Fetches and merges real-time environmental context for high-severity days.

    Two main entry points:
    - ``fetch(date_str)``            — cache-first raw snapshot dict
    - ``fetch_and_merge(date_str)``  — fetch and write into the day's EnvironmentalEntry
    """

    def __init__(
        self,
        patient: Patient,
        storage: StorageManager,
        cache_dir: str = "data/snapshot_cache",
    ):
        self.patient   = patient
        self.storage   = storage
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def has_location(self) -> bool:
        return self.patient.latitude is not None and self.patient.longitude is not None

    # =========================================================
    # CACHE
    # =========================================================

    def _cache_path(self, date_str: str) -> str:
        return os.path.join(self.cache_dir, f"{date_str}.json")

    def _load_cache(self, date_str: str) -> Optional[Dict]:
        path = self._cache_path(date_str)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
            if datetime.now() > datetime.fromisoformat(entry["expires_at"]):
                return None
            return entry["snapshot"]
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            return None

    def _save_cache(self, date_str: str, snapshot: Dict) -> None:
        entry = {
            "cached_at":  datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=CACHE_TTL_H)).isoformat(),
            "snapshot":   snapshot,
        }
        try:
            with open(self._cache_path(date_str), "w", encoding="utf-8") as f:
                json.dump(entry, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    # =========================================================
    # HTTP HELPERS
    # =========================================================

    def _get_json(self, url: str, params: Dict[str, str]) -> Optional[Dict]:
        full_url = f"{url}?{urlencode(params)}"
        try:
            req = Request(full_url, headers={"User-Agent": "FlareTrack/1.0"})
            with urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (URLError, HTTPError, json.JSONDecodeError, OSError):
            return None

    # =========================================================
    # API FETCHERS
    # =========================================================

    def _fetch_weather(self, lat: float, lon: float) -> Dict[str, Any]:
        data = self._get_json(WEATHER_API, {
            "latitude":         str(lat),
            "longitude":        str(lon),
            "current":          ",".join([
                "temperature_2m", "relative_humidity_2m", "surface_pressure",
                "uv_index", "wind_speed_10m", "weather_code",
            ]),
            "temperature_unit": "fahrenheit",
            "wind_speed_unit":  "mph",
            "timezone":         "auto",
        })
        if data is None:
            return {}
        cur  = data.get("current", {})
        code = cur.get("weather_code")
        return {
            "temperature_f":           cur.get("temperature_2m"),
            "humidity_percent":        cur.get("relative_humidity_2m"),
            "barometric_pressure_hpa": cur.get("surface_pressure"),
            "uv_index":                cur.get("uv_index"),
            "wind_speed_mph":          cur.get("wind_speed_10m"),
            "weather":                 _WMO.get(code, f"Code {code}") if code is not None else None,
        }

    def _fetch_air_quality(self, lat: float, lon: float) -> Dict[str, Any]:
        data = self._get_json(AQI_API, {
            "latitude":  str(lat),
            "longitude": str(lon),
            "current":   ",".join([
                "us_aqi", "pm2_5", "pm10", "european_aqi",
                "alder_pollen", "birch_pollen", "grass_pollen",
                "mugwort_pollen", "olive_pollen", "ragweed_pollen",
            ]),
            "timezone":  "auto",
        })
        if data is None:
            return {}
        cur = data.get("current", {})
        # Pollen fields are only populated in Europe; take max of available values
        pollen_vals = [
            cur.get("alder_pollen"),  cur.get("birch_pollen"),
            cur.get("grass_pollen"),  cur.get("mugwort_pollen"),
            cur.get("olive_pollen"),  cur.get("ragweed_pollen"),
        ]
        available = [v for v in pollen_vals if v is not None]
        return {
            "air_quality_index": cur.get("us_aqi"),
            "pm25":              cur.get("pm2_5"),
            "pm10":              cur.get("pm10"),
            "european_aqi":      cur.get("european_aqi"),
            "pollen_index":      max(available) if available else None,
        }

    def _fetch_pollen_tomorrow(self, lat: float, lon: float) -> Dict[str, Any]:
        """Fetch tree, grass, and weed pollen indices from Tomorrow.io.

        Pollen index scale: 0=None, 1=Very Low, 2=Low, 3=Medium, 4=High, 5=Very High.
        Returns an empty dict — without raising — if the key is absent, the
        request fails, or the response shape is unexpected.
        """
        # Re-check at call time so a config file created after import is found.
        key = TOMORROW_API_KEY or _load_api_key("TOMORROW_API_KEY")
        if not key:
            return {}

        data = self._get_json(TOMORROW_API, {
            "location": f"{lat},{lon}",
            "fields":   "treeIndex,grassIndex,weedIndex",
            "units":    "metric",
            "apikey":   key,
        })
        if data is None:
            return {}

        try:
            values = data["data"]["values"]
        except (KeyError, TypeError):
            return {}

        result: Dict[str, Any] = {}
        for src_key, dst_key in (
            ("treeIndex",  "pollen_tree_index"),
            ("grassIndex", "pollen_grass_index"),
            ("weedIndex",  "pollen_weed_index"),
        ):
            val = values.get(src_key)
            if val is not None:
                result[dst_key] = val

        if result:
            result["pollen_source"] = "tomorrow.io"

        return result

    # =========================================================
    # PUBLIC API
    # =========================================================

    def fetch(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Return a snapshot dict for the patient's location.
        Serves from local cache when available and not stale (< 1 hour old)."""
        date_str = date_str or datetime.now().date().isoformat()

        cached = self._load_cache(date_str)
        if cached is not None:
            return cached

        if not self.has_location():
            return {"error": "No location saved — add coordinates in menu option 9."}

        lat, lon = self.patient.latitude, self.patient.longitude

        weather = self._fetch_weather(lat, lon)
        if not weather:
            return {"error": "Could not reach Open-Meteo weather API. Check your connection."}

        time.sleep(REQUEST_DELAY)
        aqi = self._fetch_air_quality(lat, lon)

        time.sleep(REQUEST_DELAY)
        pollen = self._fetch_pollen_tomorrow(lat, lon)

        snapshot = {
            "fetched_at": datetime.now().isoformat(),
            "latitude":   lat,
            "longitude":  lon,
            **weather,
            **aqi,
            **pollen,  # pollen_tree_index/grass/weed + pollen_source (empty if key missing)
        }
        self._save_cache(date_str, snapshot)
        return snapshot

    def fetch_and_merge(self, date_str: str) -> Dict[str, Any]:
        """Fetch snapshot and merge into the day's EnvironmentalEntry.

        Fill-in semantics: snapshot values only overwrite EnvironmentalEntry
        fields that are currently None, so manually logged values are never
        clobbered.  Extended fields (UV, wind, PM2.5, pollen …) always go
        into custom_factors so they reach extract_features() correlations.
        """
        snapshot = self.fetch(date_str)
        if "error" in snapshot:
            print(f"[Snapshot] {snapshot['error']}")
            return snapshot

        env = self.storage.load_environment(date_str) or EnvironmentalEntry()

        # Standard EnvironmentalEntry fields: fill only if unset
        if env.temperature_f           is None:
            env.temperature_f           = snapshot.get("temperature_f")
        if env.humidity_percent        is None:
            env.humidity_percent        = snapshot.get("humidity_percent")
        if env.air_quality_index       is None:
            env.air_quality_index       = snapshot.get("air_quality_index")
        if env.barometric_pressure_hpa is None:
            env.barometric_pressure_hpa = snapshot.get("barometric_pressure_hpa")

        # Extended snapshot fields always written to custom_factors
        has_tomorrow_pollen = snapshot.get("pollen_source") == "tomorrow.io"
        extras = {
            "weather":            snapshot.get("weather"),
            "uv_index":           snapshot.get("uv_index"),
            "wind_speed_mph":     snapshot.get("wind_speed_mph"),
            "pm25":               snapshot.get("pm25"),
            "pm10":               snapshot.get("pm10"),
            "pollen_index":       snapshot.get("pollen_index"),       # Open-Meteo grains/m³, Europe only
            "european_aqi":       snapshot.get("european_aqi"),
            "pollen_tree_index":  snapshot.get("pollen_tree_index"),  # Tomorrow.io 0-5 scale
            "pollen_grass_index": snapshot.get("pollen_grass_index"),
            "pollen_weed_index":  snapshot.get("pollen_weed_index"),
            "pollen_source":      snapshot.get("pollen_source"),
            "snapshot_at":        snapshot["fetched_at"],
            "snapshot_source":    "open-meteo + tomorrow.io" if has_tomorrow_pollen else "open-meteo",
        }
        env.custom_factors.update({k: v for k, v in extras.items() if v is not None})

        self.storage.save_environment(env, date_str)

        pollen_str = ""
        if has_tomorrow_pollen:
            pollen_str = (
                f", Pollen T:{snapshot['pollen_tree_index']}"
                f"/G:{snapshot['pollen_grass_index']}"
                f"/W:{snapshot['pollen_weed_index']} (0-5)"
            )
        print(
            f"[Snapshot] {snapshot.get('weather', 'N/A')}, "
            f"{snapshot.get('temperature_f', '?')}°F, "
            f"AQI {snapshot.get('air_quality_index', '?')}, "
            f"{snapshot.get('barometric_pressure_hpa', '?')} hPa"
            f"{pollen_str}"
        )
        return snapshot

    # =========================================================
    # CACHE UTILITIES
    # =========================================================

    def cache_stats(self) -> Dict[str, Any]:
        files      = [f for f in os.listdir(self.cache_dir) if f.endswith(".json")]
        total_size = sum(
            os.path.getsize(os.path.join(self.cache_dir, f)) for f in files
        )
        return {
            "cache_dir":      self.cache_dir,
            "cached_days":    len(files),
            "total_size_kb":  round(total_size / 1024, 1),
            "ttl_hours":      CACHE_TTL_H,
        }
