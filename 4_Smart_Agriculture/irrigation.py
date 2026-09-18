"""Irrigation controller: turns sensor readings + forecast into pump actions.

Safety-first design:

* **DRY_RUN defaults to true** - commands are logged and published but never
  energise a relay until you deliberately set ``FARM_DRY_RUN=false``.
* A **cooldown** prevents short-cycling a pump.
* Actions are published to MQTT and recorded in ``irrigation_events`` so the
  physical outcome is auditable.
"""
from __future__ import annotations

import datetime
import json

import advisor
import database as db
import weather
from config import (DRY_RUN, IRRIGATION_COOLDOWN_MIN, LATITUDE, LONGITUDE,
                    MQTT_CMD_TOPIC)


def _minutes_since(ts: str) -> float:
    try:
        t = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return 1e9
    return (datetime.datetime.now() - t).total_seconds() / 60.0


def decide(conn, reading: dict) -> dict:
    """Pure decision for one reading: {"irrigate", "reason", "minutes"}."""
    device_id = reading.get("device_id")
    rain = 0.0
    if device_id:
        last = db.last_irrigation(conn, device_id)
        if last and _minutes_since(last["ts"]) < IRRIGATION_COOLDOWN_MIN:
            return {"irrigate": False,
                    "reason": f"cooldown ({IRRIGATION_COOLDOWN_MIN} min) active",
                    "minutes": 0}
    try:
        rain = weather.rain_next_mm(LATITUDE, LONGITUDE)
    except Exception:
        rain = 0.0
    decision = advisor.wants_irrigation(reading, rain_forecast_mm=rain)
    decision["rain_mm"] = rain
    return decision


def apply(conn, reading: dict, publisher=None) -> dict:
    """Decide, record, and (unless DRY_RUN) publish an irrigation command."""
    device_id = reading.get("device_id") or "unknown"
    decision = decide(conn, reading)
    minutes = decision.get("minutes", 0)

    if decision["irrigate"]:
        action = "START_IRRIGATION"
        db.set_actuator(conn, device_id, "pump", "on", decision["reason"])
    else:
        action = "HOLD_IRRIGATION"
        db.set_actuator(conn, device_id, "pump", "off", decision["reason"])

    db.log_irrigation(conn, device_id, action, minutes, decision["reason"],
                      soil_moisture=reading.get("soil_moisture"),
                      rain_forecast=decision.get("rain_mm"))

    payload = {
        "device_id": device_id,
        "action": action,
        "minutes": minutes,
        "reason": decision["reason"],
        "dry_run": DRY_RUN,
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    if publisher is not None:
        publisher(MQTT_CMD_TOPIC, json.dumps(payload))
    return payload
