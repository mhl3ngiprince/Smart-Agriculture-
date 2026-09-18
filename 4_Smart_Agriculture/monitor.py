"""Smart Agriculture - real MQTT + HTTP ingest, irrigation control, alerts.

Ingest paths
------------
* **MQTT** (`monitor` command) - subscribes to a real broker; field nodes
  (ESP32/Arduino/gateways) publish JSON readings; commands are published back.
* **HTTP** (`api` command) - devices that cannot speak MQTT POST JSON instead.

Every frame: validate -> SQLite -> agronomy rules -> alerts/notifications ->
rain-aware irrigation decision -> command published + logged.

Commands
--------
    python monitor.py monitor                 # MQTT subscriber + controller
    python monitor.py simulate                # drive a full frame through the logic
    python monitor.py api                     # HTTP ingest + dashboard API
    python monitor.py report [--csv]          # recent readings + alerts
    python monitor.py devices
    python monitor.py selftest
"""
from __future__ import annotations

import argparse
import json
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import database as db
import pipeline as ingest_mod
from config import (API_HOST, API_PORT, DRY_RUN, MQTT_CLIENT_ID, MQTT_CMD_TOPIC,
                    MQTT_HOST, MQTT_PASS, MQTT_PORT, MQTT_RECONNECT, MQTT_TLS,
                    MQTT_TOPIC, MQTT_USER)


