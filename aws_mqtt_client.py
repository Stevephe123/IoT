
#!/usr/bin/env python3
import json
import ssl
import time
import paho.mqtt.client as mqtt
from datetime import datetime
import logging
import requests

logger = logging.getLogger(__name__)

class AWSIoTClient:
    def __init__(self, smart_farm_system):
        self.smart_farm = smart_farm_system
        
        # AWS IoT Core settings - UPDATE THESE WITH YOUR VALUES
        self.endpoint = "a33lwo3x84hk6s-ats.iot.ap-southeast-1.amazonaws.com"
        self.client_id = "SmartFarmDevice"
        self.thing_name = "SmartFarmDevice"
        
        # Certificate file paths - put your downloaded certificates here
        self.cert_dir = "certificates/"
        self.ca_cert = f"{self.cert_dir}AmazonRootCA1.pem"
        self.cert_file = f"{self.cert_dir}55e0c74e5986c96a8d935520e0d5d5ff5a3775d9067b0ad44de34e32c8e3c003-certificate.pem.crt"
        self.key_file = f"{self.cert_dir}55e0c74e5986c96a8d935520e0d5d5ff5a3775d9067b0ad44de34e32c8e3c003-private.pem.key"
        
        # MQTT Topics
        self.topics = {
            "telemetry": f"smartfarm/{self.thing_name}/telemetry",
            "commands": f"smartfarm/{self.thing_name}/commands", 
            "alerts": f"smartfarm/{self.thing_name}/alerts",
            "status": f"smartfarm/{self.thing_name}/status"
        }
        
        # Weather API (optional)
        self.weather_api_key = "e7f6e8cf2c4f7f26c500df56658af71d"  # Add your OpenWeather API key if you want
        
        self.connected = False
        self.setup_mqtt_client()
        
    def setup_mqtt_client(self):
        """Initialize MQTT client for AWS IoT"""
        try:
            self.client = mqtt.Client(self.client_id)
            
            # Configure TLS
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            context.load_verify_locations(self.ca_cert)
            context.load_cert_chain(self.cert_file, self.key_file)
            
            self.client.tls_set_context(context)
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            self.client.on_disconnect = self.on_disconnect
            
            logger.info("✅ AWS IoT MQTT client configured")
            
        except Exception as e:
            logger.error(f"❌ AWS IoT setup error: {e}")
            logger.error("Make sure certificate files are in certificates/ folder")
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to AWS IoT"""
        if rc == 0:
            self.connected = True
            logger.info("✅ Connected to AWS IoT Core!")
            
            # Subscribe to command topic
            client.subscribe(self.topics["commands"])
            logger.info(f"📡 Subscribed to {self.topics['commands']}")
            
            # Send initial status
            self.publish_status("CONNECTED")
            
        else:
            logger.error(f"❌ Failed to connect to AWS IoT: {rc}")
            
    def on_message(self, client, userdata, msg):
        """Handle incoming messages from AWS IoT"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            logger.info(f"📥 Command received: {payload}")
            
            if topic == self.topics["commands"]:
                self.process_cloud_command(payload)
                
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
    
    def on_disconnect(self, client, userdata, rc):
        """Handle disconnection"""
        self.connected = False
        logger.warning(f"⚠️ Disconnected from AWS IoT: {rc}")
    
    def connect(self):
        """Connect to AWS IoT Core"""
        try:
            logger.info("🔗 Connecting to AWS IoT Core...")
            self.client.connect(self.endpoint, 8883, 60)
            self.client.loop_start()
            
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
    
    def disconnect(self):
        """Disconnect from AWS IoT"""
        if self.connected:
            self.publish_status("DISCONNECTING")
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("✅ Disconnected from AWS IoT")
    
    def process_cloud_command(self, command):
        """Process commands from AWS IoT console"""
        try:
            command_type = command.get("type")
            
            if command_type == "actuator":
                actuator = command.get("actuator")
                action = command.get("action")
                
                # Map to Arduino commands
                arduino_commands = {
                    "irrigation": f"RELAY:{1 if action.upper() == 'ON' else 0}",
                    "gate": f"GATE:{action.upper()}",
                    "buzzer": f"BUZZER:{1 if action.upper() == 'ON' else 0}"
                }
                
                if actuator in arduino_commands:
                    success = self.smart_farm.send_arduino_command(arduino_commands[actuator])
                    
                    # Send response back to cloud
                    response = {
                        "timestamp": datetime.now().isoformat(),
                        "command_id": command.get("id", "unknown"),
                        "status": "success" if success else "failed",
                        "actuator": actuator,
                        "action": action
                    }
                    self.publish_message("status", response)
                    
            elif command_type == "system":
                action = command.get("action")
                if action == "get_status":
                    status = self.smart_farm.get_system_status()
                    self.publish_message("status", status)
                    
        except Exception as e:
            logger.error(f"❌ Command processing error: {e}")
    
    

    
    def publish_sensor_data(self, node_id, sensor_data):
        """Publish sensor data to AWS IoT"""
        if not self.connected:
            return
            
        try:
            # Get weather data if API key available
            weather_data = self.get_weather_data() if self.weather_api_key else {}
            
            # Create enriched payload
            payload = {
                "timestamp": datetime.now().isoformat(),
                "device_id": self.thing_name,
                "node_id": node_id,
                "location": self.smart_farm.location,
                "sensors": sensor_data,
                "weather": weather_data,
                "analytics": self.calculate_analytics(sensor_data)
            }
            
            self.publish_message("telemetry", payload)
            logger.info(f"📤 Published {node_id} data to AWS IoT")
            
        except Exception as e:
            logger.error(f"❌ Error publishing sensor data: {e}")
    
    def calculate_analytics(self, sensor_data):
        """Calculate analytics for cloud processing"""
        analytics = {}
        
        try:
            # Soil analysis
            if 'SOIL' in sensor_data:
                soil_raw = sensor_data['SOIL']
                soil_percent = max(0, min(100, (1023 - soil_raw) / 723 * 100))
                
                analytics["soil_analysis"] = {
                    "moisture_percent": soil_percent,
                    "condition": "dry" if soil_percent < 30 else "optimal" if soil_percent < 70 else "wet",
                    "irrigation_recommended": soil_percent < 30
                }
            
            # Environmental analysis
            if 'TEMP' in sensor_data and 'HUMID' in sensor_data:
                temp = sensor_data['TEMP']
                humid = sensor_data['HUMID']
                
                analytics["environmental"] = {
                    "temperature_celsius": temp,
                    "humidity_percent": humid,
                    "comfort_index": self.calculate_comfort_index(temp, humid),
                    "heat_stress": temp > 35
                }
            
            # Security analysis
            if 'PIR' in sensor_data:
                analytics["security"] = {
                    "motion_detected": sensor_data['PIR'] == 1,
                    "alert_level": "high" if sensor_data['PIR'] == 1 else "normal"
                }
                
        except Exception as e:
            logger.error(f"❌ Analytics calculation error: {e}")
        
        return analytics
    
    def calculate_comfort_index(self, temp, humidity):
        """Calculate plant comfort index"""
        # Simple comfort calculation for plants
        if 20 <= temp <= 30 and 40 <= humidity <= 70:
            return "optimal"
        elif 15 <= temp <= 35 and 30 <= humidity <= 80:
            return "acceptable"
        else:
            return "stress"
    
    def publish_alert(self, alert_type, message, severity="INFO", data=None):
        """Publish alerts to AWS IoT"""
        if not self.connected:
            return
            
        try:
            alert = {
                "timestamp": datetime.now().isoformat(),
                "device_id": self.thing_name,
                "alert_type": alert_type,
                "message": message,
                "severity": severity,
                "location": self.smart_farm.location,
                "data": data or {}
            }
            
            self.publish_message("alerts", alert)
            logger.info(f"🚨 Alert published: {alert_type}")
            
        except Exception as e:
            logger.error(f"❌ Error publishing alert: {e}")
    
    def publish_status(self, status):
        """Publish system status"""
        if not self.connected and status != "DISCONNECTING":
            return
            
        try:
            status_data = {
                "timestamp": datetime.now().isoformat(),
                "device_id": self.thing_name,
                "status": status,
                "system_info": self.smart_farm.get_system_status(),
                "uptime": time.time()
            }
            
            self.publish_message("status", status_data)
            
        except Exception as e:
            logger.error(f"❌ Error publishing status: {e}")
    
    def publish_message(self, topic_type, data):
        """Generic publish method"""
        if not self.connected:
            return
            
        try:
            topic = self.topics[topic_type]
            payload = json.dumps(data, default=str)
            result = self.client.publish(topic, payload, qos=1)
            
            if result.rc != 0:
                logger.error(f"❌ Failed to publish to {topic}")
                
        except Exception as e:
            logger.error(f"❌ Publish error: {e}")
    
    def get_weather_data(self):
        """Get weather data from OpenWeatherMap (optional)"""
        if not self.weather_api_key:
            return {}
            
        try:
            url = "http://api.openweathermap.org/data/2.5/weather"
            params = {
                "lat": self.smart_farm.location["lat"],
                "lon": self.smart_farm.location["lng"],
                "appid": self.weather_api_key,
                "units": "metric"
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {
                    "temperature": data["main"]["temp"],
                    "humidity": data["main"]["humidity"],
                    "description": data["weather"][0]["description"],
                    "pressure": data["main"]["pressure"],
                    "wind_speed": data.get("wind", {}).get("speed", 0)
                }
        except Exception as e:
            logger.error(f"❌ Weather API error: {e}")
        
        return {}
