"""Konfigurationssliders för SG Ready — värden bevaras vid omstart."""
from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN, NUMBER_BOOST_PCT, NUMBER_BLOCK_PCT, NUMBER_MIN_TEMP,
    DEFAULT_BOOST_PCT, DEFAULT_BLOCK_PCT, DEFAULT_MIN_TEMP,
    DEFAULT_PROD_NORMAL_THRESHOLD, DEFAULT_PROD_BOOST_THRESHOLD,
    DEFAULT_PROD_RETURN_THRESHOLD, DEFAULT_PROD_HYSTERESIS,
    DEFAULT_PROD_MIN_DURATION, DEFAULT_PROD_OFF_DELAY,
)
from .coordinator import SGReadyCoordinator


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    coordinator: SGReadyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        SGReadyBoostPercent(coordinator, entry),
        SGReadyBlockPercent(coordinator, entry),
        SGReadyMinTemp(coordinator, entry),
        SGReadyProdNormalThreshold(coordinator, entry),
        SGReadyProdBoostThreshold(coordinator, entry),
        SGReadyProdReturnThreshold(coordinator, entry),
        SGReadyProdHysteresis(coordinator, entry),
        SGReadyProdMinDuration(coordinator, entry),
        SGReadyProdOffDelay(coordinator, entry),
    ])


# ── Hjälpbas ─────────────────────────────────────────────────────────────────

class _SGReadyNumber(RestoreNumber):
    """Basklass med automatisk restore vid HA-restart."""

    _coord_attr: str          # attributnamn på coordinator
    _default_value: float     # defaultvärde om ingen historik finns

    def __init__(self, coordinator: SGReadyCoordinator, entry):
        self._coordinator = coordinator
        self._attr_native_value = getattr(coordinator, self._coord_attr)

    async def async_added_to_hass(self) -> None:
        """Återställ senaste värde från HA-databasen."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._attr_native_value = last.native_value
            setattr(self._coordinator, self._coord_attr, last.native_value)

    async def async_set_native_value(self, value: float) -> None:
        setattr(self._coordinator, self._coord_attr, value)
        self._attr_native_value = value
        self.async_write_ha_state()
        await self._coordinator.async_refresh()


# ── Prisalgoritm ─────────────────────────────────────────────────────────────

class SGReadyBoostPercent(_SGReadyNumber):
    """Procentandel billigaste timmar som ger boost."""
    _coord_attr = "boost_pct"
    _default_value = DEFAULT_BOOST_PCT
    _attr_icon = "mdi:arrow-up-bold"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 5
    _attr_native_max_value = 50
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{NUMBER_BOOST_PCT}"
        self._attr_name = "SG Ready Boost-procent"


class SGReadyBlockPercent(_SGReadyNumber):
    """Procentandel dyraste timmar som blockeras."""
    _coord_attr = "block_pct"
    _default_value = DEFAULT_BLOCK_PCT
    _attr_icon = "mdi:arrow-down-bold"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 10
    _attr_native_max_value = 80
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{NUMBER_BLOCK_PCT}"
        self._attr_name = "SG Ready Block-procent"


class SGReadyMinTemp(_SGReadyNumber):
    """Mintemperatur — block aktiveras inte om det är kallare."""
    _coord_attr = "min_temp"
    _default_value = DEFAULT_MIN_TEMP
    _attr_icon = "mdi:thermometer-low"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 15
    _attr_native_max_value = 25
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{NUMBER_MIN_TEMP}"
        self._attr_name = "SG Ready Mintemperatur"


# ── Production override sliders ───────────────────────────────────────────────

class SGReadyProdNormalThreshold(_SGReadyNumber):
    """Exportnivå (W) för att gå till normal-läge."""
    _coord_attr = "prod_normal_threshold"
    _default_value = DEFAULT_PROD_NORMAL_THRESHOLD
    _attr_icon = "mdi:solar-power"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = -2000
    _attr_native_max_value = -10
    _attr_native_step = 50
    _attr_native_unit_of_measurement = "W"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_prod_normal_threshold"
        self._attr_name = "SG Ready Produktion Normal-tröskel"

    async def async_set_native_value(self, value: float) -> None:
        """Prod-sliders triggar inte coordinator refresh."""
        self._coordinator.prod_normal_threshold = value
        self._attr_native_value = value
        self.async_write_ha_state()


class SGReadyProdBoostThreshold(_SGReadyNumber):
    """Exportnivå (W) för att gå till boost-läge."""
    _coord_attr = "prod_boost_threshold"
    _default_value = DEFAULT_PROD_BOOST_THRESHOLD
    _attr_icon = "mdi:solar-power-variant"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = -5000
    _attr_native_max_value = -50
    _attr_native_step = 50
    _attr_native_unit_of_measurement = "W"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_prod_boost_threshold"
        self._attr_name = "SG Ready Produktion Boost-tröskel"

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.prod_boost_threshold = value
        self._attr_native_value = value
        self.async_write_ha_state()


class SGReadyProdReturnThreshold(_SGReadyNumber):
    """Importnivå (W) för att deaktivera production override."""
    _coord_attr = "prod_return_threshold"
    _default_value = DEFAULT_PROD_RETURN_THRESHOLD
    _attr_icon = "mdi:transmission-tower-import"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 500
    _attr_native_step = 25
    _attr_native_unit_of_measurement = "W"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_prod_return_threshold"
        self._attr_name = "SG Ready Produktion Återgångs-tröskel"

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.prod_return_threshold = value
        self._attr_native_value = value
        self.async_write_ha_state()


class SGReadyProdHysteresis(_SGReadyNumber):
    """Hysteres i W för att undvika snabb växling."""
    _coord_attr = "prod_hysteresis"
    _default_value = DEFAULT_PROD_HYSTERESIS
    _attr_icon = "mdi:sine-wave"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 10
    _attr_native_max_value = 300
    _attr_native_step = 10
    _attr_native_unit_of_measurement = "W"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_prod_hysteresis"
        self._attr_name = "SG Ready Produktion Hysteres"

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.prod_hysteresis = value
        self._attr_native_value = value
        self.async_write_ha_state()


class SGReadyProdMinDuration(_SGReadyNumber):
    """Minsta tid (s) med överskott innan aktivering."""
    _coord_attr = "prod_min_duration"
    _default_value = DEFAULT_PROD_MIN_DURATION
    _attr_icon = "mdi:timer-sand"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 30
    _attr_native_max_value = 900
    _attr_native_step = 30
    _attr_native_unit_of_measurement = "s"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_prod_min_duration"
        self._attr_name = "SG Ready Produktion Aktiveringstid"

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.prod_min_duration = value
        self._attr_native_value = value
        self.async_write_ha_state()


class SGReadyProdOffDelay(_SGReadyNumber):
    """Fördröjning (s) innan production override stängs av."""
    _coord_attr = "prod_off_delay"
    _default_value = DEFAULT_PROD_OFF_DELAY
    _attr_icon = "mdi:timer-off"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 60
    _attr_native_max_value = 3600
    _attr_native_step = 60
    _attr_native_unit_of_measurement = "s"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_prod_off_delay"
        self._attr_name = "SG Ready Produktion Avstängningstid"

    async def async_set_native_value(self, value: float) -> None:
        self._coordinator.prod_off_delay = value
        self._attr_native_value = value
        self.async_write_ha_state()
