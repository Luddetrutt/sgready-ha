"""Override-switch för SG Ready — tvingar boost-läge."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SWITCH_OVERRIDE
from .coordinator import SGReadyCoordinator


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    coordinator: SGReadyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SGReadyOverrideSwitch(coordinator, entry)])


class SGReadyOverrideSwitch(SwitchEntity):
    """Manuell override — slår på boost oavsett pris."""

    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, coordinator: SGReadyCoordinator, entry):
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_{SWITCH_OVERRIDE}"
        self._attr_name = "SG Ready Boost Override"

    @property
    def is_on(self) -> bool:
        return self._coordinator.override

    async def async_turn_on(self, **kwargs) -> None:
        self._coordinator.override = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._coordinator.override = False
        self.async_write_ha_state()
