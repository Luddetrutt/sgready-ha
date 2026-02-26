"""Konfigurationsflöde för SG Ready."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_MQTT_TOPIC, CONF_MQTT_AI_TOPIC,
    CONF_NORDPOOL_CONFIG_ENTRY, CONF_NORDPOOL_AREA,
    CONF_TEMP_ENTITY, CONF_BOOST_PCT, CONF_BLOCK_PCT, CONF_MIN_TEMP,
    DEFAULT_MQTT_TOPIC, DEFAULT_MQTT_AI_TOPIC,
    DEFAULT_BOOST_PCT, DEFAULT_BLOCK_PCT, DEFAULT_MIN_TEMP,
)

STEP_USER_SCHEMA = vol.Schema({
    vol.Required(CONF_NORDPOOL_CONFIG_ENTRY): str,
    vol.Required(CONF_NORDPOOL_AREA, default="SE4"): str,
    vol.Optional(CONF_TEMP_ENTITY, default=""): str,
    vol.Required(CONF_MQTT_TOPIC, default=DEFAULT_MQTT_TOPIC): str,
    vol.Required(CONF_MQTT_AI_TOPIC, default=DEFAULT_MQTT_AI_TOPIC): str,
    vol.Required(CONF_BOOST_PCT, default=DEFAULT_BOOST_PCT): vol.Coerce(float),
    vol.Required(CONF_BLOCK_PCT, default=DEFAULT_BLOCK_PCT): vol.Coerce(float),
    vol.Required(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
})


class SGReadyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="SG Ready Styrning", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={
                "nordpool_hint": "Hittas under Inställningar → Integrationer → Nord Pool → Konfigurera"
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SGReadyOptionsFlow(config_entry)


class SGReadyOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        d = self._entry.data
        schema = vol.Schema({
            vol.Required(CONF_BOOST_PCT, default=d.get(CONF_BOOST_PCT, DEFAULT_BOOST_PCT)): vol.Coerce(float),
            vol.Required(CONF_BLOCK_PCT, default=d.get(CONF_BLOCK_PCT, DEFAULT_BLOCK_PCT)): vol.Coerce(float),
            vol.Required(CONF_MIN_TEMP, default=d.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)): vol.Coerce(float),
            vol.Required(CONF_MQTT_TOPIC, default=d.get(CONF_MQTT_TOPIC, DEFAULT_MQTT_TOPIC)): str,
            vol.Required(CONF_MQTT_AI_TOPIC, default=d.get(CONF_MQTT_AI_TOPIC, DEFAULT_MQTT_AI_TOPIC)): str,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
