"""Konfigurationssliders för SG Ready."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NUMBER_BOOST_PCT, NUMBER_BLOCK_PCT, NUMBER_MIN_TEMP
from .coordinator import SGReadyCoordinator


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    coordinator: SGReadyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        SGReadyBoostPercent(coordinator, entry),
        SGReadyBlockPercent(coordinator, entry),
        SGReadyMinTemp(coordinator, entry),
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
