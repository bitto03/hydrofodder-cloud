/*
  HydroFodder ESP32 transport skeleton for Phase 1/2.
  IMPORTANT: This sketch intentionally leaves cloud TLS/provisioning integration for the next phase.
  Validate your relay board's ACTIVE HIGH/LOW behavior and electrical ratings before connecting loads.
*/
#include <WiFi.h>
#include <DHT.h>

#define DHT_PIN 4
#define DHT_TYPE DHT11
DHT dht(DHT_PIN, DHT_TYPE);

const uint8_t RELAY_PINS[4] = {16, 17, 18, 19};
const bool RELAY_ACTIVE_LOW = true; // VERIFY YOUR RELAY MODULE
bool relayState[4] = {false,false,false,false};
unsigned long lastSensorMs = 0;

void writeRelay(uint8_t channel, bool on) {
  if (channel < 1 || channel > 4) return;
  relayState[channel-1] = on;
  int level = RELAY_ACTIVE_LOW ? (on ? LOW : HIGH) : (on ? HIGH : LOW);
  digitalWrite(RELAY_PINS[channel-1], level);
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  for (int i=0;i<4;i++) { pinMode(RELAY_PINS[i], OUTPUT); writeRelay(i+1, false); }
  // Next phase: load provisioned Wi-Fi/device credentials from NVS and connect non-blockingly.
}

void loop() {
  const unsigned long now = millis();
  if (now - lastSensorMs >= 5000) {
    lastSensorMs = now;
    float h = dht.readHumidity();
    float t = dht.readTemperature();
    if (!isnan(h) && !isnan(t)) {
      Serial.printf("temperature=%.1fC humidity=%.1f%%\n", t, h);
      // Next phase: publish telemetry through the authenticated transport adapter.
    } else {
      Serial.println("DHT11 read failed");
    }
  }
  // No blocking delay: transport reconnect, command processing, watchdog and schedules go here.
}
