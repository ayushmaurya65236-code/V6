/*
  ============================================================
                       AURA LINK v4.0
                    ESP32 HARDWARE CORE
  ============================================================

  LOCAL NETWORK SYSTEM

  ESP32
     |
    Wi-Fi
     |
  Laptop / AURA SYSTEM

  HTTP:
      /
      /status
      /led/on
      /led/off

  UDP:
      Port 4210
      AURA_DISCOVER_V1

  SECURITY:
  - Replace the Wi-Fi placeholders below on your own device.
  - Never commit real Wi-Fi credentials to a public repository.
*/

#include <WiFi.h>
#include <WebServer.h>
#include <WiFiUdp.h>

// ============================================================
// WIFI CONFIGURATION
// ============================================================

// Replace these locally before uploading to your ESP32.
// Do not enter real credentials in a public GitHub commit.
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// ============================================================
// AURA DEVICE INFO
// ============================================================

const char* AURA_NAME = "AURA LINK";
const char* AURA_VERSION = "1.0";

// ============================================================
// BUILT-IN LED
// ============================================================

#ifndef LED_BUILTIN
#define LED_BUILTIN 2
#endif

const int LED_PIN = LED_BUILTIN;

// ============================================================
// SERVERS
// ============================================================

WebServer server(80);
WiFiUDP udp;
const uint16_t DISCOVERY_PORT = 4210;

// ============================================================
// STATE
// ============================================================

bool ledState = false;
char packetBuffer[128];

// ============================================================
// HTML HELPERS
// ============================================================

String ledText() {
  return ledState ? "ON" : "OFF";
}

String ledColor() {
  return ledState ? "#00ff88" : "#ff4060";
}

// ============================================================
// LED CONTROL
// ============================================================

void setLED(bool state) {
  ledState = state;
  digitalWrite(LED_PIN, state ? HIGH : LOW);

  Serial.print("[AURA] LED -> ");
  Serial.println(state ? "ON" : "OFF");
}

// ============================================================
// WEB DASHBOARD
// ============================================================

void handleHome() {
  String html = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AURA LINK</title>
<style>
body {
  margin: 0;
  padding: 0;
  background: #090909;
  color: white;
  font-family: Arial, Helvetica, sans-serif;
}
.container {
  width: 90%;
  max-width: 900px;
  margin: 50px auto;
}
.header {
  border-bottom: 1px solid #222;
  padding-bottom: 20px;
  margin-bottom: 30px;
}
.title {
  font-size: 42px;
  font-weight: bold;
  letter-spacing: 3px;
}
.subtitle {
  color: #00d9ff;
  margin-top: 8px;
  letter-spacing: 2px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 20px;
}
.card {
  background: #151515;
  border: 1px solid #292929;
  border-radius: 16px;
  padding: 25px;
}
.label {
  color: #777;
  font-size: 13px;
  letter-spacing: 2px;
  margin-bottom: 10px;
}
.value {
  font-size: 24px;
  font-weight: bold;
}
.online {
  color: #00ff88;
}
.offline {
  color: #ff4060;
}
.led {
  color: )rawliteral";

  html += ledColor();

  html += R"rawliteral(;
}
.buttons {
  display: flex;
  gap: 15px;
  margin-top: 25px;
  flex-wrap: wrap;
}
button {
  border: none;
  border-radius: 10px;
  padding: 15px 25px;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
}
.on {
  background: #00ff88;
  color: #000;
}
.off {
  background: #ff4060;
  color: #fff;
}
.footer {
  margin-top: 35px;
  color: #555;
  font-size: 13px;
}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="title">AURA LINK</div>
    <div class="subtitle">ESP32 HARDWARE CORE</div>
  </div>
  <div class="grid">
    <div class="card">
      <div class="label">SYSTEM</div>
      <div class="value online">ONLINE</div>
    </div>
    <div class="card">
      <div class="label">DEVICE</div>
      <div class="value">ESP32</div>
    </div>
    <div class="card">
      <div class="label">VERSION</div>
      <div class="value">1.0</div>
    </div>
    <div class="card">
      <div class="label">LED</div>
      <div class="value led">)rawliteral";

  html += ledText();

  html += R"rawliteral(</div>
    </div>
    <div class="card">
      <div class="label">IP ADDRESS</div>
      <div class="value">)rawliteral";

  html += WiFi.localIP().toString();

  html += R"rawliteral(</div>
    </div>
  </div>
  <div class="buttons">
    <button class="on" onclick="location.href='/led/on'">LED ON</button>
    <button class="off" onclick="location.href='/led/off'">LED OFF</button>
  </div>
  <div class="footer">
    AURA LINK v1.0 · Local Network Hardware Interface
  </div>
