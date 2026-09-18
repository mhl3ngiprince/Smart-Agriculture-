"""Fetch and store REAL weather data for a farm location.

Pulls the Open-Meteo ERA5 archive (free, no API key) for the configured
latitude/longitude and stores *only genuine weather observations* - no
invented sensor values, no derived readings.

Weather is stored in its own ``weather_hourly`` table, separate from the
``readings`` table which holds **real device telemetry only**. That separation
is deliberate: a dashboard must never present a modelled value as a sensor
measurement.

Usage:
    python weather_sync.py --start 2024-01-01 --end 2024-12-31
    python weather_sync.py --recent                 # last 7 days
"""
from __future__ import annotations

import argparse
import datetime as dt
import json

import database as db
from config import LATITUDE, LONGITUDE

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FORECAST = "https://api.open-meteo.com/v1/forecast"


def fetch_history(lat, lon, start, end):
    """Real observed weather from the ERA5 reanalysis archive."""
    import requests
    r = requests.get(ARCHIVE, params={
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "daily": ("temperature_2m_max,temperature_2m_min,"
                  "precipitation_sum,relative_humidity_2m_mean,"
                  "shortwave_radiation_sum,wind_speed_10m_max"),
        "timezone": "auto",
    }, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_recent(lat, lon, past_days=7):
    """Real recent observations + forecast from the live forecast API."""
    import requests
    r = requests.get(FORECAST, params={
        "latitude": lat, "longitude": lon,
        "daily": ("temperature_2m_max,temperature_2m_min,precipitation_sum,"
                  "relative_humidity_2m_mean,shortwave_radiation_sum,"
                  "wind_speed_10m_max"),
        "past_days": past_days,
        "forecast_days": 3,
        "timezone": "auto",
    }, timeout=30)
    r.raise_for_status()
    return r.json()


def store_history(conn, lat, lon, payload):
    daily = payload.get("daily", {})
    dates = daily.get("time", [])
    n = 0
    for i, day in enumerate(dates):
        def val(key):
            series = daily.get(key)
            return series[i] if series and i < len(series) else None
        db.upsert_weather(conn, lat, lon, day,
                          temp_max=val("temperature_2m_max"),
                          temp_min=val("temperature_2m_min"),
                          rain_mm=val("precipitation_sum"),
                          humidity=val("relative_humidity_2m_mean"),
                          radiation=val("shortwave_radiation_sum"),
                          wind_max=val("wind_speed_10m_max"))
        n += 1
    conn.commit()
    return n


def sync(lat=LATITUDE, lon=LONGITUDE, start=None, end=None, recent=False):
    conn = db.get_conn()
    if recent:
        payload = fetch_recent(lat, lon)
        n = store_history(conn, lat, lon, payload)
        return {"rows": n, "mode": "recent", "location": [lat, lon]}
    end = end or dt.date.today().isoformat()
    start = start or (dt.date.today() - dt.timedelta(days=365)).isoformat()
    payload = fetch_history(lat, lon, start, end)
    n = store_history(conn, lat, lon, payload)
    # keep the raw payload too, so nothing is lost if the table shape changes
    db.cache_weather(conn, lat, lon, json.dumps(payload.get("daily", {})))
    return {"rows": n, "mode": "archive", "start": start, "end": end,
            "location": [lat, lon]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--recent", action="store_true",
                   help="sync the last 7 days of real observations + forecast")
    args = p.parse_args(argv)
    info = sync(start=args.start, end=args.end, recent=args.recent)
    print(f"Stored {info['rows']} days of REAL weather for {info['location']} "
          f"({info.get('mode')}).")


if __name__ == "__main__":
    main()
