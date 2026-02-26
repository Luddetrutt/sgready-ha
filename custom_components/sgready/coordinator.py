"""SG Ready koordinator — portad direkt från Node-RED-algoritmen."""
from __future__ import annotations

import logging
import math
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

# Algoritm-konstanter (speglar Node-RED-flödet)
MIN_SPREAD_TO_ACT = 0.10   # 10 öre — under detta = alltid normal
PRICE_ROUND_TO = 0.10      # Avrundning till närmaste 10 öre
EXTREME_LOW = 0.10         # Under detta = alltid boost
EXTREME_HIGH = 5.0         # Över detta = alltid block


def _round_price(p: float) -> float:
    """Avrunda pris till närmaste PRICE_ROUND_TO (undviker floatfel)."""
    return round(p * 100 / (PRICE_ROUND_TO * 100)) * PRICE_ROUND_TO


def _calculate_stats(prices: list[float]) -> dict | None:
    """Beräkna statistik för ett prisfönster."""
    valid = [p for p in prices if p is not None and not math.isnan(p)]
    if not valid:
        return None
    n = len(valid)
    avg = sum(valid) / n
    sorted_p = sorted(valid)
    variance = sum((x - avg) ** 2 for x in valid) / n
    return {
        "avg": avg,
        "min": min(valid),
        "max": max(valid),
        "std": math.sqrt(variance),
        "q1": sorted_p[n // 4],
        "q3": sorted_p[(n * 3) // 4],
        "median": sorted_p[n // 2],
        "count": n,
        "sorted": sorted_p,
    }


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
        self.boost_pct: float = entry.data.get(CONF_BOOST_PCT, DEFAULT_BOOST_PCT)
        self.block_pct: float = entry.data.get(CONF_BLOCK_PCT, DEFAULT_BLOCK_PCT)
        self.min_temp: float = entry.data.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)

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
            today_prices, tomorrow_prices = self._get_prices()
            result = self._calculate_mode(today_prices, tomorrow_prices)

            # Manuell override slår alltid till boost
            if self._override:
                result["mode"] = MODE_BOOST
                result["reason"] = "⚡ Manuell boost-override aktiv"
                result["override"] = True

            await self._publish_mqtt(result["mode"])
            result["override"] = self._override
            return result

        except Exception as err:
            raise UpdateFailed(f"Fel vid uppdatering: {err}") from err

    def _get_prices(self) -> tuple[list, list]:
        """Hämta timpriser från Nord Pool-sensorn."""
        price_entity = self.entry.data.get(CONF_PRICE_ENTITY)
        state = self.hass.states.get(price_entity)

        if not state or state.state in ("unknown", "unavailable"):
            _LOGGER.warning("Kan inte läsa prisdata från %s", price_entity)
            return [], []

        attrs = state.attributes
        today = attrs.get("today", [])
        tomorrow = attrs.get("tomorrow", [])

        # Stöd för raw_today/raw_tomorrow (nyare Nord Pool-integration)
        if not today:
            today = [h.get("value", 0) for h in attrs.get("raw_today", [])]
        if not tomorrow:
            tomorrow = [h.get("value", 0) for h in attrs.get("raw_tomorrow", [])]

        return today, tomorrow

    def _build_window(
        self,
        today: list,
        tomorrow: list,
        current_hour: int,
        perspective_hours: int = 24,
    ) -> tuple[list[float], bool]:
        """Bygg ett centrerat analysfönster av timpriser."""
        hours_back = perspective_hours // 2
        hours_forward = perspective_hours - hours_back
        has_tomorrow = bool(tomorrow)

        window = []

        # Bakåt
        for i in range(hours_back, 0, -1):
            h = current_hour - i
            if h >= 0 and h < len(today) and today[h] is not None:
                window.append(float(today[h]))

        # Nuvarande
        if current_hour < len(today) and today[current_hour] is not None:
            window.append(float(today[current_hour]))

        # Framåt
        for i in range(1, hours_forward):
            h = current_hour + i
            if h < 24 and h < len(today) and today[h] is not None:
                window.append(float(today[h]))
            elif h >= 24 and has_tomorrow:
                th = h - 24
                if th < len(tomorrow) and tomorrow[th] is not None:
                    window.append(float(tomorrow[th]))

        return window, has_tomorrow

    def _calculate_mode(self, today: list, tomorrow: list) -> dict:
        """Beräkna SG Ready-läge — exakt portad från Node-RED-algoritmen."""
        current_hour = datetime.now().hour
        perspective_hours = 24

        # Bygg analysfönster
        window, has_tomorrow = self._build_window(today, tomorrow, current_hour, perspective_hours)
        window_stats = _calculate_stats(window)

        # Aktuellt pris
        current_price = float(today[current_hour]) if current_hour < len(today) else 0.0

        # Beräkna percentil med avrundade priser
        price_percentile = 50.0
        boost_threshold = None
        block_threshold = None

        # BOOST_PERCENTILE = boost_pct, BLOCK_PERCENTILE = 100 - block_pct
        boost_percentile = self.boost_pct
        block_percentile = 100 - self.block_pct

        if window_stats and window:
            rounded_current = _round_price(current_price)
            rounded_window = [_round_price(p) for p in window_stats["sorted"]]

            lower_count = sum(1 for p in rounded_window if p < rounded_current)
            price_percentile = (lower_count / len(rounded_window)) * 100

            boost_idx = min(
                math.floor(len(rounded_window) * boost_percentile / 100),
                len(rounded_window) - 1,
            )
            block_idx = min(
                math.floor(len(rounded_window) * block_percentile / 100),
                len(rounded_window) - 1,
            )
            boost_threshold = rounded_window[boost_idx]
            block_threshold = rounded_window[block_idx]

        # Prisspridning
        price_spread = (window_stats["max"] - window_stats["min"]) if window_stats else 0
        insignificant_spread = price_spread < MIN_SPREAD_TO_ACT

        # === BESLUTSLOGIK (prioritetsordning från Node-RED) ===
        sg_mode = MODE_NORMAL
        reason = ""
        confidence = 75
        temp_override_active = False

        # P1: Minimal prisspridning
        if insignificant_spread:
            sg_mode = MODE_NORMAL
            reason = f"Minimal prisspridning ({price_spread * 100:.0f} öre)"
            confidence = 85

        # P2: Extrempriser
        elif current_price < EXTREME_LOW:
            sg_mode = MODE_BOOST
            reason = "⚡ Extremt lågt pris (<10 öre)"
            confidence = 100

        elif current_price > EXTREME_HIGH:
            sg_mode = MODE_BLOCK
            reason = "⚠️ Extremt högt pris (>5 kr)"
            confidence = 100

        # P3: Percentilbaserad
        elif price_percentile <= boost_percentile:
            sg_mode = MODE_BOOST
            reason = f"Låg percentil P{price_percentile:.0f} (billigaste {self.boost_pct:.0f}%)"
            confidence = 85

        elif price_percentile >= block_percentile:
            sg_mode = MODE_BLOCK
            reason = f"Hög percentil P{price_percentile:.0f} (dyraste {self.block_pct:.0f}%)"
            confidence = 85

        # P4: Normal
        else:
            sg_mode = MODE_NORMAL
            reason = f"Normalläge P{price_percentile:.0f}"
            confidence = 75

        # SIST: Temperaturskydd — förhindrar endast BLOCK
        indoor_temp = self._get_indoor_temp()
        if indoor_temp is not None and indoor_temp < self.min_temp and sg_mode == MODE_BLOCK:
            sg_mode = MODE_NORMAL
            reason = f"🌡 Temp för låg ({indoor_temp:.1f}°C < {self.min_temp}°C) — förhindrar block"
            confidence = 95
            temp_override_active = True
            _LOGGER.info("TEMPERATUR-OVERRIDE: Förhindrar block, temp=%.1f°C", indoor_temp)

        # Sänk confidence om imorgondagens priser saknas sent på dagen
        if not has_tomorrow and current_hour >= 18:
            confidence = max(50, confidence - 10)
            reason += " [begränsad data]"
        elif not has_tomorrow:
            confidence = max(55, confidence - 5)

        _LOGGER.info(
            "SG Ready: %s | %s | P%.0f | pris=%.2f kr | spread=%.2f kr | conf=%d%%",
            sg_mode.upper(), reason, price_percentile, current_price, price_spread, confidence,
        )

        return {
            "mode": sg_mode,
            "reason": reason,
            "confidence": confidence,
            "current_price": current_price,
            "price_percentile": round(price_percentile, 1),
            "price_spread": round(price_spread, 4),
            "boost_threshold": boost_threshold,
            "block_threshold": block_threshold,
            "window_size": len(window),
            "has_tomorrow": has_tomorrow,
            "temp_override_active": temp_override_active,
            "indoor_temp": indoor_temp,
        }

    def _get_indoor_temp(self) -> float | None:
        """Hämta inomhustemperatur."""
        temp_entity = self.entry.data.get(CONF_TEMP_ENTITY)
        if not temp_entity:
            return None
        state = self.hass.states.get(temp_entity)
        if not state or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    async def _publish_mqtt(self, mode: str) -> None:
        """Publicera läget till MQTT."""
        topic = self.entry.data.get(CONF_MQTT_TOPIC, DEFAULT_MQTT_TOPIC)
        await mqtt.async_publish(self.hass, topic, mode, qos=1, retain=True)
        _LOGGER.debug("MQTT → %s: %s", topic, mode)
