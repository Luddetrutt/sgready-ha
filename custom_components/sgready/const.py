"""Konstanter för SG Ready-integrationen."""

DOMAIN = "sgready"

# Standardvärden
DEFAULT_BOOST_PCT = 30
DEFAULT_BLOCK_PCT = 30
DEFAULT_MIN_TEMP = 20.0
DEFAULT_MQTT_TOPIC = "homeassistant/sgready/control"
DEFAULT_MQTT_AI_TOPIC = "homeassistant/sgready/ai_command"
DEFAULT_PERSPECTIVE_HOURS = 24

# Algoritm-konstanter
MIN_SPREAD_TO_ACT = 0.10
PRICE_ROUND_TO = 0.10
EXTREME_LOW = 0.10
EXTREME_HIGH = 5.0

# Lägen
MODE_BOOST = "boost"
MODE_NORMAL = "normal"
MODE_BLOCK = "block"

# AI Override-lägen
AI_MODE_AUTO = "auto"
AI_MODE_FORCE_BOOST = "force_boost"
AI_MODE_FORCE_NORMAL = "force_normal"
AI_MODE_FORCE_BLOCK = "force_block"
AI_MODES = [AI_MODE_AUTO, AI_MODE_FORCE_BOOST, AI_MODE_FORCE_NORMAL, AI_MODE_FORCE_BLOCK]

# Config-nycklar
CONF_MQTT_TOPIC = "mqtt_topic"
CONF_MQTT_AI_TOPIC = "mqtt_ai_topic"
CONF_NORDPOOL_CONFIG_ENTRY = "nordpool_config_entry"
CONF_NORDPOOL_AREA = "nordpool_area"
CONF_TEMP_ENTITY = "temp_entity"
CONF_BOOST_PCT = "boost_pct"
CONF_BLOCK_PCT = "block_pct"
CONF_MIN_TEMP = "min_temp"

# Entitets-ID:n
SENSOR_MODE = "mode"
SENSOR_PRICE = "current_price"
SENSOR_RANK = "price_percentile"
NUMBER_BOOST_PCT = "boost_percent"
NUMBER_BLOCK_PCT = "block_percent"
NUMBER_MIN_TEMP = "min_temp"
SWITCH_OVERRIDE = "boost_override"
SELECT_AI_OVERRIDE = "ai_override"
TEXT_AI_REASON = "ai_reason"
DATETIME_AI_UNTIL = "ai_override_until"
