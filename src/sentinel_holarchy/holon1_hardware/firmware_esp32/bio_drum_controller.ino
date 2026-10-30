/*
 * ==============================================================================
 * SENTINEL-HOLARCHY | ESP32 FIRMWARE FOR BIO-DRUM 60L HARDWARE CONTROLLER
 * Target: ESP32-WROOM-32 / NodeMCU ESP32
 * ==============================================================================
 * Interfaces:
 * - Analog pH Sensor (BNC Probe on GPIO 34)
 * - Analog ORP Sensor (BNC Probe on GPIO 35)
 * - DS18B20 1-Wire Digital Temp Sensor (GPIO 4)
 * - Tachometer / Optical Encoder for Drum RPM (GPIO 18)
 * - Relays:
 *   - PIN 25: Drum Inverter Speed PWM / Motor Direction
 *   - PIN 26: Aeration Pump 12V
 *   - PIN 27: Heating Mat / Solid-State Relay (PID controlled)
 *   - PIN 32: VFA Liquid Transfer Valve
 *   - PIN 33: Waste Drain Centrifuge Valve
 * 
 * Telemetry: JSON over WiFi / HTTP POST or MQTT to Local Gateway.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>

// WiFi Configuration
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* gateway_url = "http://192.168.1.100:5000/api/telemetry";

// Pin Definitions
#define PIN_PH 34
#define PIN_ORP 35
#define PIN_ONEWIRE_TEMP 4
#define PIN_TACHO 18

#define RELAY_MOTOR_PWM 25
#define RELAY_AERATION 26
#define RELAY_HEATER 27
#define VALVE_TRANSFER 32
#define VALVE_DRAIN 33

// Sensors
OneWire oneWire(PIN_ONEWIRE_TEMP);
DallasTemperature tempSensor(&oneWire);

// State tracking
float current_ph = 7.0;
float current_orp_mv = 0.0;
float current_temp_c = 22.0;
volatile unsigned int pulseCount = 0;
float current_rpm = 0.0;

unsigned long lastTelemetryTime = 0;
const unsigned long telemetryInterval = 5000; // Send telemetry every 5 sec

void IRAM_ATTR countPulse() {
  pulseCount++;
}

void setup() {
  Serial.begin(115200);
  Serial.println(">>> SENTINEL BIO-DRUM 60L CONTROLLER INITIALIZING <<<");

  // Relay Pins Setup
  pinMode(RELAY_MOTOR_PWM, OUTPUT);
  pinMode(RELAY_AERATION, OUTPUT);
  pinMode(RELAY_HEATER, OUTPUT);
  pinMode(VALVE_TRANSFER, OUTPUT);
  pinMode(VALVE_DRAIN, OUTPUT);

  digitalWrite(RELAY_MOTOR_PWM, LOW);
  digitalWrite(RELAY_AERATION, LOW);
  digitalWrite(RELAY_HEATER, LOW);
  digitalWrite(VALVE_TRANSFER, LOW);
  digitalWrite(VALVE_DRAIN, LOW);

  // Tachometer Interrupt
  pinMode(PIN_TACHO, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_TACHO), countPulse, FALLING);

  // Temp sensor init
  tempSensor.begin();

  // WiFi Connect
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected! IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("\nRunning in standalone offline telemetry mode.");
  }
}

void readSensors() {
  // Read Temperature
  tempSensor.requestTemperatures();
  current_temp_c = tempSensor.getTempCByIndex(0);
  if (current_temp_c < -10.0 || current_temp_c > 100.0) {
    current_temp_c = 22.0; // Sensor fallback
  }

  // Read pH (ADC 12-bit on 3.3V)
  int phRaw = analogRead(PIN_PH);
  float phVoltage = phRaw * (3.3 / 4095.0);
  // Calibration: standard linear mapping 3.5 * voltage + offset
  current_ph = 7.0 - (phVoltage - 1.65) * 3.5;

  // Read ORP
  int orpRaw = analogRead(PIN_ORP);
  float orpVoltage = orpRaw * (3.3 / 4095.0);
  current_orp_mv = (orpVoltage - 1.65) * 1000.0;

  // Calculate RPM
  detachInterrupt(digitalPinToInterrupt(PIN_TACHO));
  current_rpm = (pulseCount / 2.0) * 60.0; // 2 pulses per revolution
  pulseCount = 0;
  attachInterrupt(digitalPinToInterrupt(PIN_TACHO), countPulse, FALLING);
}

void sendTelemetry() {
  StaticJsonDocument<256> doc;
  doc["device_id"] = "ESP32-CLAMART-01";
  doc["batch_id"] = "BATCH-CLAMART-LOCAL";
  doc["temp_c"] = current_temp_c;
  doc["ph"] = current_ph;
  doc["orp_mv"] = current_orp_mv;
  doc["drum_rpm"] = current_rpm;
  doc["heater_status"] = digitalRead(RELAY_HEATER) == HIGH;
  doc["aeration_status"] = digitalRead(RELAY_AERATION) == HIGH;

  String jsonString;
  serializeJson(doc, jsonString);
  Serial.println("[TELEMETRY] " + jsonString);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(gateway_url);
    http.addHeader("Content-Type", "application/json");
    int httpResponseCode = http.POST(jsonString);
    if (httpResponseCode > 0) {
      Serial.printf("HTTP Response code: %d\n", httpResponseCode);
    }
    http.end();
  }
}

void loop() {
  readSensors();

  // Basic onboard thermal safety: keep slurry around 28-30C during acidogenesis
  if (current_temp_c < 27.5) {
    digitalWrite(RELAY_HEATER, HIGH);
  } else if (current_temp_c > 30.5) {
    digitalWrite(RELAY_HEATER, LOW);
  }

  if (millis() - lastTelemetryTime >= telemetryInterval) {
    sendTelemetry();
    lastTelemetryTime = millis();
  }

  delay(200);
}
