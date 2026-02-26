"""Konfigurationsflöde för SG Ready."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_MQTT_TOPIC, CONF_MQTT_AI_TOPIC,
    CONF_NORDPOOL_CONFIG_ENTRY, CONF_NORDPOOL_AREA,
    CONF_TEMP_ENTITY, CONF_TARIFF_ENTITY,
    CONF_GRID_POWER_ENTITY, CONF_PROD_ENABLED,
    CONF_BOOST_PCT, CONF_BLOCK_PCT, CONF_MIN_TEMP,
    DEFAULT_MQTT_TOPIC, DEFAULT_MQTT_AI_TOPIC,
    DEFAULT_BOOST_PCT, DEFAULT_BLOCK_PCT, DEFAULT_MIN_TEMP,
)


def _nordpool_entries(hass) -> list[dict]:
    """Hitta alla installerade Nord Pool-integrationer."""
    entries = []
    for entry in hass.config_entries.async_entries("nordpool"):
        area = entry.data.get("area", "?")
        if not area or area == "?":
            areas = entry.data.get("areas", [])
            area = areas[0] if areas else "?"
        entries.append({
            "value": entry.entry_id,
            "label": f"Nord Pool – {area} ({entry.entry_id[:8]}…)",
        })
    return entries


class SGReadyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        nordpool_entries = _nordpool_entries(self.hass)
        if not nordpool_entries:
            return self.async_abort(reason="nordpool_not_found")

        if user_input is not None:
            return self.async_create_entry(title="SG Ready Styrning", data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_NORDPOOL_CONFIG_ENTRY, default=nordpool_entries[0]["value"]): selector.selector({
                "select": {
                    "options": nordpool_entries,
                    "mode": "dropdown",
                }
            }),
            vol.Required(CONF_NORDPOOL_AREA, default="SE4"): selector.selector({
                "select": {
                    "options": ["SE1", "SE2", "SE3", "SE4"],
                    "mode": "dropdown",
                }
            }),
            vol.Required(CONF_MQTT_TOPIC, default=DEFAULT_MQTT_TOPIC): str,
            vol.Optional(CONF_MQTT_AI_TOPIC, default=DEFAULT_MQTT_AI_TOPIC): str,
            vol.Optional(CONF_TEMP_ENTITY, default=""): selector.selector({
                "entity": {"domain": "sensor", "device_class": "temperature"},
            }),
            vol.Optional(CONF_GRID_POWER_ENTITY, default=""): selector.selector({
                "entity": {"domain": "sensor", "device_class": "power"},
            }),
            vol.Optional(CONF_TARIFF_ENTITY, default=""): selector.selector({
                "entity": {"domain": ["sensor", "input_select", "select"]},
            }),
            vol.Optional(CONF_PROD_ENABLED, default=True): bool,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
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
            vol.Optional(CONF_MQTT_AI_TOPIC, default=d.get(CONF_MQTT_AI_TOPIC, DEFAULT_MQTT_AI_TOPIC)): str,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
