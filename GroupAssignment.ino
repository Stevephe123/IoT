#include <DHT.h>
#include <SPI.h>
#include <Servo.h>

// Pin Definitions
#define SOIL_PIN A0
#define LDR_PIN A1
#define DHTPIN 2
#define DHTTYPE DHT11
#define RELAY_PIN 7
#define SOIL_LED 8
#define PIR_PIN 3
#define BUZZER_PIN 4
#define SERVO_PIN 5
#define GATE_LED 6
#define BUTTON_PIN 9

// Objects
DHT dht(DHTPIN, DHTTYPE);
Servo gateServo;

// Variables
bool gateOpen = false;
unsigned long lastDebounceTime = 0;
unsigned long debounceDelay = 50;
int lastButtonState = HIGH;
int buttonState;

// CRITICAL: Data sending variables
unsigned long lastDataSend = 0;
const unsigned long DATA_SEND_INTERVAL = 3000; // Send every 3 seconds (faster for testing)

void setup() {
  Serial.begin(9600);
  Serial.println("Smart Farm System Starting...");
  
  dht.begin();
  SPI.begin();
  gateServo.attach(SERVO_PIN);
  
  pinMode(SOIL_PIN, INPUT);
  pinMode(LDR_PIN, INPUT);
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(SOIL_LED, OUTPUT);
  pinMode(GATE_LED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(PIR_PIN, INPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  digitalWrite(RELAY_PIN, LOW);
  digitalWrite(SOIL_LED, LOW);
  digitalWrite(GATE_LED, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  gateServo.write(0);
  
  Serial.println("SYSTEM_READY");
  Serial.println("Data will be sent every 3 seconds...");
}

void loop() {
  Serial.println("Loop Start");
  
  handleSmartGarden();
  handlePIRandBuzzer();
  handleButtonAndServo();
  
  // SEND DATA EVERY 3 SECONDS - NO MATTER WHAT
  if (millis() - lastDataSend >= DATA_SEND_INTERVAL) {
    Serial.println("=== SENDING DATA TO RASPBERRY PI ===");
    sendDataToRPi();
    lastDataSend = millis();
    Serial.println("=== DATA SENT ===");
  }
  
  processRPiCommands();
  
  Serial.println("Loop End\n");
  delay(1000); // Shorter delay for faster response
}

// Your existing functions (keep as-is)
void handleSmartGarden() {
  Serial.println("Reading sensors...");
  int soilValue = analogRead(SOIL_PIN);
  int light = analogRead(LDR_PIN);
  float temp = dht.readTemperature();
  float humid = dht.readHumidity();
  
  if (isnan(temp) || isnan(humid)) {
    Serial.println("Warning: Failed to read from DHT sensor. Using defaults.");
    temp = 25.0;   // Default temperature
    humid = 60.0;  // Default humidity
  }
  
  Serial.print("Soil: "); Serial.print(soilValue);
  Serial.print(" | Temp: "); Serial.print(temp);
  Serial.print("°C | Humidity: "); Serial.print(humid);
  Serial.print("% | Light: "); Serial.println(light);
  
  if (soilValue < 500) {
    digitalWrite(RELAY_PIN, HIGH);
    digitalWrite(SOIL_LED, HIGH);
    Serial.println("Soil is wet enough. No watering needed (Relay OFF, LED OFF).");
  } else {
    digitalWrite(RELAY_PIN, LOW);
    digitalWrite(SOIL_LED, LOW);
    Serial.println("Soil is dry. Watering activated (Relay ON, LED ON).");
  }
}

void handlePIRandBuzzer() {
  int pirState = digitalRead(PIR_PIN);
  if (pirState == HIGH) {
    Serial.println("PIR: Motion Detected. Buzzer ON.");
    digitalWrite(BUZZER_PIN, HIGH);
  } else {
    Serial.println("PIR: No Motion. Buzzer OFF.");
    digitalWrite(BUZZER_PIN, LOW);
  }
}

void handleButtonAndServo() {
  int reading = digitalRead(BUTTON_PIN);
  
  if (reading != lastButtonState) {
    lastDebounceTime = millis();
  }
  
  if ((millis() - lastDebounceTime) > debounceDelay) {
    if (reading != buttonState) {
      buttonState = reading;
      
      if (buttonState == LOW) {
        gateOpen = !gateOpen;
        if (gateOpen) {
          gateServo.write(90);
          digitalWrite(GATE_LED, HIGH);
          Serial.println("Button pressed: Gate OPENED.");
        } else {
          gateServo.write(0);
          digitalWrite(GATE_LED, LOW);
          Serial.println("Button pressed: Gate CLOSED.");
        }
      }
    }
  }
  
  lastButtonState = reading;
  
  if (gateOpen) {
    Serial.println("Gate is currently OPEN.");
  } else {
    Serial.println("Gate is currently CLOSED.");
  }
}

// CRITICAL FUNCTION: Send data every 3 seconds
void sendDataToRPi() {
  int soilValue = analogRead(SOIL_PIN);
  int light = analogRead(LDR_PIN);
  float temp = dht.readTemperature();
  float humid = dht.readHumidity();
  int pirState = digitalRead(PIR_PIN);
  
  // Handle sensor errors
  if (isnan(temp) || isnan(humid)) {
    Serial.println("ERROR|DHT_SENSOR_FAIL");
    temp = 25.0;   // Use default values
    humid = 60.0;
  }
  
  // Send Node 1 data
  Serial.print("NODE1|");
  Serial.print("SOIL:" + String(soilValue) + "|");
  Serial.print("TEMP:" + String(temp, 1) + "|");
  Serial.print("HUMID:" + String(humid, 1) + "|");
  Serial.print("LIGHT:" + String(light) + "|");
  Serial.print("RELAY:" + String(digitalRead(RELAY_PIN)) + "|");
  Serial.println("SOIL_LED:" + String(digitalRead(SOIL_LED)));
  
  // Send Node 2 data
  Serial.print("NODE2|");
  Serial.print("PIR:" + String(pirState) + "|");
  Serial.print("GATE:" + String(gateOpen ? 1 : 0) + "|");
  Serial.print("BUZZER:" + String(digitalRead(BUZZER_PIN)) + "|");
  Serial.println("GATE_LED:" + String(digitalRead(GATE_LED)));
}

void processRPiCommands() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command.startsWith("RELAY:")) {
      int value = command.substring(6).toInt();
      digitalWrite(RELAY_PIN, value);
      digitalWrite(SOIL_LED, value);
      Serial.println("ACK|RELAY:" + String(value));
    }
    else if (command.startsWith("GATE:")) {
      String action = command.substring(5);
      if (action == "OPEN") {
        gateServo.write(90);
        gateOpen = true;
        digitalWrite(GATE_LED, HIGH);
        Serial.println("ACK|GATE:OPEN");
      } else if (action == "CLOSE") {
        gateServo.write(0);
        gateOpen = false;
        digitalWrite(GATE_LED, LOW);
        Serial.println("ACK|GATE:CLOSE");
      }
    }
    else if (command == "STATUS") {
      Serial.println("STATUS|ONLINE|" + String(millis()));
    }
  }
}
