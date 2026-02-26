# SG Ready Styrning — Home Assistant Custom Integration

Smart styrning av värmepump via SG Ready-signaler baserat på Nord Pool-elpriser.

---

## Förutsättningar

Innan du installerar SG Ready behöver du ha dessa integrationer installerade och konfigurerade i HA:

1. **Nord Pool** (via HACS) — hämtar spotpriser per timme
   - Installera via HACS → Integrations → sök "Nord Pool"
   - Konfigurera: välj ditt elområde (SE1–SE4)
   - Verifieras under: Inställningar → Enheter & Tjänster → Nord Pool

2. **MQTT** (inbyggd i HA) — skickar styrkommandon till värmepumpen
   - Konfigurera via: Inställningar → Enheter & Tjänster → Lägg till → MQTT
   - Behöver en MQTT-broker, t.ex. Mosquitto (tillägg i HA)

---

## Installation

### Via Studio Code Server (rekommenderas)

```bash
cd /config/custom_components
git clone https://github.com/Luddetrutt/sgready-ha.git _tmp
cp -r _tmp/custom_components/sgready .
rm -rf _tmp
```

Starta om Home Assistant.

### Uppdatering

```bash
cd /config/custom_components
rm -rf _tmp
git clone https://github.com/Luddetrutt/sgready-ha.git _tmp
cp -r _tmp/custom_components/sgready .
rm -rf _tmp
```

Starta om Home Assistant.

---

## Konfiguration

Gå till **Inställningar → Enheter & Tjänster → Lägg till integration → SG Ready Styrning**

Konfigurationsguiden hittar automatiskt din Nord Pool-integration och presenterar den i en dropdown — du behöver inte leta upp något ID manuellt.

| Fält | Beskrivning | Krav |
|---|---|---|
| Nord Pool-integration | Väljs automatiskt från dropdown | Obligatorisk |
| Elområde | SE1 / SE2 / SE3 / SE4 | Obligatorisk |
| MQTT-topic styrkommando | Där läget publiceras | Obligatorisk |
| MQTT-topic AI-override | För extern AI-styrning | Valfri |
| Inomhustermometer | Temperaturskydd för block | Valfri |
| Elmätare / nettomätare | Aktiverar produktionsöverstyrning (solceller) | Valfri |
| Tariff-sensor | Blockerar boost vid högtariff | Valfri |

---

## Entiteter

### Sensorer
| Entitet | Beskrivning |
|---|---|
| `sensor.sg_ready_läge` | Aktuellt läge: boost / normal / block |
| `sensor.sg_ready_aktuellt_pris` | Elpriset just nu (SEK/kWh) |
| `sensor.sg_ready_prisrankning` | Prisrankning, t.ex. P13/24 |

### Sliders (justeras direkt i dashboarden, bevaras vid omstart)
| Entitet | Beskrivning | Default |
|---|---|---|
| `number.sg_ready_boost_procent` | % billigaste timmar som ger boost | 30% |
| `number.sg_ready_block_procent` | % dyraste timmar som blockeras | 30% |
| `number.sg_ready_mintemperatur` | Temperaturskydd — block ej aktivt under denna temp | 20°C |
| `number.sg_ready_produktion_normal_tröskel` | Exportnivå (W) för normal-läge | −100 W |
| `number.sg_ready_produktion_boost_tröskel` | Exportnivå (W) för boost-läge | −500 W |
| `number.sg_ready_produktion_återgångs_tröskel` | Importnivå (W) för att deaktivera | 50 W |
| `number.sg_ready_produktion_hysteres` | Hysteres (W) mot snabb växling | 50 W |
| `number.sg_ready_produktion_aktiveringstid` | Sekunder med överskott innan aktivering | 300 s |
| `number.sg_ready_produktion_avstängningstid` | Sekunder med import innan deaktivering | 600 s |

### Övriga entiteter
| Entitet | Beskrivning |
|---|---|
| `switch.sg_ready_boost_override` | Manuell boost (P0 — överrider allt) |
| `select.sg_ready_ai_override` | AI-override: force_boost / force_normal / force_block / auto |

---

## Prioritetsordning

```
P0a  Manuell switch         → Boost direkt
P0b  AI override            → force_boost / normal / block + tidsbegränsning
P1   Minimal prisspridning  → Normal (om spread < 10 öre)
P2   Extrempris             → Boost (< 0,10 kr) / Block (> 5,00 kr)
P3   Percentil              → Boost / Block / Normal (centrerat 24h-fönster)
P4   Övrigt                 → Normal
─────────────────────────────────────────────────────
POST-1  Produktionsöverstyrning  → Ersätter BARA block vid solöverskott
POST-2  Temperaturskydd          → Ersätter BARA block vid kall inomhusluft
POST-3  Tariff                   → Nedgraderar boost → normal vid högtariff
```

---

## Shelly-script

Shellyn i värmepumpen lyssnar på MQTT-topicet och kopplar de fysiska SG Ready-kontakterna:

```
boost  → Kontakt 1 = ON,  Kontakt 2 = ON
normal → Kontakt 1 = OFF, Kontakt 2 = OFF
block  → Kontakt 1 = ON,  Kontakt 2 = OFF
```

---

## Lovelace-dashboard

Färdigt kort finns i [`lovelace-card.yaml`](lovelace-card.yaml).

Lägg till det via **Dashboard → Redigera → Lägg till kort → Manuell** och klistra in innehållet.

> **Tips:** Kontrollera entity-ID:na under Inställningar → Enheter & Tjänster → SG Ready → Entiteter om något kort inte visas. Svenska tecken (ä/ö/å) kan påverka det automatgenererade ID:t.

---

## Utvecklat av

JL STYR AB — [jlstyr.se](https://jlstyr.se)
