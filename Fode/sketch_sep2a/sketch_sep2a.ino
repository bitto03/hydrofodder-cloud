#include <WiFi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <WebSocketsServer.h>

// =====================================================
// ESP32 4-CHANNEL RELAY CONTROLLER
// AP MODE + WEB DASHBOARD + WEBSOCKET
// =====================================================

// -------------------- AP SETTINGS --------------------

const char* AP_SSID = "IoT";
const char* AP_PASSWORD = "87654321";

// ESP32 AP IP
IPAddress local_IP(192, 168, 4, 1);
IPAddress gateway(192, 168, 4, 1);
IPAddress subnet(255, 255, 255, 0);

// -------------------- RELAY PINS ----------------------

#define RELAY1 23
#define RELAY2 22
#define RELAY3 21
#define RELAY4 19

const int relayPins[4] = {
  RELAY1,
  RELAY2,
  RELAY3,
  RELAY4
};

// -----------------------------------------------------
// Relay module type
//
// Most 4-channel relay modules are ACTIVE LOW:
//
// LOW  = Relay ON
// HIGH = Relay OFF
//
// If your relay works opposite, change these:
// -----------------------------------------------------

#define RELAY_ON  LOW
#define RELAY_OFF HIGH

// -------------------- SERVERS -------------------------

AsyncWebServer server(80);
WebSocketsServer webSocket = WebSocketsServer(81);

// Relay states
bool relayState[4] = {
  false,
  false,
  false,
  false
};

// =====================================================
// WEB DASHBOARD
// =====================================================

const char index_html[] PROGMEM = R"rawliteral(

<!DOCTYPE html>

<html>

<head>

<meta name="viewport" content="width=device-width, initial-scale=1">

<title>ESP32 Relay Control</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    padding: 0;
    font-family: Arial, Helvetica, sans-serif;
    background: #101820;
    color: white;
}

.header {
    padding: 25px;
    text-align: center;
    background: #17232d;
    box-shadow: 0 2px 10px rgba(0,0,0,0.4);
}

.header h1 {
    margin: 0;
    font-size: 28px;
}

.header p {
    margin-top: 8px;
    color: #aaa;
}

.container {
    max-width: 900px;
    margin: auto;
    padding: 25px;
}

.connection {
    text-align: center;
    padding: 12px;
    margin-bottom: 25px;
    border-radius: 10px;
    background: #333;
}

.online {
    background: #0c6b3d;
}

.offline {
    background: #8b2020;
}

.relay-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 20px;
}

.relay-card {
    background: #1c2933;
    border-radius: 15px;
    padding: 25px;
    text-align: center;
    box-shadow: 0 5px 15px rgba(0,0,0,0.3);
}

.relay-card h2 {
    margin-top: 0;
}

.status {
    font-size: 18px;
    font-weight: bold;
    margin: 15px 0;
}

.status.on {
    color: #00ff88;
}

.status.off {
    color: #ff5555;
}

button {
    width: 100%;
    padding: 13px;
    margin-top: 8px;
    border: none;
    border-radius: 8px;
    color: white;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
}

.on-btn {
    background: #087f4f;
}

.off-btn {
    background: #a52525;
}

.on-btn:hover {
    background: #09a765;
}

.off-btn:hover {
    background: #d33131;
}

.master {
    margin-top: 30px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
}

.all-on {
    background: #087f4f;
}

.all-off {
    background: #a52525;
}

.info {
    margin-top: 30px;
    padding: 20px;
    background: #17232d;
    border-radius: 12px;
    text-align: center;
    color: #aaa;
}

.ip {
    color: #00c8ff;
    font-weight: bold;
}

</style>

</head>

<body>

<div class="header">

<h1>ESP32 Relay Controller</h1>

<p>4 Channel Wireless Relay Dashboard</p>

</div>


<div class="container">

<div id="connection" class="connection offline">

 Connecting...

</div>


<div class="relay-grid">


<!-- RELAY 1 -->

<div class="relay-card">

<h2>Relay 1</h2>

<div id="status1" class="status off">

OFF

</div>

<button class="on-btn" onclick="relayControl(1, 1)">

TURN ON

</button>

<button class="off-btn" onclick="relayControl(1, 0)">

TURN OFF

</button>

</div>


<!-- RELAY 2 -->

<div class="relay-card">

