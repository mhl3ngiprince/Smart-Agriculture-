"""Central configuration for the Smart Agriculture system."""
import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name, default):
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


# ------------------------------------------------------------------- broker ---
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "farm/sensors")            # sensor readings in
MQTT_CMD_TOPIC = os.getenv("MQTT_CMD_TOPIC", "farm/commands")   # actuator commands out
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
MQTT_TLS = _bool("MQTT_TLS", "false")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "smart-agri")
MQTT_RECONNECT = int(os.getenv("MQTT_RECONNECT", "5"))

# ------------------------------------------------------------------- storage --
DB_PATH = os.getenv("FARM_DB_PATH", "farm.db")
EXPORT_DIR = os.getenv("FARM_EXPORT_DIR", "exports")

# ------------------------------------------------------------------ weather ---
# Open-Meteo is free and needs no API key.
WEATHER_ENABLED = _bool("FARM_WEATHER", "true")
LATITUDE = float(os.getenv("FARM_LAT", "-26.2041"))     # default: Johannesburg
LONGITUDE = float(os.getenv("FARM_LON", "28.0473"))
RAIN_LOOKAHEAD_HOURS = int(os.getenv("FARM_RAIN_HOURS", "12"))
RAIN_SKIP_MM = float(os.getenv("FARM_RAIN_SKIP_MM", "2.0"))  # skip irrigation if >= this rain expected

# --------------------------------------------------------------- irrigation ---
# Agronomic irrigation window and per-crop moisture targets.
MOISTURE_MIN = float(os.getenv("FARM_MOISTURE_MIN", "35"))
MOISTURE_MAX = float(os.getenv("FARM_MOISTURE_MAX", "85"))
MOISTURE_TARGET = float(os.getenv("FARM_MOISTURE_TARGET", "50"))
PUMP_RUNTIME_MIN = int(os.getenv("FARM_PUMP_MINUTES", "20"))
IRRIGATION_COOLDOWN_MIN = int(os.getenv("FARM_IRRIG_COOLDOWN", "120"))
DRY_RUN = _bool("FARM_DRY_RUN", "true")   # never energise real relays until you set false

# ------------------------------------------------------------------ alerts ----
ALERT_WEBHOOK = os.getenv("FARM_ALERT_WEBHOOK", "")   # POST alerts as JSON here
ALERT_EMAIL = os.getenv("FARM_ALERT_EMAIL", "")
SMTP_HOST = os.getenv("FARM_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("FARM_SMTP_PORT", "587"))
SMTP_USER = os.getenv("FARM_SMTP_USER", "")
SMTP_PASS = os.getenv("FARM_SMTP_PASS", "")

# --------------------------------------------------------------------- API ----
API_HOST = os.getenv("FARM_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("FARM_API_PORT", "8004"))
DEVICE_TOKEN = os.getenv("FARM_DEVICE_TOKEN", "")   # if set, devices must send it
