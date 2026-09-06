/*
  HydroFodder Cloud - ESP32 HTTP device firmware (local development transport)

  Cloud API contract:
    POST /api/device/heartbeat/
    POST /api/device/telemetry/
    GET  /api/device/commands/
    POST /api/device/commands/{uuid}/ack/

  Device authentication headers:
    X-Device-UID
    X-Device-Token

  IMPORTANT:
  - This local-development sketch uses plain HTTP on your trusted LAN.
  - Use HTTPS/TLS or MQTT/TLS in production.
  - Verify relay active LOW/HIGH behavior before connecting pumps or mains loads.
  - "actual_state" here means the ESP32 GPIO/output state, not proof that a pump
    physically moved water. Add current/flow feedback for true actuator verification.
*/

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <time.h>

#include "secrets.h"

// ---------------- Hardware ----------------
#define DHT_PIN 4
#define DHT_TYPE DHT11

DHT dht(DHT_PIN, DHT_TYPE);

const uint8_t RELAY_PINS[4] = {22, 23, 18, 19};

// Many 4-channel relay boards are active LOW, but NOT all are.
// Test with loads disconnected first.
const bool RELAY_ACTIVE_LOW = true;

bool relayState[4] = {false, false, false, false};

// ---------------- Firmware ----------------
const char *FIRMWARE_VERSION = "Fodder v1";

// Polling intervals for local MVP.
const unsigned long COMMAND_POLL_INTERVAL_MS = 1000;
const unsigned long TELEMETRY_INTERVAL_MS    = 5000;
const unsigned long HEARTBEAT_INTERVAL_MS    = 10000;
const unsigned long WIFI_RETRY_INTERVAL_MS   = 5000;

unsigned long lastCommandPollMs = 0;
unsigned long lastTelemetryMs   = 0;
unsigned long lastHeartbeatMs   = 0;
unsigned long lastWifiRetryMs   = 0;

// ---------------- Relay control ----------------
void setRelay(uint8_t channel, bool on) {
  if (channel < 1 || channel > 4) {
    Serial.printf("[RELAY] Invalid channel: %u\n", channel);
    return;
  }

  const uint8_t index = channel - 1;
  const uint8_t outputLevel = RELAY_ACTIVE_LOW
                                ? (on ? LOW : HIGH)
                                : (on ? HIGH : LOW);

  digitalWrite(RELAY_PINS[index], outputLevel);
  relayState[index] = on;

  Serial.printf("[RELAY] Channel %u -> %s\n", channel, on ? "ON" : "OFF");
}

bool getRelayState(uint8_t channel) {
  if (channel < 1 || channel > 4) {
    return false;
  }
  return relayState[channel - 1];
}

