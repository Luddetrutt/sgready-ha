"""SG Ready koordinator — portad från Node-RED + AI-override handles."""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import now as ha_now, parse_datetime

from .const import (
    DOMAIN,
    MODE_BOOST, MODE_NORMAL, MODE_BLOCK,
    AI_MODE_AUTO, AI_MODE_FORCE_BOOST, AI_MODE_FORCE_NORMAL, AI_MODE_FORCE_BLOCK,
    CONF_MQTT_TOPIC, CONF_MQTT_AI_TOPIC,
    CONF_NORDPOOL_CONFIG_ENTRY, CONF_NORDPOOL_AREA,
    CONF_TEMP_ENTITY, CONF_TARIFF_ENTITY,
    CONF_BOOST_PCT, CONF_BLOCK_PCT, CONF_MIN_TEMP,
    DEFAULT_BOOST_PCT, DEFAULT_BLOCK_PCT, DEFAULT_MIN_TEMP,
    DEFAULT_MQTT_TOPIC, DEFAULT_MQTT_AI_TOPIC,
    MIN_SPREAD_TO_ACT, PRICE_ROUND_TO, EXTREME_LOW, EXTREME_HIGH,
    CONF_GRID_POWER_ENTITY,
    CONF_PROD_ENABLED,
    CONF_PROD_NORMAL_THRESHOLD, CONF_PROD_BOOST_THRESHOLD,
    CONF_PROD_RETURN_THRESHOLD, CONF_PROD_HYSTERESIS,
    CONF_PROD_MIN_DURATION, CONF_PROD_OFF_DELAY,
    DEFAULT_PROD_NORMAL_THRESHOLD, DEFAULT_PROD_BOOST_THRESHOLD,
    DEFAULT_PROD_RETURN_THRESHOLD, DEFAULT_PROD_HYSTERESIS,
    DEFAULT_PROD_MIN_DURATION, DEFAULT_PROD_OFF_DELAY,
)

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(minutes=5)


def _conf(entry, key, default=None):
    """Läs config — options har högre prioritet än data."""
    return entry.options.get(key, entry.data.get(key, default))


def _round_price(p: float) -> float:
    return round(p * 100 / (PRICE_ROUND_TO * 100)) * PRICE_ROUND_TO


def _calculate_stats(prices: list[float]) -> dict | None:
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
        "median": sorted_p[n // 2],
        "count": n,
        "sorted": sorted_p,
    }


