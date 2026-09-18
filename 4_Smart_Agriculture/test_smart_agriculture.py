"""Tests for the Smart Agriculture system - run with:  pytest -q"""
import tempfile

import pytest

import advisor
import database as db
import irrigation
import pipeline as ingest_mod


@pytest.fixture()
def conn():
    return db.get_conn(tempfile.mktemp(suffix=".db"))


HEALTHY = {"device_id": "d1", "soil_moisture": 52, "temperature": 24,
           "humidity": 55, "ph": 6.6, "nitrogen": 60, "phosphorus": 35,
           "potassium": 40}
DRY = {"device_id": "d1", "soil_moisture": 22, "temperature": 37,
       "humidity": 40, "ph": 5.6, "nitrogen": 30, "phosphorus": 15,
       "potassium": 20}


# ------------------------------------------------------------------ rules ----
def test_healthy_frame_is_ok():
    alerts = advisor.evaluate(HEALTHY)
    assert alerts[0]["kind"] == "OK"


def test_dry_frame_triggers_expected_alerts():
    kinds = {a["kind"] for a in advisor.evaluate(DRY)}
    assert {"LOW_MOISTURE", "HEAT_STRESS", "ACID_SOIL", "LOW_N"} <= kinds


def test_waterlog_critical():
    kinds = {a["kind"]: a["severity"] for a in advisor.evaluate(
        {**HEALTHY, "soil_moisture": 95})}
    assert kinds.get("WATERLOG") == "critical"


def test_frost_critical():
    kinds = {a["kind"]: a["severity"] for a in advisor.evaluate(
        {**HEALTHY, "temperature": 1})}
    assert kinds.get("FROST") == "critical"


def test_missing_sensor_values_do_not_crash():
    advisor.evaluate({"device_id": "x", "soil_moisture": "not-a-number"})


# ------------------------------------------------------------ irrigation -----
def test_irrigation_holds_when_wet():
    d = advisor.wants_irrigation({**HEALTHY, "soil_moisture": 70})
    assert d["irrigate"] is False


def test_irrigation_runs_when_dry():
    d = advisor.wants_irrigation({**HEALTHY, "soil_moisture": 20})
    assert d["irrigate"] is True and d["minutes"] > 0


def test_irrigation_skipped_for_forecast_rain():
    d = advisor.wants_irrigation({**HEALTHY, "soil_moisture": 20},
                                 rain_forecast_mm=10)
    assert d["irrigate"] is False
    assert "rain" in d["reason"].lower()


def test_irrigation_cooldown(conn):
    db.register_device(conn, "d1")
    db.log_irrigation(conn, "d1", "START_IRRIGATION", 20, "test")
    decision = irrigation.decide(conn, DRY)
    assert decision["irrigate"] is False
    assert "cooldown" in decision["reason"]


# --------------------------------------------------------------- ingest ------
def test_ingest_stores_and_alerts(conn):
    r = ingest_mod.ingest(conn, DRY, publisher=None)
    assert r["stored"] is True
    s = db.summary(conn)
    assert s["readings"] == 1 and s["alerts"] >= 4
    assert s["devices"] == 1


def test_ingest_rejects_garbage(conn):
    r = ingest_mod.ingest(conn, {"foo": 1}, publisher=None)
    assert r["stored"] is False


def test_ingest_publishes_command(conn):
    published = []
    ingest_mod.ingest(conn, DRY, publisher=lambda t, p: published.append((t, p)))
    assert published, "an irrigation command should be published"
    assert "START_IRRIGATION" in published[0][1]


def test_actuator_state_recorded(conn):
    ingest_mod.ingest(conn, DRY, publisher=None)
    states = db.actuator_states(conn, "d1")
    assert states and states[0]["name"] == "pump"


def test_export_csv(conn):
    ingest_mod.ingest(conn, HEALTHY, publisher=None)
    path = db.export_csv(conn, out_dir=tempfile.mkdtemp())
    assert path.endswith(".csv")


# --------------------------------------------------------- weather module ----
def test_weather_returns_dict_or_none():
    import weather
    fc = weather.get_forecast()
    assert fc is None or "rain_next_mm" in fc
