"""Konstanter för SG Ready-integrationen."""

DOMAIN = "sgready"

# Standardvärden
DEFAULT_BOOST_PCT = 15       # % billigaste timmar → boost
DEFAULT_BLOCK_PCT = 50       # % dyraste timmar → block
DEFAULT_MIN_TEMP = 20.0      # Mintemperatur (C) — håll alltid minst normal
DEFAULT_MQTT_TOPIC = "homeassistant/sgready/control"
DEFAULT_PRICE_ENTITY = "sensor.nordpool_kwh_se4_sek_3"

# Lägen
MODE_BOOST = "boost"
MODE_NORMAL = "normal"
MODE_BLOCK = "block"

# Config-nycklar
CONF_MQTT_TOPIC = "mqtt_topic"
CONF_PRICE_ENTITY = "price_entity"
CONF_TEMP_ENTITY = "temp_entity"
CONF_BOOST_PCT = "boost_pct"
CONF_BLOCK_PCT = "block_pct"
CONF_MIN_TEMP = "min_temp"

# Entitets-ID:n
SENSOR_MODE = "mode"
SENSOR_PRICE = "current_price"
SENSOR_RANK = "price_rank"
NUMBER_BOOST_PCT = "boost_percent"
NUMBER_BLOCK_PCT = "block_percent"
NUMBER_MIN_TEMP = "min_temp"
SWITCH_OVERRIDE = "boost_override"
