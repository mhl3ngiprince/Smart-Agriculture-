"""Shared ingest pipeline.

Both MQTT and HTTP ingestion call :func:`ingest`, so a frame is processed
identically no matter how it arrived: validate -> store -> rules -> alerts ->
irrigation decision -> publish command.
"""
from __future__ import annotations

import datetime

import advisor
import database as db
import irrigation
import notifier

REQUIRED = ("soil_moisture", "temperature", "humidity", "ph",
            "nitrogen", "phosphorus", "potassium")


def validate(frame: dict) -> tuple[bool, str]:
    if not isinstance(frame, dict):
        return False, "payload is not a JSON object"
    if not frame.get("device_id"):
        # allow a default so bench testing is easy
        frame["device_id"] = "unknown"
    present = [k for k in REQUIRED if frame.get(k) is not None]
    if not present:
        return False, "no recognised sensor fields present"
    return True, ""


def ingest(conn, frame: dict, publisher=None, do_irrigation=True) -> dict:
    """Process one sensor frame. Returns a summary dict."""
    ok, err = validate(frame)
    if not ok:
        return {"stored": False, "error": err}

    db.register_device(conn, frame.get("device_id"),
                       plot=frame.get("plot"), crop=frame.get("crop"),
                       lat=frame.get("lat"), lon=frame.get("lon"))
    reading_id = db.add_reading(conn, frame)

    alerts = advisor.evaluate(frame)
    for a in alerts:
        db.add_alert(conn, a["kind"], a["message"], a.get("severity", "info"),
                     reading_id=reading_id, device_id=frame.get("device_id"))
        if a["kind"] != "OK":
            db.add_recommendation(conn, reading_id, a["message"])
            if a.get("severity") in ("warning", "critical"):
                notifier.notify(a, {"reading_id": reading_id, "frame": frame})

    irrigation_result = None
    if do_irrigation:
        irrigation_result = irrigation.apply(conn, frame, publisher=publisher)

    return {
        "stored": True,
        "reading_id": reading_id,
        "alerts": alerts,
        "irrigation": irrigation_result,
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
    }