// ---------------- Wi-Fi ----------------
void beginWiFi() {
  Serial.printf("[WIFI] Connecting to %s\n", WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void maintainWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  const unsigned long now = millis();
  if (now - lastWifiRetryMs < WIFI_RETRY_INTERVAL_MS) {
    return;
  }

  lastWifiRetryMs = now;
  Serial.println("[WIFI] Disconnected. Reconnecting...");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

// ---------------- Time / UTC ----------------
void beginClockSync() {
  // Keep device clock in UTC. The cloud stores timezone-aware timestamps.
  configTime(0, 0, "pool.ntp.org", "time.google.com", "time.cloudflare.com");
}

bool clockIsValid() {
  return time(nullptr) > 1700000000;  // sanity check: after 2023-11
}

String utcTimestamp() {
  time_t now = time(nullptr);
  if (now <= 1700000000) {
    return "";
  }

  struct tm tmUtc;
  gmtime_r(&now, &tmUtc);

  char buffer[25];
  strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &tmUtc);
  return String(buffer);
}

// ---------------- HTTP helpers ----------------
bool beginAuthenticatedRequest(HTTPClient &http, const String &url) {
  http.setConnectTimeout(4000);
  http.setTimeout(5000);

  if (!http.begin(url)) {
    Serial.printf("[HTTP] begin() failed: %s\n", url.c_str());
    return false;
  }

  http.addHeader("X-Device-UID", DEVICE_UID);
  http.addHeader("X-Device-Token", DEVICE_TOKEN);
  http.addHeader("Accept", "application/json");
  return true;
}

void printHttpFailure(const char *operation, int statusCode, const String &body) {
  Serial.printf("[HTTP] %s failed. status=%d", operation, statusCode);
  if (body.length() > 0) {
    Serial.printf(" body=%s", body.c_str());
  }
  Serial.println();
}

// ---------------- Heartbeat ----------------
bool sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  const String url = String(SERVER_BASE_URL) + "/api/device/heartbeat/";

  if (!beginAuthenticatedRequest(http, url)) {
    return false;
  }

  http.addHeader("Content-Type", "application/json");

  JsonDocument doc;
  doc["firmware_version"] = FIRMWARE_VERSION;

  String payload;
  serializeJson(doc, payload);

  const int statusCode = http.POST(payload);
  const String responseBody = statusCode > 0 ? http.getString() : "";
  http.end();

  if (statusCode >= 200 && statusCode < 300) {
    Serial.println("[HEARTBEAT] OK");
    return true;
  }

  printHttpFailure("heartbeat", statusCode, responseBody);
  return false;
}

// ---------------- Telemetry ----------------
bool sendTelemetry(float temperatureC, float humidityPct) {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  const String recordedAt = utcTimestamp();
  if (recordedAt.length() == 0) {
    Serial.println("[TELEMETRY] Clock not synchronized yet; skipping sample.");
    return false;
  }

  HTTPClient http;
  const String url = String(SERVER_BASE_URL) + "/api/device/telemetry/";

  if (!beginAuthenticatedRequest(http, url)) {
    return false;
  }

  http.addHeader("Content-Type", "application/json");

  JsonDocument doc;
  doc["temperature_c"] = temperatureC;
  doc["humidity_pct"] = humidityPct;
  doc["recorded_at"] = recordedAt;

  String payload;
  serializeJson(doc, payload);

  const int statusCode = http.POST(payload);
  const String responseBody = statusCode > 0 ? http.getString() : "";
  http.end();

  if (statusCode >= 200 && statusCode < 300) {
    Serial.printf(
      "[TELEMETRY] OK temp=%.2fC humidity=%.2f%% at %s\n",
      temperatureC,
      humidityPct,
      recordedAt.c_str()
    );
    return true;
  }

  printHttpFailure("telemetry", statusCode, responseBody);
  return false;
}

// ---------------- Command ACK ----------------
bool acknowledgeCommand(
  const String &commandId,
  bool success,
  bool actualState,
  const String &errorMessage = ""
) {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  const String url = String(SERVER_BASE_URL)
                   + "/api/device/commands/"
                   + commandId
                   + "/ack/";

  if (!beginAuthenticatedRequest(http, url)) {
    return false;
  }

  http.addHeader("Content-Type", "application/json");

  JsonDocument doc;
  doc["success"] = success;
  doc["actual_state"] = actualState;
  if (errorMessage.length() > 0) {
    doc["error"] = errorMessage;
  }

  String payload;
  serializeJson(doc, payload);

  const int statusCode = http.POST(payload);
  const String responseBody = statusCode > 0 ? http.getString() : "";
  http.end();

  if (statusCode >= 200 && statusCode < 300) {
    Serial.printf("[ACK] command=%s OK\n", commandId.c_str());
    return true;
  }

  printHttpFailure("command ACK", statusCode, responseBody);
  return false;
}

