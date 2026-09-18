# 4 · Smart Agriculture - Real Ingest, Rain-Aware Irrigation, Live Dashboard

An end-to-end farm monitoring and control system. Real field nodes send real
sensor frames over **MQTT** or **HTTP**; the system stores them, runs agronomy
rules, raises alerts, and makes **rain-aware irrigation decisions** that are
published back to the field hardware.

**No simulated data path.** The only "fake" mode is an explicit `simulate`
command for bench-testing the logic, and irrigation is **dry-run by default**
so it can never accidentally energise a real relay.

## What's real here

| Concern | What this does |
|--------|-----------------|
| Ingest | MQTT subscriber (auto-reconnect, TLS, auth) **and** an HTTP `/ingest` endpoint for Wi-Fi/LoRa gateways |
| Weather | Real **Open-Meteo** forecast (free, no key) used to skip irrigation when rain is coming |
| Rules | Drought, waterlogging, heat/extreme heat, frost, pH, N/P/K, high-humidity disease risk - with severities |
| Irrigation | Deficit-based runtime, **pump cooldown** to prevent short-cycling, **dry-run safety**, commands published to MQTT and logged |
| Alerts | Console + **webhook** (HTTP POST) + optional **email** (SMTP) |
| Actuators | Pump/valve state tracked per device with reasons |
| Devices | Multi-device / multi-plot registry |
| Interfaces | REST API **and** a live browser dashboard |
| Reporting | Recent readings, alerts, actuator state, CSV export |
| Tests | `pytest` suite for rules, irrigation, ingest, cooldown, export |

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env            # point at your broker / set lat+lon

python monitor.py selftest      # verify the whole logic offline
python monitor.py simulate      # push healthy + drought frames through it
python monitor.py report        # readings, alerts, actuator state
python monitor.py api           # dashboard + HTTP ingest at :8004
python monitor.py monitor       # run against a real MQTT broker
```

### Field device -> MQTT
```bash
mosquitto_pub -h localhost -t farm/sensors -m \
 '{"device_id":"node-01","plot":"north","crop":"maize",
   "soil_moisture":28,"temperature":36,"humidity":44,"ph":5.4,
   "nitrogen":30,"phosphorus":25,"potassium":40}'
```
The controller replies on `farm/commands` with its irrigation decision.

### Field device -> HTTP
```bash
curl -X POST http://localhost:8004/ingest -H "Content-Type: application/json" \
 -d '{"device_id":"node-01","soil_moisture":28,"temperature":36,
      "humidity":44,"ph":5.4,"nitrogen":30,"phosphorus":25,"potassium":40}'
```

## REST API / dashboard
| Method | Path | Purpose |
|-------|------|---------|
| POST | `/ingest` | device reading (drives rules + irrigation) |
| GET  | `/readings` · `/alerts` · `/actuators` · `/devices` | dashboard data |
| GET  | `/weather` | live forecast |
| GET  | `/export` | CSV of readings |
| GET  | `/` | live HTML dashboard |

## Going live with real relays
1. Wire the pump/valve relay to an ESP32 that subscribes to `farm/commands`.
2. Set `FARM_DRY_RUN=false` **only after** testing in dry-run.
3. Tune `FARM_MOISTURE_TARGET`, `FARM_PUMP_MINUTES`, `FARM_IRRIG_COOLDOWN`
   and `FARM_RAIN_SKIP_MM` for your crop and soil.

## Tables
`devices` · `readings` · `alerts` · `recommendations` · `actuators` ·
`irrigation_events` · `weather`

> Safety: irrigation controls real water and power. Keep the cooldown and a
> hardwired emergency stop; never let software be the only protection.

## Web dashboard

Every project ships a server-rendered **web dashboard** (a real HTML page).

* **No emoji** ? all icons are inline **SVG** (defined in `../_shared/dashboard_kit.py`).
* **Real data only** ? every card is labelled with its data source, and the
  page reads the same SQLite tables the pipeline writes.
* **No CDN / no JavaScript required** ? charts are plain inline SVG.

Open it by running the project's API and visiting `/dashboard`:

    python <api-entrypoint>            # start the service
    # then open http://127.0.0.1:<port>/dashboard

## Data integrity (no fake data)

This project contains **no simulated or derived sensor values**.

* `readings` holds **real device telemetry only** ? rows arrive from a real
  MQTT broker or the HTTP `/ingest` endpoint.
* Weather lives in a **separate** `weather_daily` table and is clearly labelled
  as observed weather (Open-Meteo ERA5). It is never mixed into `readings`.
* The dashboard labels every card with its source, so a modelled value can
  never be mistaken for a measurement.

Sync real weather:

    python weather_sync.py --start 2024-01-01 --end 2024-12-31
    python weather_sync.py --recent
