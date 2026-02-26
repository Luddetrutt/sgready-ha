"""Sensorer för SG Ready."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_MODE, SENSOR_PRICE, SENSOR_RANK
from .coordinator import SGReadyCoordinator


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    coordinator: SGReadyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        SGReadyModeSensor(coordinator, entry),
        SGReadyPriceSensor(coordinator, entry),
        SGReadyRankSensor(coordinator, entry),
    ])


class SGReadyModeSensor(CoordinatorEntity, SensorEntity):
    """Visar aktuellt SG Ready-läge."""

    _attr_icon = "mdi:heat-pump"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{SENSOR_MODE}"
        self._attr_name = "SG Ready Läge"

    @property
    def native_value(self):
        return self.coordinator.data.get("mode") if self.coordinator.data else None

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        return {
            "override": self.coordinator.data.get("override", False),
            "rank": self.coordinator.data.get("rank"),
            "total_hours": self.coordinator.data.get("total"),
        }


class SGReadyPriceSensor(CoordinatorEntity, SensorEntity):
    """Visar aktuellt elpris."""

    _attr_icon = "mdi:currency-usd"
    _attr_native_unit_of_measurement = "SEK/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{SENSOR_PRICE}"
        self._attr_name = "SG Ready Aktuellt Pris"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        price = self.coordinator.data.get("current_price")
        return round(price, 4) if price is not None else None


class SGReadyRankSensor(CoordinatorEntity, SensorEntity):
    """Visar prisrankning för aktuell timme."""

    _attr_icon = "mdi:sort-numeric-ascending"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{SENSOR_RANK}"
        self._attr_name = "SG Ready Prisrankning"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        rank = self.coordinator.data.get("rank")
        total = self.coordinator.data.get("total")
        return f"P{rank}/{total}" if rank and total else None