// ---------------- Command polling ----------------
void pollCommands() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  HTTPClient http;
  const String url = String(SERVER_BASE_URL) + "/api/device/commands/";

  if (!beginAuthenticatedRequest(http, url)) {
    return;
  }

  const int statusCode = http.GET();
  const String responseBody = statusCode > 0 ? http.getString() : "";
  http.end();

  if (statusCode < 200 || statusCode >= 300) {
    printHttpFailure("command poll", statusCode, responseBody);
    return;
  }

  JsonDocument doc;
  const DeserializationError jsonError = deserializeJson(doc, responseBody);
  if (jsonError) {
    Serial.printf("[JSON] Command response parse failed: %s\n", jsonError.c_str());
    return;
  }

  JsonArray commands = doc["commands"].as<JsonArray>();
  if (commands.isNull()) {
    Serial.println("[JSON] Missing commands array");
    return;
  }

  for (JsonObject command : commands) {
    const char *idValue = command["id"] | "";
    const int channel = command["relay_channel"] | 0;
    const bool desiredState = command["state"] | false;

    if (strlen(idValue) == 0 || channel < 1 || channel > 4) {
      Serial.println("[COMMAND] Invalid command payload; ignoring.");
      continue;
    }

    const String commandId(idValue);

    Serial.printf(
      "[COMMAND] id=%s relay=%d requested=%s\n",
      commandId.c_str(),
      channel,
      desiredState ? "ON" : "OFF"
    );

    // State-setting commands are intentionally idempotent. If ACK transmission
    // fails and Django returns the same pending command again, applying it again
    // is safe for ON/OFF state control.
    setRelay(static_cast<uint8_t>(channel), desiredState);

    const bool actualState = getRelayState(static_cast<uint8_t>(channel));
    const bool success = actualState == desiredState;

    acknowledgeCommand(
      commandId,
      success,
      actualState,
      success ? "" : "GPIO state did not match requested state"
    );
  }
}

// ---------------- Sensor task ----------------
void readAndSendDht() {
  const float humidity = dht.readHumidity();
  const float temperature = dht.readTemperature();

  if (isnan(humidity) || isnan(temperature)) {
    Serial.println("[DHT11] Read failed");
    return;
  }

  // Backend validation currently accepts -40..80 C and 0..100 %RH.
  if (temperature < -40.0f || temperature > 80.0f ||
      humidity < 0.0f || humidity > 100.0f) {
    Serial.println("[DHT11] Reading outside accepted range; ignoring.");
    return;
  }

  sendTelemetry(temperature, humidity);
}

// ---------------- Setup / Loop ----------------
void setup() {
  Serial.begin(115200);
  delay(100);

  Serial.println();
  Serial.println("========================================");
  Serial.println(" HydroFodder ESP32 HTTP Device Firmware ");
  Serial.println("========================================");

  // IMPORTANT: set outputs to OFF before initializing the relay module.
  for (uint8_t i = 0; i < 4; ++i) {
    pinMode(RELAY_PINS[i], OUTPUT);
  }

  for (uint8_t channel = 1; channel <= 4; ++channel) {
    setRelay(channel, false);
  }

  dht.begin();
  beginWiFi();
  beginClockSync();
}

void loop() {
  maintainWiFi();

  if (WiFi.status() != WL_CONNECTED) {
    delay(5);  // small yield; no long blocking wait
    return;
  }

  static bool printedConnectionInfo = false;
  if (!printedConnectionInfo) {
    printedConnectionInfo = true;
    Serial.printf("[WIFI] Connected. IP=%s RSSI=%d dBm\n",
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
    Serial.printf("[CLOUD] %s\n", SERVER_BASE_URL);
  }

  const unsigned long now = millis();

  if (now - lastCommandPollMs >= COMMAND_POLL_INTERVAL_MS) {
    lastCommandPollMs = now;
    pollCommands();
  }

  if (now - lastTelemetryMs >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryMs = now;
    readAndSendDht();
  }

  if (now - lastHeartbeatMs >= HEARTBEAT_INTERVAL_MS) {
    lastHeartbeatMs = now;
    sendHeartbeat();
  }

  delay(2); // yield to Wi-Fi/RTOS; not a scheduling delay
}
