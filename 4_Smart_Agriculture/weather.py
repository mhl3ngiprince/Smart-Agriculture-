"""Real weather + short-term forecast via Open-Meteo (free, no API key).

Used to make irrigation *rain-aware*: if meaningful rain is forecast in the
look-ahead window the controller holds off. If the network is down the module
returns None and the controller simply proceeds without the forecast.
"""
from __future__ import annotations

import json
from typing import Optional

from config import LATITUDE, LONGITUDE, RAIN_LOOKAHEAD_HOURS, WEATHER_ENABLED

_API = "https://api.open-meteo.com/v1/forecast"


def get_forecast(lat: float = LATITUDE, lon: float = LONGITUDE,
                 hours: int = RAIN_LOOKAHEAD_HOURS) -> Optional[dict]:
    """Return {temp_c, rain_next_mm, rain_next_hours, humidity, raw} or None."""
    if not WEATHER_ENABLED:
        return None
    try:
        import requests
        r = requests.get(_API, params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,precipitation",
            "hourly": "precipitation",
            "forecast_days": 2,
            "timezone": "auto",
        }, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    cur = data.get("current", {})
    hourly = data.get("hourly", {})
    precip = hourly.get("precipitation", [])[:hours] or []
    rain_next = sum(float(p or 0) for p in precip)
    return {
        "temp_c": cur.get("temperature_2m"),
        "humidity": cur.get("relative_humidity_2m"),
        "rain_next_mm": round(rain_next, 2),
        "rain_next_hours": hours,
        "raw": json.dumps({k: data.get(k) for k in ("current",)}),
    }


def rain_next_mm(lat: float = LATITUDE, lon: float = LONGITUDE) -> float:
    fc = get_forecast(lat, lon)
    return float(fc["rain_next_mm"]) if fc else 0.0