<h2>Relay 2</h2>

<div id="status2" class="status off">

OFF

</div>

<button class="on-btn" onclick="relayControl(2, 1)">

TURN ON

</button>

<button class="off-btn" onclick="relayControl(2, 0)">

TURN OFF

</button>

</div>


<!-- RELAY 3 -->

<div class="relay-card">

<h2>Relay 3</h2>

<div id="status3" class="status off">

OFF

</div>

<button class="on-btn" onclick="relayControl(3, 1)">

TURN ON

</button>

<button class="off-btn" onclick="relayControl(3, 0)">

TURN OFF

</button>

</div>


<!-- RELAY 4 -->

<div class="relay-card">

<h2>Relay 4</h2>

<div id="status4" class="status off">

OFF

</div>

<button class="on-btn" onclick="relayControl(4, 1)">

TURN ON

</button>

<button class="off-btn" onclick="relayControl(4, 0)">

TURN OFF

</button>

</div>

</div>


<!-- MASTER CONTROL -->

<div class="master">

<button class="all-on" onclick="allRelays(1)">

 ALL ON

</button>

<button class="all-off" onclick="allRelays(0)">

 ALL OFF

</button>

</div>


<div class="info">

<p>ESP32 Access Point</p>

<p>

IP Address:

<span class="ip">192.168.4.1</span>

</p>

</div>

</div>


<script>

let websocket;

function connectWebSocket() {

    websocket = new WebSocket("ws://" + window.location.hostname + ":81/");

    websocket.onopen = function() {

        console.log("WebSocket Connected");

        let connection = document.getElementById("connection");

        connection.innerHTML = " WebSocket Connected";

        connection.classList.remove("offline");

        connection.classList.add("online");

    };


    websocket.onclose = function() {

        console.log("WebSocket Disconnected");

        let connection = document.getElementById("connection");

        connection.innerHTML = " WebSocket Disconnected";

        connection.classList.remove("online");

        connection.classList.add("offline");

        setTimeout(connectWebSocket, 2000);

    };


    websocket.onmessage = function(event) {

        console.log("Received:", event.data);

        updateDashboard(event.data);

    };

}


function relayControl(relay, state) {

    if (websocket.readyState === WebSocket.OPEN) {

        let command = "RELAY" + relay + ":" + state;

        websocket.send(command);

    }

}


function allRelays(state) {

    if (websocket.readyState === WebSocket.OPEN) {

        websocket.send("ALL:" + state);

    }

}


function updateDashboard(message) {

    // Example:

    // STATE:1,0,1,0

    if (!message.startsWith("STATE:")) {

        return;

    }

    let states = message.substring(6).split(",");


    for (let i = 0; i < 4; i++) {

        let status = document.getElementById("status" + (i + 1));

        if (states[i] === "1") {

            status.innerHTML = "ON";

            status.classList.remove("off");

            status.classList.add("on");

        }

        else {

            status.innerHTML = "OFF";

            status.classList.remove("on");

            status.classList.add("off");

        }

    }

}


connectWebSocket();

</script>

</body>

</html>

)rawliteral";


// =====================================================
// UPDATE RELAY
// =====================================================

void setRelay(int relay, bool state) {

  if (relay < 0 || relay >= 4) {
    return;
  }

  relayState[relay] = state;

  if (state) {
    digitalWrite(relayPins[relay], RELAY_ON);
  }
  else {
    digitalWrite(relayPins[relay], RELAY_OFF);
  }

  Serial.print("Relay ");
  Serial.print(relay + 1);
  Serial.print(" -> ");

  if (state) {
    Serial.println("ON");
  }
  else {
    Serial.println("OFF");
  }
}


// =====================================================
// SEND CURRENT STATE TO ALL CLIENTS
// =====================================================

void sendRelayStates() {

  String message = "STATE:";

  for (int i = 0; i < 4; i++) {

    message += relayState[i] ? "1" : "0";

    if (i < 3) {
      message += ",";
    }

  }

  webSocket.broadcastTXT(message);

  Serial.print("Broadcast: ");
  Serial.println(message);
}


// =====================================================
// WEBSOCKET EVENT
// =====================================================

