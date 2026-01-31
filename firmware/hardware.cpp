#include <ArduinoJson.h>
#include <ESP8266WiFi.h>
#include <WebSocketsClient.h>

/*
 * SMART DORMITORY - Wemos D1 Mini (ESP8266) Firmware
 *
 * Dependencies (install via Library Manager):
 * 1. WebSockets by Markus Sattler (Links2004)
 * 2. ArduinoJson by Benoit Blanchon (v6.x)
 */

// --- WIFI CONFIGURATION ---
const char *ssid = "YOUR_WIFI_SSID";         // <-- Enter your WiFi Name
const char *password = "YOUR_WIFI_PASSWORD"; // <-- Enter your WiFi Password

// --- SERVER CONFIGURATION ---
// IMPORTANT: Use your computer's local IP address (e.g., 192.168.1.X), not
// localhost!
const char *serverHost = "shohruxyigitaliev.uz"; // Custom Domain
const uint16_t serverPort = 80; // Use 80 for WS (http) or 443 for WSS (https)
const char *deviceId = "desk_light_1"; // Unique name for this device

// --- HARDWARE CONFIGURATION ---
// Wemos D1 Mini: LED_BUILTIN is usually D4 (GPIO2) and is inverted (LOW = ON)
const int RELAY_PIN = LED_BUILTIN;
const bool INVERT_LOGIC = true; // Set true if LOW signal turns the light ON

WebSocketsClient webSocket;
String currentState = "OFF";

// --- HELPER FUNCTIONS ---

void setLight(bool on) {
  if (on) {
    digitalWrite(RELAY_PIN, INVERT_LOGIC ? LOW : HIGH);
    currentState = "ON";
  } else {
    digitalWrite(RELAY_PIN, INVERT_LOGIC ? HIGH : LOW);
    currentState = "OFF";
  }
  Serial.printf("Light is now %s\n", currentState.c_str());
}

// Send initial Hello message
void sendHello() {
  StaticJsonDocument<200> doc;
  doc["type"] = "device_hello";
  doc["device_id"] = deviceId;
  doc["state"] = currentState;

  String output;
  serializeJson(doc, output);
  webSocket.sendTXT(output);
}

// Respond to Ping
void sendPong() {
  StaticJsonDocument<50> doc;
  doc["type"] = "pong";
  String output;
  serializeJson(doc, output);
  webSocket.sendTXT(output);
}

// Confirm state change to server
void sendStateUpdate() {
  StaticJsonDocument<200> doc;
  doc["type"] = "state_update";
  doc["device_id"] = deviceId;
  doc["state"] = currentState;

  String output;
  serializeJson(doc, output);
  webSocket.sendTXT(output);
}

// --- WEBSOCKET EVENT HANDLER ---

void webSocketEvent(WStype_t type, uint8_t *payload, size_t length) {
  switch (type) {
  case WStype_DISCONNECTED:
    Serial.printf("[WSc] Disconnected!\n");
    break;

  case WStype_CONNECTED: {
    Serial.printf("[WSc] Connected to url: %s\n", payload);
    sendHello(); // Identify ourselves upon connection
  } break;

  case WStype_TEXT: {
    Serial.printf("[WSc] get text: %s\n", payload);

    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, payload);

    if (error) {
      Serial.print(F("deserializeJson() failed: "));
      Serial.println(error.f_str());
      return;
    }

    const char *msgType = doc["type"];

    // 1. Handle PING (Heartbeat)
    if (strcmp(msgType, "ping") == 0) {
      Serial.println("Ping received -> Sending Pong");
      sendPong();
    }
    // 2. Handle State Sync (Server Authority)
    else if (strcmp(msgType, "sync_state") == 0) {
      const char *newState = doc["state"];
      Serial.printf("Sync State received: %s\n", newState);
      bool turnOn = (strcmp(newState, "ON") == 0);
      setLight(turnOn);
    }
    // 3. Handle Commands (Manual Control)
    else if (strcmp(msgType, "command") == 0) {
      const char *action = doc["action"];
      if (strcmp(action, "TURN_ON") == 0) {
        setLight(true);
        sendStateUpdate();
      } else if (strcmp(action, "TURN_OFF") == 0) {
        setLight(false);
        sendStateUpdate();
      }
    }
  } break;

  case WStype_BIN:
  case WStype_ERROR:
  case WStype_FRAGMENT_TEXT_START:
  case WStype_FRAGMENT_BIN_START:
  case WStype_FRAGMENT:
  case WStype_FRAGMENT_FIN:
    break;
  }
}

// --- MAIN SETUP ---

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  setLight(false); // Default OFF

  Serial.println();
  Serial.println("--------------------------------");
  Serial.println("SMART DORMITORY - DEVICE BOOTING");
  Serial.println("--------------------------------");

  // Connect to WiFi
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.print("WiFi connected! IP: ");
  Serial.println(WiFi.localIP());

  // Connect to WebSocket Server
  Serial.printf("Connecting to Server: %s:%d\n", serverHost, serverPort);
  webSocket.begin(serverHost, serverPort, "/ws");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000); // Try to reconnect every 5s if lost
}

// --- MAIN LOOP ---

void loop() { webSocket.loop(); }
