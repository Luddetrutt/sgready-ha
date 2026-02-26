"""SG Ready koordinator — hämtar priser och beräknar läge."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    MODE_BOOST,
    MODE_NORMAL,
    MODE_BLOCK,
    CONF_MQTT_TOPIC,
    CONF_PRICE_ENTITY,
    CONF_TEMP_ENTITY,
    CONF_BOOST_PCT,
    CONF_BLOCK_PCT,
    CONF_MIN_TEMP,
    DEFAULT_BOOST_PCT,
    DEFAULT_BLOCK_PCT,
    DEFAULT_MIN_TEMP,
    DEFAULT_MQTT_TOPIC,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=5)


class SGReadyCoordinator(DataUpdateCoordinator):
    """Hanterar prisdata och beräknar SG Ready-läge."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        self._override = False

        # Inställningar (uppdateras från number-entiteter)
        self.boost_pct: float = entry.options.get(CONF_BOOST_PCT, DEFAULT_BOOST_PCT)
        self.block_pct: float = entry.options.get(CONF_BLOCK_PCT, DEFAULT_BLOCK_PCT)
        self.min_temp: float = entry.options.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)

    @property
    def override(self) -> bool:
        return self._override

    @override.setter
    def override(self, value: bool) -> None:
        self._override = value
        self.hass.async_create_task(self.async_refresh())

    async def _async_update_data(self) -> dict:
        """Hämta prisdata, beräkna läge och publicera via MQTT."""
        try:
            prices = self._get_prices()
            current_price, rank, total, mode = self._calculate_mode(prices)
            await self._publish_mqtt(mode)

            return {
                "mode": mode,
                "current_price": current_price,
                "rank": rank,
                "total": total,
                "prices": prices,
                "override": self._override,
            }
        except Exception as err:
            raise UpdateFailed(f"Fel vid uppdatering: {err}") from err

    def _get_prices(self) -> list[tuple[int, float]]:
        """Hämta timpriser från Nord Pool-sensorn. Returnerar lista av (timme, pris)."""
        price_entity = self.entry.data.get(CONF_PRICE_ENTITY)
        state = self.hass.states.get(price_entity)

        if not state or state.state in ("unknown", "unavailable"):
            _LOGGER.warning("Kan inte läsa prisdata från %s", price_entity)
            return []

        # Nord Pool-sensorn har dagens priser i attributes["today"]
        today_prices = state.attributes.get("today", [])
        if not today_prices:
            # Försök med raw_today (nyare version av integrationen)
            raw = state.attributes.get("raw_today", [])
            today_prices = [h.get("value", 0) for h in raw] if raw else []

        now = datetime.now().hour
        prices = []
        for i, price in enumerate(today_prices):
            if price is not None:
                prices.append((i, float(price)))

        _LOGGER.debug("Hämtade %d timpriser", len(prices))
        return prices

    def _calculate_mode(self, prices: list) -> tuple:
        """Beräkna vilket SG Ready-läge som gäller för aktuell timme."""
        now = datetime.now().hour

        if not prices:
            return 0.0, 0, 0, MODE_NORMAL

        current_price = next((p for h, p in prices if h == now), 0.0)
        total = len(prices)

        # Sortera priser för rankning
        sorted_prices = sorted(prices, key=lambda x: x[1])
        price_rank = next((i + 1 for i, (h, _) in enumerate(sorted_prices) if h == now), 0)

        # Beräkna gränser
        boost_count = max(1, round(total * self.boost_pct / 100))
        block_count = max(1, round(total * self.block_pct / 100))

        boost_hours = {h for h, _ in sorted_prices[:boost_count]}
        block_hours = {h for h, _ in sorted_prices[-block_count:]}

        # Override slår alltid till boost
        if self._override:
            mode = MODE_BOOST
        # Temperaturskydd — aldrig block om det är för kallt
        elif now in block_hours and not self._is_too_cold():
            mode = MODE_BLOCK
        elif now in boost_hours:
            mode = MODE_BOOST
        else:
            mode = MODE_NORMAL

        _LOGGER.info(
            "SG Ready: %s (pris: %.2f kr, rank: %d/%d)",
            mode, current_price, price_rank, total,
        )
        return current_price, price_rank, total, mode

    def _is_too_cold(self) -> bool:
        """Kolla om innetempen är under min_temp."""
        temp_entity = self.entry.data.get(CONF_TEMP_ENTITY)
        if not temp_entity:
            return False
        state = self.hass.states.get(temp_entity)
        if not state or state.state in ("unknown", "unavailable"):
            return False
        try:
            return float(state.state) < self.min_temp
        except ValueError:
            return False

    async def _publish_mqtt(self, mode: str) -> None:
        """Publicera läget till MQTT."""
        topic = self.entry.data.get(CONF_MQTT_TOPIC, DEFAULT_MQTT_TOPIC)
        await mqtt.async_publish(self.hass, topic, mode, qos=1, retain=True)
        _LOGGER.debug("MQTT publicerat: %s → %s", topic, mode)
