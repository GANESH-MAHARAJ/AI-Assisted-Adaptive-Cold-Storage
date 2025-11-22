import os

from datetime import datetime, timezone

SERIAL_PORT = os.getenv("ACS_SERIAL_PORT", "COM7")     # change for Linux: "/dev/ttyACM0"
SERIAL_BAUD = int(os.getenv("ACS_SERIAL_BAUD", "9600"))
SERIAL_READ_INTERVAL_MS = int(os.getenv("ACS_READ_INTERVAL_MS", "2000"))  # Arduino sends every ~2s

# mongo
MONGO_URI = os.getenv("ACS_MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("ACS_MONGO_DB", "adaptive_cold_storage")
MONGO_COLLECTION = os.getenv("ACS_MONGO_COLLECTION", "events")

# agent
OLLAMA_MODEL = os.getenv("ACS_OLLAMA_MODEL", "llama3.1")
AGENT_MAX_TOKENS = int(os.getenv("ACS_AGENT_MAX_TOKENS", "512"))

# safety clamps for PWM & booleans
PWM_MIN, PWM_MAX = 0, 255

# simple sanity ranges for sensors (you can tune)
MAX_TEMP_C = 60.0
MIN_TEMP_C = -10.0
MAX_HUMID = 100.0
MIN_HUMID = 0.0
MAX_CO2 = 20000.0
MAX_ETHYLENE = 1000.0
MAX_WEIGHT = 100000.0  # grams (adjust to your load cell range)
