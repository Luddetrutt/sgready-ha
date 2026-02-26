"""Konfigurationssliders för SG Ready."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN, NUMBER_BOOST_PCT, NUMBER_BLOCK_PCT, NUMBER_MIN_TEMP,
    DEFAULT_PROD_NORMAL_THRESHOLD, DEFAULT_PROD_BOOST_THRESHOLD,
    DEFAULT_PROD_RETURN_THRESHOLD, DEFAULT_PROD_HYSTERESIS,
    DEFAULT_PROD_MIN_DURATION, DEFAULT_PROD_OFF_DELAY,
)
from .coordinator import SGReadyCoordinator


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    coordinator: SGReadyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        # Prisalgoritm
        SGReadyBoostPercent(coordinator, entry),
        SGReadyBlockPercent(coordinator, entry),
        SGReadyMinTemp(coordinator, entry),
        # Production override
        SGReadyProdNormalThreshold(coordinator, entry),
        SGReadyProdBoostThreshold(coordinator, entry),
        SGReadyProdReturnThreshold(coordinator, entry),
        SGReadyProdHysteresis(coordinator, entry),
        SGReadyProdMinDuration(coordinator, entry),
        SGReadyProdOffDelay(coordinator, entry),
    ])


class SGReadyBoostPercent(NumberEntity):
    """Procentandel billigaste timmar som ger boost."""

    _attr_icon = "mdi:arrow-up-bold"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 5
    _attr_native_max_value = 50
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: SGReadyCoordinator, entry):
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_{NUMBER_BOOST_PCT}"
        self._attr_name = "SG Ready Boost-procent"
        self._attr_native_value = coordinator.boost_pct

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.boost_pct = value
        self._attr_native_value = value
        self.async_write_ha_state()
        await self._coordinator.async_refresh()


class SGReadyBlockPercent(NumberEntity):
    """Procentandel dyraste timmar som blockeras."""

    _attr_icon = "mdi:arrow-down-bold"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 10
    _attr_native_max_value = 80
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: SGReadyCoordinator, entry):
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_{NUMBER_BLOCK_PCT}"
        self._attr_name = "SG Ready Block-procent"
        self._attr_native_value = coordinator.block_pct

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.block_pct = value
        self._attr_native_value = value
        self.async_write_ha_state()
        await self._coordinator.async_refresh()


class SGReadyMinTemp(NumberEntity):
    """Mintemperatur — block aktiveras inte om det är kallare."""

    _attr_icon = "mdi:thermometer-low"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 15
    _attr_native_max_value = 25
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: SGReadyCoordinator, entry):
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_{NUMBER_MIN_TEMP}"
        self._attr_name = "SG Ready Mintemperatur"
        self._attr_native_value = coordinator.min_temp

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.min_temp = value
        self._attr_native_value = value
        self.async_write_ha_state()
        await self._coordinator.async_refresh()


# ── Production override sliders ──────────────────────────────────────────────

class SGReadyProdNormalThreshold(NumberEntity):
    """Exportnivå (W) för att gå till normal-läge."""
    _attr_icon = "mdi:solar-power"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = -2000
    _attr_native_max_value = -10
    _attr_native_step = 50
    _attr_native_unit_of_measurement = "W"

    def __init__(self, coordinator: SGReadyCoordinator, entry):
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_prod_normal_threshold"
        self._attr_name = "SG Ready Produktion Normal-tröskel"
        self._attr_native_value = coordinator.prod_normal_threshold

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.prod_normal_threshold = value
        self._attr_native_value = value
        self.async_write_ha_state()


class SGReadyProdBoostThreshold(NumberEntity):
    """Exportnivå (W) för att gå till boost-läge."""
    _attr_icon = "mdi:solar-power-variant"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = -5000
    _attr_native_max_value = -50
    _attr_native_step = 50
    _attr_native_unit_of_measurement = "W"

    def __init__(self, coordinator: SGReadyCoordinator, entry):
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_prod_boost_threshold"
        self._attr_name = "SG Ready Produktion Boost-tröskel"
        self._attr_native_value = coordinator.prod_boost_threshold

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.prod_boost_threshold = value
        self._attr_native_value = value
        self.async_write_ha_state()


class SGReadyProdReturnThreshold(NumberEntity):
    """Importnivå (W) för att deaktivera production override."""
    _attr_icon = "mdi:transmission-tower-import"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 500
    _attr_native_step = 25
    _attr_native_unit_of_measurement = "W"

    def __init__(self, coordinator: SGReadyCoordinator, entry):
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_prod_return_threshold"
        self._attr_name = "SG Ready Produktion Återgångs-tröskel"
        self._attr_native_value = coordinator.prod_return_threshold

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.prod_return_threshold = value
        self._attr_native_value = value
        self.async_write_ha_state()


class SGReadyProdHysteresis(NumberEntity):
    """Hysteres i W för att undvika snabb växling."""
    _attr_icon = "mdi:sine-wave"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 10
    _attr_native_max_value = 300
    _attr_native_step = 10
    _attr_native_unit_of_measurement = "W"

    def __init__(self, coordinator: SGReadyCoordinator, entry):
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_prod_hysteresis"
        self._attr_name = "SG Ready Produktion Hysteres"
        self._attr_native_value = coordinator.prod_hysteresis

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.prod_hysteresis = value
        self._attr_native_value = value
        self.async_write_ha_state()


class SGReadyProdMinDuration(NumberEntity):
    """Minsta tid (s) med överskott innan aktivering."""
    _attr_icon = "mdi:timer-sand"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 30
    _attr_native_max_value = 900
    _attr_native_step = 30
    _attr_native_unit_of_measurement = "s"

    def __init__(self, coordinator: SGReadyCoordinator, entry):
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_prod_min_duration"
        self._attr_name = "SG Ready Produktion Aktiveringstid"
        self._attr_native_value = coordinator.prod_min_duration

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.prod_min_duration = value
        self._attr_native_value = value
        self.async_write_ha_state()


class SGReadyProdOffDelay(NumberEntity):
    """Fördröjning (s) innan production override stängs av."""
    _attr_icon = "mdi:timer-off"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 60
    _attr_native_max_value = 3600
    _attr_native_step = 60
    _attr_native_unit_of_measurement = "s"

    def __init__(self, coordinator: SGReadyCoordinator, entry):
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_prod_off_delay"
        self._attr_name = "SG Ready Produktion Avstängningstid"
        self._attr_native_value = coordinator.prod_off_delay

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.prod_off_delay = value
        self._attr_native_value = value
        self.async_write_ha_state()