void webSocketEvent(
  uint8_t num,
  WStype_t type,
  uint8_t *payload,
  size_t length
) {

  switch (type) {

    // -------------------------------------------------
    // CLIENT CONNECTED
    // -------------------------------------------------

    case WStype_CONNECTED:

      Serial.print("WebSocket client connected: ");
      Serial.println(num);

      // Send current relay states to new client

      {

        String message = "STATE:";

        for (int i = 0; i < 4; i++) {

          message += relayState[i] ? "1" : "0";

          if (i < 3) {
            message += ",";
          }

        }

        webSocket.sendTXT(num, message);

      }

      break;


    // -------------------------------------------------
    // CLIENT DISCONNECTED
    // -------------------------------------------------

    case WStype_DISCONNECTED:

      Serial.print("WebSocket client disconnected: ");
      Serial.println(num);

      break;


    // -------------------------------------------------
    // MESSAGE RECEIVED
    // -------------------------------------------------

    case WStype_TEXT:

      {

        String command = "";

        for (size_t i = 0; i < length; i++) {
          command += (char)payload[i];
        }

        Serial.print("Command received: ");
        Serial.println(command);


        // ---------------------------------------------
        // RELAY COMMAND
        //
        // RELAY1:1
        // RELAY1:0
        // ---------------------------------------------

        if (command.startsWith("RELAY")) {

          int relayNumber = command.substring(5, 6).toInt();

          int separator = command.indexOf(":");

          if (separator != -1) {

            int state =
              command.substring(separator + 1).toInt();

            if (relayNumber >= 1 && relayNumber <= 4) {

              setRelay(
                relayNumber - 1,
                state == 1
              );

              sendRelayStates();

            }

          }

        }


        // ---------------------------------------------
        // ALL RELAYS
        //
        // ALL:1
        // ALL:0
        // ---------------------------------------------

        else if (command.startsWith("ALL:")) {

          int state =
            command.substring(4).toInt();

          for (int i = 0; i < 4; i++) {

            setRelay(
              i,
              state == 1
            );

          }

          sendRelayStates();

        }

      }

      break;


    default:

      break;

  }

}


// =====================================================
// SETUP
// =====================================================

void setup() {

  Serial.begin(115200);

  delay(1000);

  Serial.println();
  Serial.println("=================================");
  Serial.println(" ESP32 4-CHANNEL RELAY SYSTEM");
  Serial.println("=================================");


  // ---------------------------------------------------
  // Configure relay pins
  // ---------------------------------------------------

  for (int i = 0; i < 4; i++) {

    pinMode(relayPins[i], OUTPUT);

    // Start with all relays OFF

    digitalWrite(
      relayPins[i],
      RELAY_OFF
    );

    relayState[i] = false;

  }


  // ---------------------------------------------------
  // Configure Access Point
  // ---------------------------------------------------

  WiFi.mode(WIFI_AP);

  WiFi.softAPConfig(
    local_IP,
    gateway,
    subnet
  );


  bool apStarted =
    WiFi.softAP(
      AP_SSID,
      AP_PASSWORD
    );


  if (apStarted) {

    Serial.println();
    Serial.println("Access Point Started!");

    Serial.print("SSID: ");
    Serial.println(AP_SSID);

    Serial.print("Password: ");
    Serial.println(AP_PASSWORD);

    Serial.print("IP Address: ");
    Serial.println(WiFi.softAPIP());

  }

  else {

    Serial.println(
      "Failed to start Access Point!"
    );

  }


  // ---------------------------------------------------
  // HTTP SERVER
  // ---------------------------------------------------

  server.on(
    "/",
    HTTP_GET,
    [](AsyncWebServerRequest *request) {

      request->send_P(
        200,
        "text/html",
        index_html
      );

    }
  );


  server.begin();

  Serial.println();
  Serial.println("HTTP Server Started");


  // ---------------------------------------------------
  // WEBSOCKET SERVER
  // ---------------------------------------------------

  webSocket.begin();

  webSocket.onEvent(webSocketEvent);

  Serial.println(
    "WebSocket Server Started on Port 81"
  );


  Serial.println();
  Serial.println("---------------------------------");
  Serial.println("Connect your phone/PC to:");
  Serial.println(AP_SSID);
  Serial.println();
  Serial.println("Open browser:");
  Serial.println("http://192.168.4.1");
  Serial.println("---------------------------------");

}


// =====================================================
// LOOP
// =====================================================

void loop() {

  webSocket.loop();

}