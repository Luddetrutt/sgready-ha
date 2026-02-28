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
        d = self.coordinator.data
        if not d:
            return {}
        return {
            # Beslut
            "reason": d.get("reason"),
            "confidence": f"{d.get('confidence', 0)}%",
            "override": d.get("override", False),
            "temp_override_active": d.get("temp_override_active"),
            # Prisanalys
            "price_percentile": f"{d.get('price_percentile', 0):.0f}%",
            "price_vs_avg": f"{d.get('price_vs_avg_pct', 0):.0f}%",
            "diff_from_avg_ore": d.get("diff_from_avg_ore"),
            "price_spread": d.get("price_spread"),
            "spread_pct": f"{d.get('spread_pct', 0):.0f}%",
            "insignificant_spread": d.get("insignificant_spread"),
            "boost_threshold": d.get("boost_threshold"),
            "block_threshold": d.get("block_threshold"),
            # Fönster
            "window_size": f"{d.get('window_size', 0)}h",
            "window_avg": d.get("window_avg"),
            "window_min": d.get("window_min"),
            "window_max": d.get("window_max"),
            "has_tomorrow_prices": d.get("has_tomorrow"),
            # Temperatur
            "indoor_temp": d.get("indoor_temp"),
            "min_temp": d.get("min_temp"),
            # Konfiguration
            "boost_pct": f"{d.get('boost_pct', 0):.0f}%",
            "block_pct": f"{d.get('block_pct', 0):.0f}%",
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
        percentile = self.coordinator.data.get("price_percentile")
        return f"P{percentile:.0f}" if percentile is not None else None