</div>
</body>
</html>
)rawliteral";

  server.send(200, "text/html", html);
}

// ============================================================
// STATUS
// ============================================================

void handleStatus() {
  String response;
  response += "AURA LINK\n";
  response += "VERSION: ";
  response += AURA_VERSION;
  response += "\n";
  response += "DEVICE: ESP32\n";
  response += "STATUS: ONLINE\n";
  response += "LED: ";
  response += ledState ? "ON\n" : "OFF\n";
  response += "IP: ";
  response += WiFi.localIP().toString();
  response += "\n";
  response += "MAC: ";
  response += WiFi.macAddress();
  response += "\n";

  server.send(200, "text/plain", response);
}

// ============================================================
// LED ON
// ============================================================

void handleLEDOn() {
  setLED(true);
  server.sendHeader("Location", "/");
  server.send(302, "text/plain", "LED ON");
}

// ============================================================
// LED OFF
// ============================================================

void handleLEDOff() {
  setLED(false);
  server.sendHeader("Location", "/");
  server.send(302, "text/plain", "LED OFF");
}

// ============================================================
// LED BLINK / STOP
// ============================================================

void handleLEDBlink() {
  for (int i = 0; i < 3; i++) {
    setLED(true);
    delay(180);
    setLED(false);
    delay(180);
  }
  server.sendHeader("Location", "/");
  server.send(302, "text/plain", "LED BLINK COMPLETE");
}

void handleStop() {
  // Safe stop for this LED-only firmware: leave the LED OFF.
  setLED(false);
  server.sendHeader("Location", "/");
  server.send(302, "text/plain", "STOPPED");
}

// ============================================================
// UNKNOWN ROUTE
// ============================================================

void handleNotFound() {
  server.send(404, "text/plain", "AURA LINK | UNKNOWN COMMAND");
}

// ============================================================
// UDP DISCOVERY
// ============================================================

void handleDiscovery() {
  int packetSize = udp.parsePacket();
  if (packetSize <= 0) {
    return;
  }

  int length = udp.read(packetBuffer, sizeof(packetBuffer) - 1);
  if (length <= 0) {
    return;
  }

  packetBuffer[length] = '\0';
  String request = String(packetBuffer);

  Serial.print("[AURA] UDP discovery: ");
  Serial.println(request);

  if (request == "AURA_DISCOVER_V1") {
    IPAddress clientIP = udp.remoteIP();
    uint16_t clientPort = udp.remotePort();

    String response;
    response += "AURA_LINK|";
    response += AURA_VERSION;
    response += "|ESP32|";
    response += WiFi.localIP().toString();
    response += "|";
    response += WiFi.macAddress();

    udp.beginPacket(clientIP, clientPort);
    udp.print(response);
    udp.endPacket();

    Serial.print("[AURA] Discovery reply -> ");
    Serial.println(clientIP);
  }
}

// ============================================================
// WIFI
// ============================================================

bool connectWiFi() {
  Serial.println();
  Serial.println("[AURA] Connecting to Wi-Fi...");

  WiFi.mode(WIFI_STA);
  WiFi.setHostname("AURA-LINK-ESP32");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 60) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[AURA] Wi-Fi connection FAILED.");
    return false;
  }

  Serial.println("Wi-Fi connected!");
  Serial.print("ESP32 IP address: ");
  Serial.println(WiFi.localIP());
  return true;
}

// ============================================================
// SETUP
// ============================================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(LED_PIN, OUTPUT);
  setLED(false);

  Serial.println();
  Serial.println("========================================");
  Serial.println("          AURA LINK v1.0");
  Serial.println("        ESP32 HARDWARE CORE");
  Serial.println("========================================");

  if (!connectWiFi()) {
    Serial.println("[AURA] SYSTEM HALTED");
    return;
  }

  server.on("/", HTTP_GET, handleHome);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/led/on", HTTP_GET, handleLEDOn);
  server.on("/led/off", HTTP_GET, handleLEDOff);
  server.on("/led/blink", HTTP_GET, handleLEDBlink);
  server.on("/stop", HTTP_GET, handleStop);
  server.onNotFound(handleNotFound);
  server.begin();

  udp.begin(DISCOVERY_PORT);

  Serial.println();
  Serial.println("AURA LINK server started.");
  Serial.println();
  Serial.println("Commands:");
  Serial.println("/");
  Serial.println("/led/on");
  Serial.println("/led/off");
  Serial.println("/status");
  Serial.print("UDP discovery port: ");
  Serial.println(DISCOVERY_PORT);
  Serial.println();
  Serial.println("AURA LINK READY.");
}

// ============================================================
// LOOP
// ============================================================

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    server.handleClient();
    handleDiscovery();
  }
}
