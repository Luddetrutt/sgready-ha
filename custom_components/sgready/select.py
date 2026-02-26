"""AI Override select-entitet för SG Ready."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, AI_MODES, AI_MODE_AUTO, SELECT_AI_OVERRIDE
from .coordinator import SGReadyCoordinator


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    coordinator: SGReadyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SGReadyAIOverrideSelect(coordinator, entry)])


class SGReadyAIOverrideSelect(SelectEntity):
    """Väljer AI-override-läge: auto / force_boost / force_normal / force_block."""

    _attr_icon = "mdi:robot"
    _attr_options = AI_MODES

    def __init__(self, coordinator: SGReadyCoordinator, entry):
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_{SELECT_AI_OVERRIDE}"
        self._attr_name = "SG Ready AI Override"
        self._attr_current_option = AI_MODE_AUTO

    @property
    def current_option(self) -> str:
        return self._coordinator.ai_mode

    @property
    def extra_state_attributes(self):
        return {
            "ai_reason": self._coordinator.ai_reason,
            "ai_until": self._coordinator.ai_until.isoformat() if self._coordinator.ai_until else None,
        }

    async def async_select_option(self, option: str) -> None:
        self._coordinator.ai_mode = option
        if option == AI_MODE_AUTO:
            self._coordinator.ai_until = None
            self._coordinator.ai_reason = ""
        self.async_write_ha_state()
