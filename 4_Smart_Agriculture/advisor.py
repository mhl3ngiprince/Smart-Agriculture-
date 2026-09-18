"""Agronomy rule engine: sensor frame -> alerts, actions and irrigation advice.

Rules are pure functions of the reading dict, so they are trivially testable.
Severity is one of: ``ok``, ``info``, ``warning``, ``critical``.
"""
from __future__ import annotations

from config import MOISTURE_MAX, MOISTURE_MIN, RAIN_SKIP_MM


def _num(r, key):
    v = r.get(key)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# Each rule: (predicate, kind, message, severity)
RULES = [
    (lambda r: _num(r, "soil_moisture") is not None and _num(r, "soil_moisture") < MOISTURE_MIN,
     "LOW_MOISTURE", "Irrigate - soil moisture below threshold (target 40-60%).", "warning"),
    (lambda r: _num(r, "soil_moisture") is not None and _num(r, "soil_moisture") > MOISTURE_MAX,
     "WATERLOG", "Stop irrigation; check drainage - root/rot risk.", "critical"),
    (lambda r: _num(r, "temperature") is not None and _num(r, "temperature") > 33,
     "HEAT_STRESS", "Heat stress: shade nets + evening irrigation.", "warning"),
    (lambda r: _num(r, "temperature") is not None and _num(r, "temperature") > 40,
     "EXTREME_HEAT", "Extreme heat - protect crops and workers, irrigate at dusk.", "critical"),
    (lambda r: _num(r, "temperature") is not None and _num(r, "temperature") < 5,
     "FROST", "Frost risk: row covers / sprinkler frost control.", "critical"),
    (lambda r: _num(r, "ph") is not None and _num(r, "ph") < 6.0,
     "ACID_SOIL", "Apply agricultural lime to raise pH.", "info"),
    (lambda r: _num(r, "ph") is not None and _num(r, "ph") > 7.5,
     "ALKALINE_SOIL", "Apply elemental sulfur to acidify.", "info"),
    (lambda r: _num(r, "nitrogen") is not None and _num(r, "nitrogen") < 40,
     "LOW_N", "Apply nitrogen fertiliser per soil test.", "warning"),
    (lambda r: _num(r, "phosphorus") is not None and _num(r, "phosphorus") < 20,
     "LOW_P", "Apply DAP / rock phosphate.", "warning"),
    (lambda r: _num(r, "potassium") is not None and _num(r, "potassium") < 25,
     "LOW_K", "Apply potassium (muriate of potash).", "warning"),
    (lambda r: _num(r, "humidity") is not None and _num(r, "humidity") > 85,
     "HIGH_HUMIDITY", "High humidity - fungal disease risk, monitor closely.", "warning"),
]


def evaluate(reading: dict) -> list[dict]:
    """Return a list of {kind, message, severity} dicts for the reading."""
    alerts = [{"kind": k, "message": m, "severity": sev}
              for cond, k, m, sev in RULES if _safe(cond, reading)]
    aqua_missing = _num(reading, "soil_moisture") is None
    if not alerts and not aqua_missing:
        alerts.append({"kind": "OK",
                       "message": "All parameters within agronomic thresholds.",
                       "severity": "ok"})
    return alerts


def _safe(cond, reading):
    try:
        return bool(cond(reading))
    except Exception:
        return False


def wants_irrigation(reading: dict, rain_forecast_mm: float = 0.0) -> dict:
    """Decide whether irrigation should run, and why.

    Returns {"irrigate": bool, "reason": str, "minutes": int}.  Irrigation is
    skipped when meaningful rain is forecast (rain-aware scheduling).
    """
    from config import MOISTURE_TARGET, PUMP_RUNTIME_MIN
    moisture = _num(reading, "soil_moisture")
    if moisture is None:
        return {"irrigate": False, "reason": "no soil-moisture sensor", "minutes": 0}
    if moisture > MOISTURE_MAX:
        return {"irrigate": False, "reason": "soil is waterlogged", "minutes": 0}
    if moisture >= MOISTURE_TARGET:
        return {"irrigate": False,
                "reason": f"moisture {moisture:.0f}% at/above target", "minutes": 0}
    if rain_forecast_mm >= RAIN_SKIP_MM:
        return {"irrigate": False,
                "reason": f"{rain_forecast_mm:.1f} mm rain forecast - holding off",
                "minutes": 0}
    # scale runtime with how dry we are (deficit-based)
    deficit = (MOISTURE_TARGET - moisture) / MOISTURE_TARGET
    minutes = int(max(5, round(PUMP_RUNTIME_MIN * (0.5 + deficit))))
    return {"irrigate": True,
            "reason": f"moisture {moisture:.0f}% below target {MOISTURE_TARGET:.0f}%",
            "minutes": minutes}