# ----------------------------------------------------------------- MQTT path ---
def cmd_monitor(args):
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        sys.exit("Install: pip install paho-mqtt")

    conn = db.get_conn()
    client = mqtt.Client(client_id=MQTT_CLIENT_ID)

    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    if MQTT_TLS:
        client.tls_set()
    client.reconnect_delay_set(min_delay=1, max_delay=MQTT_RECONNECT)

    def publish(topic, payload):
        client.publish(topic, payload)
        print(f"  -> published to {topic}: {payload[:120]}")

    def on_connect(c, userdata, flags, rc, properties=None):
        if rc == 0:
            print(f"Connected to mqtt://{MQTT_HOST}:{MQTT_PORT}  "
                  f"(subscribing {MQTT_TOPIC})")
            c.subscribe(MQTT_TOPIC)
        else:
            print(f"MQTT connect failed rc={rc}")

    def on_disconnect(c, userdata, rc, properties=None):
        if rc != 0:
            print(f"MQTT disconnected (rc={rc}); auto-reconnecting...")

    def on_message(c, userdata, msg):
        try:
            frame = json.loads(msg.payload.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            print("bad JSON payload:", msg.payload[:120])
            return
        result = ingest_mod.ingest(conn, frame, publisher=publish)
        if not result.get("stored"):
            print("  rejected:", result.get("error"))
            return
        for a in result["alerts"]:
            if a["kind"] != "OK":
                print(f"  [{a['severity']}] {a['kind']}: {a['message']}")
        irr = result.get("irrigation") or {}
        if irr.get("action"):
            print(f"  irrigation: {irr['action']} ({irr['minutes']} min) "
                  f"- {irr['reason']}")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    print(f"Farm controller starting (DRY_RUN={DRY_RUN}).")
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_forever()
        except KeyboardInterrupt:
            print("\nStopping.")
            break
        except Exception as exc:
            print(f"MQTT error: {exc}; retrying in {MQTT_RECONNECT}s")
            time.sleep(MQTT_RECONNECT)


# ----------------------------------------------------------- HTTP/api path ----
def cmd_api(args):
    try:
        import uvicorn
    except ImportError:
        sys.exit("Install API extras: pip install fastapi 'uvicorn[standard]'")
    print(f"Farm API on http://{API_HOST}:{API_PORT}  (docs at /docs)")
    uvicorn.run("farm_api:app", host=API_HOST, port=API_PORT, reload=False)


# --------------------------------------------------------------- simulate ------
def cmd_simulate(args):
    """Push representative frames through the real pipeline (no broker needed)."""
    frame_ok = {"device_id": "sim-01", "plot": "north", "crop": "maize",
                "soil_moisture": 52, "temperature": 24, "humidity": 55,
                "ph": 6.6, "nitrogen": 60, "phosphorus": 35, "potassium": 40}
    frame_dry = {"device_id": "sim-01", "soil_moisture": 22, "temperature": 37,
                 "humidity": 40, "ph": 5.6, "nitrogen": 30, "phosphorus": 15,
                 "potassium": 20}
    print("== Simulating a healthy frame ==")
    r = ingest_mod.ingest(db.get_conn(), frame_ok, publisher=_echo_publish)
    for a in r["alerts"]:
        print("  ", a["severity"], a["kind"], "-", a["message"])
    print("   irrigation:", (r["irrigation"] or {}).get("action"),
          "-", (r["irrigation"] or {}).get("reason"))

    print("== Simulating a dry/heat frame ==")
    r = ingest_mod.ingest(db.get_conn(), frame_dry, publisher=_echo_publish)
    for a in r["alerts"]:
        print("  ", a["severity"], a["kind"], "-", a["message"])
    print("   irrigation:", (r["irrigation"] or {}).get("action"),
          "-", (r["irrigation"] or {}).get("reason"))


def _echo_publish(topic, payload):
    print(f"  -> publish {topic}: {payload}")


# --------------------------------------------------------------- reporting -----
def cmd_report(args):
    conn = db.get_conn()
    print("== Summary ==", db.summary(conn))
    print("\n== Latest readings ==")
    for r in db.readings(conn, limit=10):
        print(f"  {r['ts']} {r['device_id']:<10} "
              f"moisture={r['soil_moisture']} temp={r['temperature']} "
              f"ph={r['ph']}")
    print("\n== Recent alerts ==")
    for a in db.recent_alerts(conn, 15):
        print(f"  {a['ts']} [{a['severity']}] {a['kind']}: {a['message']}")
    print("\n== Actuator state ==")
    for s in db.actuator_states(conn):
        print(f"  {s['device_id']:<10} {s['name']} = {s['state']}  ({s['reason']})")
    if args.csv:
        path = db.export_csv(conn)
        print(f"\nExported readings -> {path}")


def cmd_devices(args):
    conn = db.get_conn()
    for d in db.devices(conn):
        print(f"  {d['device_id']:<12} plot={d['plot']} crop={d['crop']} "
              f"last_seen={d['last_seen']}")
    print("  totals:", db.summary(conn))


# --------------------------------------------------------------- selftest ------
def cmd_selftest(args):
    print("== Self-test ==")
    import tempfile
    conn = db.get_conn(tempfile.mktemp(suffix=".db"))
    frame = {"device_id": "t1", "soil_moisture": 30, "temperature": 36,
             "humidity": 40, "ph": 5.5, "nitrogen": 30, "phosphorus": 15,
             "potassium": 20}
    r = ingest_mod.ingest(conn, frame, publisher=None)
    kinds = {a["kind"] for a in r["alerts"]}
    print("  alerts:", sorted(kinds))
    print("  stored reading id:", r["reading_id"])
    print("  irrigation:", (r["irrigation"] or {}).get("action"))
    s = db.summary(conn)
    print("  summary:", s)
    ok = (r["stored"] and "LOW_MOISTURE" in kinds and "HEAT_STRESS" in kinds
          and s["readings"] == 1 and s["alerts"] >= 4)
    # bad payload rejected
    bad = ingest_mod.ingest(conn, {"foo": 1}, publisher=None)
    ok = ok and not bad["stored"]
    print("  SELFTEST", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


# -------------------------------------------------------------------- main -----
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("monitor").set_defaults(func=cmd_monitor)
    sub.add_parser("simulate").set_defaults(func=cmd_simulate)
    sub.add_parser("api").set_defaults(func=cmd_api)
    r = sub.add_parser("report"); r.add_argument("--csv", action="store_true"); r.set_defaults(func=cmd_report)
    sub.add_parser("devices").set_defaults(func=cmd_devices)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)

    args = p.parse_args(argv)
    if not getattr(args, "cmd", None):
        p.print_help()
        return 0
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
