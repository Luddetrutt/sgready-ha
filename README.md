# SG Ready Styrning — Home Assistant Custom Integration

Smart styrning av värmepump via SG Ready-signaler baserat på Nord Pool-elpriser.

## Funktioner

- 🔥 **Boost** — billigaste X% av dygnet (laddar ackumulatortank, sänker framledning)
- ❄️ **Block** — dyraste Y% av dygnet (minimerar förbrukning)
- ✅ **Normal** — standardläge övriga timmar
- 🌡️ **Temperaturskydd** — block aktiveras aldrig om innetempen är under min-värdet
- ⚡ **Override** — manuell boost-switch

## Installation

1. Kopiera `custom_components/sgready/` till din HA `/config/custom_components/`
2. Starta om Home Assistant
3. Lägg till integration via **Inställningar → Enheter & Tjänster → Lägg till integration → SG Ready**

## Konfiguration

| Parameter | Beskrivning | Standard |
|---|---|---|
| Prisenhet | Nord Pool-sensor i HA | `sensor.nordpool_kwh_se4_sek_3` |
| Temperaturenhet | Inomhustermometer (valfri) | — |
| MQTT-topic | Vart läget publiceras | `homeassistant/sgready/control` |
| Boost-procent | % billigaste timmar | 15% |
| Block-procent | % dyraste timmar | 50% |
| Mintemperatur | Block-skydd | 20°C |

## Entiteter

| Entitet | Typ | Beskrivning |
|---|---|---|
| `sensor.sg_ready_läge` | Sensor | boost / normal / block |
| `sensor.sg_ready_aktuellt_pris` | Sensor | SEK/kWh |
| `sensor.sg_ready_prisrankning` | Sensor | P13/24 |
| `number.sg_ready_boost_procent` | Slider | 5–50% |
| `number.sg_ready_block_procent` | Slider | 10–80% |
| `number.sg_ready_mintemperatur` | Slider | 15–25°C |
| `switch.sg_ready_boost_override` | Switch | Manuell boost |

## Shelly-script

Shellyn i värmepumpen lyssnar på MQTT-topicet och kopplar de fysiska SG Ready-kontakterna:

```
boost  → Kontakt 1 = ON,  Kontakt 2 = ON
normal → Kontakt 1 = OFF, Kontakt 2 = OFF  
block  → Kontakt 1 = ON,  Kontakt 2 = OFF
```

## Utvecklat av

JL STYR AB — [jlstyr.se](https://jlstyr.se)