class SGReadyCoordinator(DataUpdateCoordinator):
    """Hanterar prisdata och beräknar SG Ready-läge."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.entry = entry
        self._manual_override = False  # Manuell boost-switch

        # AI override state
        self._ai_mode: str = AI_MODE_AUTO
        self._ai_until: datetime | None = None
        self._ai_reason: str = ""
        self._mqtt_unsub = None
        self._nordpool_unsub = None   # Prenumeration på Nord Pool-uppdateringar
        self._had_prices: bool = False  # Har vi fått priser någon gång?

        # Production override state machine
        self._prod_state = {
            "active": False,
            "mode": None,
            "start_time": None,       # Tidpunkt för att börja räkna aktiveringstid
            "last_change": None,      # Tidpunkt för in i hysteres-zon
            "in_hysteresis": False,
            "tariff_limited": False,
        }

        # Grid meter
        self._grid_power: float = 0.0
        self._grid_timestamp: datetime | None = None

        # Konfiguration — pris
        self.boost_pct: float = _conf(entry, CONF_BOOST_PCT, DEFAULT_BOOST_PCT)
        self.block_pct: float = _conf(entry, CONF_BLOCK_PCT, DEFAULT_BLOCK_PCT)
        self.min_temp: float = _conf(entry, CONF_MIN_TEMP, DEFAULT_MIN_TEMP)

        # Konfiguration — production override (tweakbara per solanläggning)
        self.prod_normal_threshold: float = _conf(entry, CONF_PROD_NORMAL_THRESHOLD, DEFAULT_PROD_NORMAL_THRESHOLD)
        self.prod_boost_threshold: float = _conf(entry, CONF_PROD_BOOST_THRESHOLD, DEFAULT_PROD_BOOST_THRESHOLD)
        self.prod_return_threshold: float = _conf(entry, CONF_PROD_RETURN_THRESHOLD, DEFAULT_PROD_RETURN_THRESHOLD)
        self.prod_hysteresis: float = _conf(entry, CONF_PROD_HYSTERESIS, DEFAULT_PROD_HYSTERESIS)
        self.prod_min_duration: float = _conf(entry, CONF_PROD_MIN_DURATION, DEFAULT_PROD_MIN_DURATION)
        self.prod_off_delay: float = _conf(entry, CONF_PROD_OFF_DELAY, DEFAULT_PROD_OFF_DELAY)

    # ── AI Override properties ──────────────────────────────────────────────

    @property
    def ai_mode(self) -> str:
        """Returnerar aktuellt AI-läge, auto om utgångstid passerat."""
        if self._ai_mode != AI_MODE_AUTO and self._ai_until:
            if ha_now() > self._ai_until:
                _LOGGER.info("AI-override utgången — återgår till auto")
                self._ai_mode = AI_MODE_AUTO
                self._ai_reason = ""
                self._ai_until = None
        return self._ai_mode

    @ai_mode.setter
    def ai_mode(self, value: str) -> None:
        self._ai_mode = value
        self.hass.async_create_task(self.async_refresh())

    @property
    def ai_until(self) -> datetime | None:
        return self._ai_until

    @ai_until.setter
    def ai_until(self, value: datetime | None) -> None:
        self._ai_until = value

    @property
    def ai_reason(self) -> str:
        return self._ai_reason

    @ai_reason.setter
    def ai_reason(self, value: str) -> None:
        self._ai_reason = value

    @property
    def manual_override(self) -> bool:
        return self._manual_override

    @manual_override.setter
    def manual_override(self, value: bool) -> None:
        self._manual_override = value
        self.hass.async_create_task(self.async_refresh())

    # ── MQTT AI-kommandolyssning ────────────────────────────────────────────

    async def async_start_ai_mqtt(self) -> None:
        """Prenumerera på MQTT-topic för AI-kommandon."""
        topic = _conf(self.entry, CONF_MQTT_AI_TOPIC, DEFAULT_MQTT_AI_TOPIC)

        @callback
        def _on_ai_command(msg) -> None:
            try:
                payload = json.loads(msg.payload)
                mode = payload.get("mode", AI_MODE_AUTO)
                reason = payload.get("reason", "AI-kommando")
                until_str = payload.get("until")
                until = parse_datetime(until_str) if until_str else None

                _LOGGER.info("AI-kommando mottaget: mode=%s, reason=%s, until=%s", mode, reason, until)
                self._ai_mode = mode
                self._ai_reason = reason
                self._ai_until = until
                self.hass.async_create_task(self.async_refresh())
            except (json.JSONDecodeError, Exception) as err:
                _LOGGER.warning("Ogiltigt AI-MQTT-kommando: %s", err)

        try:
            self._mqtt_unsub = await mqtt.async_subscribe(self.hass, topic, _on_ai_command)
            _LOGGER.info("Lyssnar på AI-kommandon via MQTT: %s", topic)
        except Exception as err:
            _LOGGER.warning("Kunde inte prenumerera på AI MQTT-topic %s: %s", topic, err)

    async def async_stop_ai_mqtt(self) -> None:
        if self._mqtt_unsub:
            self._mqtt_unsub()
            self._mqtt_unsub = None

    # ── Nord Pool-lyssnare ──────────────────────────────────────────────────

    def async_start_nordpool_listener(self) -> None:
        """Prenumerera på Nord Pool-koordinatorn — refresha direkt vid ny data.

        Nord Pool publicerar morgondagens priser ~kl 13. Utan denna lyssnare
        kan det dröja upp till 60 min innan vi märker det (Nord Pools egna
        uppdateringsintervall). Med lyssnaren refreshar vi inom sekunder.
        """
        nordpool_entry_id = _conf(self.entry, CONF_NORDPOOL_CONFIG_ENTRY)
        nordpool_entry = self.hass.config_entries.async_get_entry(nordpool_entry_id)
        if not nordpool_entry:
            _LOGGER.warning("Kan inte starta Nord Pool-lyssnare — entry saknas")
            return

        coordinator = getattr(nordpool_entry, "runtime_data", None)
        if not coordinator:
            _LOGGER.warning("Kan inte starta Nord Pool-lyssnare — ingen coordinator")
            return

        @callback
        def _on_nordpool_update() -> None:
            _LOGGER.debug("Nord Pool uppdaterades — triggar SG Ready refresh")
            self.hass.async_create_task(self.async_refresh())

        self._nordpool_unsub = coordinator.async_add_listener(_on_nordpool_update)
        _LOGGER.info("Prenumererar på Nord Pool-uppdateringar")

    def async_stop_nordpool_listener(self) -> None:
        if self._nordpool_unsub:
            self._nordpool_unsub()
            self._nordpool_unsub = None

    # ── Prisfetching via Nord Pool coordinator ──────────────────────────────

    async def _fetch_prices(self) -> tuple[list[float], list[float]]:
        """Hämta timpriser direkt från Nord Pool-koordinatorns data.

        Nord Pool-integrationen (officiell, HA 2024+) lagrar priser i
        config_entry.runtime_data. Rådata är i milli-SEK/MWh — delas
        med 1000 för att få SEK/kWh.
        """
        from homeassistant.util import dt as dt_util

        nordpool_entry_id = _conf(self.entry, CONF_NORDPOOL_CONFIG_ENTRY)
        area = _conf(self.entry, CONF_NORDPOOL_AREA, "SE4")

        nordpool_entry = self.hass.config_entries.async_get_entry(nordpool_entry_id)
        if not nordpool_entry:
            _LOGGER.warning("Nord Pool config entry '%s' hittades inte", nordpool_entry_id)
            return [], []

        coordinator = getattr(nordpool_entry, "runtime_data", None)
        if not coordinator or not getattr(coordinator, "data", None):
            _LOGGER.warning("Nord Pool coordinator har ingen data ännu")
            return [], []

        today_str = dt_util.now().strftime("%Y-%m-%d")
        tomorrow_str = (dt_util.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        today_prices: list[float] = []
        tomorrow_prices: list[float] = []

        try:
            today_start = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow_start = today_start + timedelta(days=1)
            day_after_start = tomorrow_start + timedelta(days=1)

            today_entries: list[tuple[int, float]] = []
            tomorrow_entries: list[tuple[int, float]] = []

            for day_data in coordinator.data.entries:
                for entry in day_data.entries:
                    price = entry.entry.get(area)
                    if price is None:
                        continue
                    entry_local = dt_util.as_local(entry.start)
                    if today_start <= entry_local < tomorrow_start:
                        today_entries.append((entry_local.hour, price / 1000))
                    elif tomorrow_start <= entry_local < day_after_start:
                        tomorrow_entries.append((entry_local.hour, price / 1000))

            # Sortera kronologiskt (timme 0 → index 0)
            today_prices = [p for _, p in sorted(today_entries)]
            tomorrow_prices = [p for _, p in sorted(tomorrow_entries)]

        except Exception as err:
            _LOGGER.error("Fel vid parsning av Nord Pool-data: %s", err, exc_info=True)
            return [], []

        if not today_prices:
            if self._had_prices:
                _LOGGER.warning(
                    "Priser saknas plötsligt för %s area=%s — kör på normalläge tills data återkommer",
                    today_str, area,
                )
            else:
                _LOGGER.warning("Inga priser hittade för %s, area=%s", today_str, area)
        else:
            self._had_prices = True
            had_tomorrow = bool(tomorrow_prices)
            _LOGGER.debug(
                "Nord Pool: %d timmar idag%s (area=%s)",
                len(today_prices),
                f", {len(tomorrow_prices)} imorgon" if had_tomorrow else " — morgondagens priser saknas ännu",
                area,
            )

        return today_prices, tomorrow_prices

    # ── Huvuduppdatering ────────────────────────────────────────────────────

    async def _async_update_data(self) -> dict:
        today, tomorrow = await self._fetch_prices()

        try:
            result = self._calculate_mode(today, tomorrow)
        except Exception as err:
            _LOGGER.error("Fel i _calculate_mode: %s", err, exc_info=True)
            result = {"mode": MODE_NORMAL, "reason": "Beräkningsfel — normal fallback", "confidence": 0,
                      "current_price": 0.0, "price_percentile": 50.0, "price_vs_avg_pct": 100.0,
                      "diff_from_avg_ore": 0.0, "price_spread": 0.0, "spread_pct": 0.0,
                      "insignificant_spread": True, "boost_threshold": None, "block_threshold": None,
                      "window_size": 0, "window_avg": None, "window_min": None, "window_max": None,
                      "has_tomorrow": False, "indoor_temp": None, "temp_override_active": False,
                      "prod_override_active": False, "prod_override_mode": None,
                      "prod_override_in_hysteresis": False, "prod_override_countdown": None,
                      "tariff_blocked": False, "ai_override_active": False}

        try:
            await self._publish_mqtt(result["mode"])
        except Exception as err:
            _LOGGER.warning("MQTT-publicering misslyckades: %s", err)

        return result

    # ── Algoritm ────────────────────────────────────────────────────────────

    def _build_window(self, today, tomorrow, current_hour, perspective_hours=24):
        hours_back = perspective_hours // 2
        hours_forward = perspective_hours - hours_back
        has_tomorrow = bool(tomorrow)
        window = []

        for i in range(hours_back, 0, -1):
            h = current_hour - i
            if 0 <= h < len(today) and today[h] is not None:
                window.append(float(today[h]))

        if current_hour < len(today) and today[current_hour] is not None:
            window.append(float(today[current_hour]))

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
        current_hour = datetime.now().hour
        window, has_tomorrow = self._build_window(today, tomorrow, current_hour)
        window_stats = _calculate_stats(window)

        current_price = float(today[current_hour]) if current_hour < len(today) else 0.0

        boost_percentile = self.boost_pct
        block_percentile = 100 - self.block_pct

        price_percentile = 50.0
        boost_threshold = None
        block_threshold = None

        if window_stats and window:
            rounded_current = _round_price(current_price)
            rounded_window = [_round_price(p) for p in window_stats["sorted"]]
            lower_count = sum(1 for p in rounded_window if p < rounded_current)
            price_percentile = (lower_count / len(rounded_window)) * 100

            boost_idx = min(math.floor(len(rounded_window) * boost_percentile / 100), len(rounded_window) - 1)
            block_idx = min(math.floor(len(rounded_window) * block_percentile / 100), len(rounded_window) - 1)
            boost_threshold = rounded_window[boost_idx]
            block_threshold = rounded_window[block_idx]

        price_spread = (window_stats["max"] - window_stats["min"]) if window_stats else 0
        insignificant_spread = price_spread < MIN_SPREAD_TO_ACT
        window_avg = window_stats["avg"] if window_stats else None
        price_vs_avg = (current_price / window_avg) if window_avg else 1.0
        diff_from_avg = abs(current_price - window_avg) if window_avg else 0.0

        # ── BESLUTSLOGIK ─────────────────────────────────────────────────────

        sg_mode = MODE_NORMAL
        reason = ""
        confidence = 0
        temp_override_active = False
        ai_override_active = False

        # P0: AI OVERRIDE (högsta prioritet)
        effective_ai_mode = self.ai_mode  # Kontrollerar utgångstid
        if self._manual_override:
            sg_mode = MODE_BOOST
            reason = "⚡ Manuell boost-override"
            confidence = 100
        elif effective_ai_mode == AI_MODE_FORCE_BOOST:
            sg_mode = MODE_BOOST
            reason = f"🤖 AI: {self._ai_reason or 'Force boost'}"
            confidence = 100
            ai_override_active = True
        elif effective_ai_mode == AI_MODE_FORCE_NORMAL:
            sg_mode = MODE_NORMAL
            reason = f"🤖 AI: {self._ai_reason or 'Force normal'}"
            confidence = 100
            ai_override_active = True
        elif effective_ai_mode == AI_MODE_FORCE_BLOCK:
            sg_mode = MODE_BLOCK
            reason = f"🤖 AI: {self._ai_reason or 'Force block'}"
            confidence = 100
            ai_override_active = True

        # P1–P4: Normal algoritm
        elif insignificant_spread:
            sg_mode = MODE_NORMAL
            reason = f"Minimal prisspridning ({price_spread * 100:.0f} öre)"
            confidence = 85
        elif current_price < EXTREME_LOW:
            sg_mode = MODE_BOOST
            reason = "⚡ Extremt lågt pris (<10 öre)"
            confidence = 100
        elif current_price > EXTREME_HIGH:
            sg_mode = MODE_BLOCK
            reason = "⚠️ Extremt högt pris (>5 kr)"
            confidence = 100
        elif price_percentile <= boost_percentile:
            sg_mode = MODE_BOOST
            reason = f"Låg percentil P{price_percentile:.0f} (billigaste {self.boost_pct:.0f}%)"
            confidence = 85
        elif price_percentile >= block_percentile:
            sg_mode = MODE_BLOCK
            reason = f"Hög percentil P{price_percentile:.0f} (dyraste {self.block_pct:.0f}%)"
            confidence = 85
        else:
            sg_mode = MODE_NORMAL
            reason = f"Normalläge P{price_percentile:.0f}"
            confidence = 75

        # POST-1: Production override (ersätter bara block, ej vid AI-override)
        prod_override_active = False
        if not ai_override_active:
            sg_mode, reason, prod_override_active = self._check_production_override(sg_mode, reason)
            if prod_override_active:
                confidence = 95

        # POST-2: Temperaturskydd (förhindrar bara block, ej vid AI/prod-override)
        indoor_temp = self._get_indoor_temp()
        if not ai_override_active and not prod_override_active and indoor_temp is not None and indoor_temp < self.min_temp and sg_mode == MODE_BLOCK:
            sg_mode = MODE_NORMAL
            reason = f"🌡 Temp för låg ({indoor_temp:.1f}°C < {self.min_temp}°C) — förhindrar block"
            confidence = 95
            temp_override_active = True

        # POST-3: Tariff blockerar boost globalt (sista steget, efter alla overrides)
        tariff_blocked = False
        if sg_mode == MODE_BOOST and not ai_override_active:
            tariff_entity = _conf(self.entry, CONF_TARIFF_ENTITY)
            if tariff_entity:
                t_state = self.hass.states.get(tariff_entity)
                if t_state and t_state.state in ("on", "true", "1", "active"):
                    sg_mode = MODE_NORMAL
                    reason = "⏰ Tariff aktiv — boost blockerad"
                    tariff_blocked = True

        # Sänk confidence om imorgondagens priser saknas sent
        if not has_tomorrow and current_hour >= 18:
            confidence = max(50, confidence - 10)
            reason += " [begränsad data]"
        elif not has_tomorrow:
            confidence = max(55, confidence - 5)

        _LOGGER.info("SG Ready: %s | %s | conf=%d%%", sg_mode.upper(), reason, confidence)

        return {
            "mode": sg_mode,
            "reason": reason,
            "confidence": confidence,
            "current_price": current_price,
            "price_percentile": round(price_percentile, 1),
            "price_vs_avg_pct": round(price_vs_avg * 100, 1),
            "diff_from_avg_ore": round(diff_from_avg * 100, 1),
            "price_spread": round(price_spread, 3),
            "spread_pct": round((price_spread / window_avg * 100) if window_avg else 0, 1),
            "insignificant_spread": insignificant_spread,
            "boost_threshold": round(boost_threshold, 3) if boost_threshold else None,
            "block_threshold": round(block_threshold, 3) if block_threshold else None,
            "window_size": len(window),
            "window_avg": round(window_avg, 3) if window_avg else None,
            "window_min": round(window_stats["min"], 3) if window_stats else None,
            "window_max": round(window_stats["max"], 3) if window_stats else None,
            "has_tomorrow": has_tomorrow,
            "indoor_temp": indoor_temp,
            "temp_override_active": temp_override_active,
            "prod_override_active": prod_override_active,
            "prod_override_mode": self._prod_state.get("mode"),
            "prod_override_in_hysteresis": self._prod_state.get("in_hysteresis", False),
            "prod_override_countdown": self._get_prod_countdown(),
            "tariff_blocked": tariff_blocked,
            "ai_override_active": ai_override_active,
            "ai_mode": effective_ai_mode,
            "ai_reason": self._ai_reason,
            "ai_until": self._ai_until.isoformat() if self._ai_until else None,
            "manual_override": self._manual_override,
            "boost_pct": self.boost_pct,
            "block_pct": self.block_pct,
            "min_temp": self.min_temp,
        }

    def _check_production_override(
        self, original_mode: str, original_reason: str
    ) -> tuple[str, str, bool]:
        """Production override — ersätter BARA 'block' vid eget överskott.
        
        Returnerar (new_mode, reason, override_active).
        Portat direkt från Node-RED 'Production Override Logic (med hysteres)'.
        """
        # Enabled?
        if not _conf(self.entry, CONF_PROD_ENABLED, True):
            return original_mode, original_reason, False

        # Hämta config från live-inställningar (tweakbara via HA-sliders)
        normal_threshold = self.prod_normal_threshold
        boost_threshold = self.prod_boost_threshold
        return_threshold = self.prod_return_threshold
        hysteresis = self.prod_hysteresis
        min_duration = self.prod_min_duration
        off_delay = self.prod_off_delay

        # Hämta mätardata
        grid_entity = _conf(self.entry, CONF_GRID_POWER_ENTITY)
        if not grid_entity:
            return original_mode, original_reason, False

        grid_state = self.hass.states.get(grid_entity)
        if not grid_state or grid_state.state in ("unknown", "unavailable"):
            return original_mode, original_reason, False

        try:
            meter_power = float(grid_state.state)
        except ValueError:
            return original_mode, original_reason, False

        # Kontrollera att mätardata är färsk (max 5 min)
        from homeassistant.util.dt import utcnow
        last_updated = grid_state.last_updated
        if (utcnow() - last_updated).total_seconds() > 300:
            _LOGGER.warning("Gammal mätardata — production override inaktiv")
            return original_mode, original_reason, False

        # Tariff-status
        in_tariff_period = False
        tariff_entity = _conf(self.entry, CONF_TARIFF_ENTITY)
        if tariff_entity:
            t_state = self.hass.states.get(tariff_entity)
            if t_state:
                in_tariff_period = t_state.state in ("on", "true", "1", "active")

        # Hysteres-tröskel vid återgång
        s = self._prod_state
        deactivation_threshold = return_threshold + (hysteresis if s["active"] else 0)
        now = datetime.now()
        surplus = abs(meter_power)

        if meter_power < normal_threshold:
            # Tillräckligt överskott
            if not s["active"]:
                if s["start_time"] is None:
                    s["start_time"] = now
                duration = (now - s["start_time"]).total_seconds()
                if duration >= min_duration:
                    s["active"] = True
                    s["last_change"] = now
                    s["in_hysteresis"] = False
                    # Välj läge
                    if surplus >= abs(boost_threshold) and (not in_tariff_period or meter_power < 0):
                        s["mode"] = MODE_BOOST
                        s["tariff_limited"] = False
                    elif surplus >= abs(boost_threshold):
                        s["mode"] = MODE_NORMAL
                        s["tariff_limited"] = True
                    else:
                        s["mode"] = MODE_NORMAL
                        s["tariff_limited"] = False
                    _LOGGER.info("Production override aktiverad: %s vid %dW", s["mode"], surplus)
            else:
                # Aktiv — uppdatera läge dynamiskt
                s["in_hysteresis"] = False
                s["last_change"] = now
                if surplus >= abs(boost_threshold):
                    if not in_tariff_period or meter_power < 0:
                        if s["mode"] != MODE_BOOST:
                            s["mode"] = MODE_BOOST
                            s["tariff_limited"] = False
                    elif s["mode"] == MODE_BOOST:
                        s["mode"] = MODE_NORMAL
                        s["tariff_limited"] = True
                elif surplus >= abs(normal_threshold):
                    if s["mode"] != MODE_NORMAL:
                        s["mode"] = MODE_NORMAL
                        s["tariff_limited"] = False

        elif meter_power > deactivation_threshold:
            # Över återgångströskel
            s["start_time"] = None
            if s["active"]:
                if not s["in_hysteresis"]:
                    s["in_hysteresis"] = True
                    s["last_change"] = now
                time_since = (now - s["last_change"]).total_seconds()
                if time_since >= off_delay:
                    s["active"] = False
                    s["mode"] = None
                    s["in_hysteresis"] = False
                    s["tariff_limited"] = False
                    _LOGGER.info("Production override inaktiverad efter %ds", off_delay)
        else:
            # Hysteres-zon
            if not s["active"]:
                s["start_time"] = None

        # Applicera — ENDAST om original_mode är "block"
        if s["active"] and s["mode"] and original_mode == MODE_BLOCK:
            power_str = f"{surplus:.0f}W överskott" if meter_power < 0 else f"{meter_power:.0f}W import"
            tariff_str = " (tariff-begränsad)" if s["tariff_limited"] else ""
            reason = f"🔋 Egen produktion: {power_str} → {s['mode']}{tariff_str}"
            return s["mode"], reason, True
        elif s["active"] and s["mode"] and original_mode != MODE_BLOCK:
            # Ursprungligt läge är inte block — låt vara
            s["active"] = False
            s["mode"] = None

        return original_mode, original_reason, False

    def _get_prod_countdown(self) -> dict:
        """Returnerar nedräkningsstatus för production override (som Node-RED status-text)."""
        s = self._prod_state
        now = datetime.now()
        min_duration = _conf(self.entry, CONF_PROD_MIN_DURATION, DEFAULT_PROD_MIN_DURATION)
        off_delay = _conf(self.entry, CONF_PROD_OFF_DELAY, DEFAULT_PROD_OFF_DELAY)

        if s["active"] and s["in_hysteresis"] and s["last_change"]:
            time_left = off_delay - (now - s["last_change"]).total_seconds()
            return {"state": "hysteresis", "seconds_left": max(0, round(time_left))}
        elif not s["active"] and s["start_time"]:
            duration = (now - s["start_time"]).total_seconds()
            time_left = min_duration - duration
            return {"state": "waiting", "seconds_left": max(0, round(time_left))}
        elif s["active"]:
            return {"state": "active", "seconds_left": 0}
        return {"state": "passive", "seconds_left": 0}

    def _get_indoor_temp(self) -> float | None:
        temp_entity = _conf(self.entry, CONF_TEMP_ENTITY)
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
        topic = _conf(self.entry, CONF_MQTT_TOPIC, DEFAULT_MQTT_TOPIC)
        await mqtt.async_publish(self.hass, topic, mode, qos=1, retain=True)
        _LOGGER.debug("MQTT → %s: %s", topic, mode)
