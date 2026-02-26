/**
 * Shelly EM — Grid Power till MQTT
 * JL Styr AB
 *
 * Publicerar näteffekten (W) till MQTT var 10:e sekund.
 * Positivt värde = import (köper från nätet)
 * Negativt värde = export (säljer till nätet / solöverskott)
 *
 * Topic: homeassistant/sgready/grid_power
 * Payload: numeriskt värde i watt, t.ex. -1250 eller 340
 *
 * Installation:
 *   1. Öppna Shelly EM i webbläsaren → Scripts → Skapa nytt script
 *   2. Klistra in denna kod
 *   3. Aktivera "Run on startup"
 *   4. Spara och starta
 *
 * Kontrollera att MQTT är aktiverat under Settings → MQTT i Shelly-gränssnittet.
 */

// ── Konfiguration ────────────────────────────────────────────────────────────
var TOPIC   = "homeassistant/sgready/grid_power";
var CHANNEL = 0;       // 0 = kanal 1 (nätanslutning), 1 = kanal 2
var INTERVAL_MS = 10000;  // publiceringsintervall i millisekunder
// ─────────────────────────────────────────────────────────────────────────────

function publishPower() {
  Shelly.call("EM.GetStatus", { id: CHANNEL }, function (result, err) {
    if (err !== 0 || !result) {
      print("EM.GetStatus fel:", err);
      return;
    }

    // act_power: positiv = import, negativ = export
    var power = result.act_power;
    if (typeof power !== "number") {
      print("Oväntat svar:", JSON.stringify(result));
      return;
    }

    // Runda av till hela watt
    var rounded = Math.round(power);

    MQTT.publish(TOPIC, String(rounded), 0, false);
    print("Publicerat:", rounded, "W →", TOPIC);
  });
}

// Kör direkt vid start, sedan var INTERVAL_MS
publishPower();
Timer.set(INTERVAL_MS, true, publishPower);
