"""FastAPI service for the farm: HTTP ingest + dashboard API.

Run:  python monitor.py api      (docs at http://localhost:8004/docs)

Devices POST readings to ``/ingest``; a dashboard reads ``/dashboard``.
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import database as db
import pipeline as ingest_mod
import weather
from config import DEVICE_TOKEN, LATITUDE, LONGITUDE

app = FastAPI(title="Smart Agriculture API", version="2.0.0")


class Reading(BaseModel):
    device_id: Optional[str] = "unknown"
    plot: Optional[str] = None
    crop: Optional[str] = None
    soil_moisture: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    ph: Optional[float] = None
    nitrogen: Optional[float] = None
    phosphorus: Optional[float] = None
    potassium: Optional[float] = None
    soil_temp: Optional[float] = None
    light: Optional[float] = None
    rainfall: Optional[float] = None


def _auth(token: Optional[str]):
    if DEVICE_TOKEN and token != DEVICE_TOKEN:
        raise HTTPException(status_code=401, detail="Bad or missing device token")


@app.get("/health")
def health():
    return {"status": "ok", "db": db.summary(db.get_conn())}


@app.post("/ingest")
def ingest(body: Reading, x_device_token: Optional[str] = Header(default=None)):
    """Devices POST a reading here (alternative to MQTT)."""
    _auth(x_device_token)
    conn = db.get_conn()
    # publish to MQTT if a broker is reachable, but never fail ingest because of it
    result = ingest_mod.ingest(conn, body.model_dump(), publisher=_maybe_publisher())
    if not result.get("stored"):
        raise HTTPException(status_code=422, detail=result.get("error"))
    return result


def _maybe_publisher():
    try:
        import paho.mqtt.client as mqtt
        from config import (MQTT_HOST, MQTT_PASS, MQTT_PORT, MQTT_USER)
        c = mqtt.Client(client_id="farm-api-pub")
        if MQTT_USER:
            c.username_pw_set(MQTT_USER, MQTT_PASS)
        c.connect(MQTT_HOST, MQTT_PORT, 5)
        c.loop_start()
        return c.publish
    except Exception:
        return None


@app.get("/readings")
def readings(limit: int = 50, device_id: Optional[str] = None):
    return {"readings": db.readings(db.get_conn(), limit, device_id)}


@app.get("/alerts")
def alerts(limit: int = 30):
    return {"alerts": db.recent_alerts(db.get_conn(), limit)}


@app.get("/actuators")
def actuators(device_id: Optional[str] = None):
    return {"actuators": db.actuator_states(db.get_conn(), device_id)}


@app.get("/devices")
def devices():
    return {"devices": db.devices(db.get_conn())}


@app.get("/weather")
def get_weather():
    return {"forecast": weather.get_forecast(LATITUDE, LONGITUDE)}


@app.post("/devices")
def register(body: Reading):
    conn = db.get_conn()
    db.register_device(conn, body.device_id, body.plot, body.crop)
    return {"ok": True, "device_id": body.device_id}


@app.get("/export")
def export():
    return {"csv": db.export_csv(db.get_conn())}


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Server-rendered dashboard (no emoji; real data only)."""
    import dashboard as dash
    return dash.render(db.get_conn())
