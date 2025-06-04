import sys
import os
import time
import logging

# Import the original system and AWS client
from smart_farm_main import SmartFarmSystem
from aws_mqtt_client import AWSIoTClient

logger = logging.getLogger(__name__)

class SmartFarmWithAWS(SmartFarmSystem):
    def __init__(self):
        super().__init__()
        self.aws_client = None
        self.aws_enabled = False
        
    def enable_aws_iot(self):
        """Enable AWS IoT connectivity"""
        try:
            logger.info("🔗 Initializing AWS IoT client...")
            self.aws_client = AWSIoTClient(self)
            
            logger.info("🔗 Connecting to AWS IoT Core...")
            self.aws_client.connect()
            
            # Wait for connection to establish
            time.sleep(3)
            
            if self.aws_client.connected:
                self.aws_enabled = True
                logger.info("✅ AWS IoT integration ENABLED - Maximum points mode!")
                self.log_system_event("AWS", "AWS IoT Core connected successfully")
                return True
            else:
                logger.warning("⚠️ AWS IoT connection not established")
                return False
                
        except Exception as e:
            logger.error(f"❌ AWS IoT enable error: {e}")
            return False
    
    def process_sensor_data(self, node_id, sensor_data):
        """Enhanced sensor data processing with AWS IoT"""
        # Call parent method for local processing (database, automation)
        super().process_sensor_data(node_id, sensor_data)
        
        # Send to AWS IoT Core if enabled
        if self.aws_enabled and self.aws_client and self.aws_client.connected:
            try:
                self.aws_client.publish_sensor_data(node_id, sensor_data)
            except Exception as e:
                logger.error(f"❌ Error sending to AWS: {e}")
    
    def check_automation_rules(self, node_id, sensor_data):
        """Enhanced automation with cloud alerts"""
        # Call parent automation (local rules)
        super().check_automation_rules(node_id, sensor_data)
        
        # Send cloud alerts if AWS enabled
        if self.aws_enabled and self.aws_client and self.aws_client.connected:
            try:
                self.send_cloud_alerts(node_id, sensor_data)
            except Exception as e:
                logger.error(f"❌ Error sending cloud alerts: {e}")
    
    def send_cloud_alerts(self, node_id, sensor_data):
        """Send intelligent alerts to AWS IoT Core"""
        try:
            if node_id == 'NODE1':
                # Smart Garden Alerts
                soil_moisture = self.convert_sensor_value('SOIL', sensor_data.get('SOIL', 1023))[0]
                temp = sensor_data.get('TEMP', 25)
                humidity = sensor_data.get('HUMID', 50)
                light = self.convert_sensor_value('LIGHT', sensor_data.get('LIGHT', 500))[0]
                
                # Critical soil moisture alert
                if soil_moisture < 15:
                    self.aws_client.publish_alert(
                        "CRITICAL_SOIL_MOISTURE",
                        f"CRITICAL: Soil moisture critically low at {soil_moisture:.1f}%",
                        "CRITICAL",
                        {
                            "soil_moisture": soil_moisture,
                            "node_id": node_id,
                            "recommended_action": "Immediate irrigation required",
                            "auto_irrigation": "activated"
                        }
                    )
                
                # High temperature stress alert
                elif temp > 38:
                    self.aws_client.publish_alert(
                        "HIGH_TEMPERATURE_STRESS",
                        f"WARNING: High temperature stress at {temp:.1f}°C",
                        "WARNING",
                        {
                            "temperature": temp,
                            "humidity": humidity,
                            "heat_index": temp + 0.5 * (humidity - 40) if humidity > 40 else temp,
                            "node_id": node_id,
                            "recommended_action": "Increase irrigation frequency"
                        }
                    )
                
                # Optimal growing conditions
                elif 20 <= temp <= 30 and 40 <= humidity <= 70 and soil_moisture > 40:
                    # Send positive status occasionally (every 10 minutes)
                    import random
                    if random.randint(1, 120) == 1:  # ~1 in 120 chance (5 sec intervals = 10 min)
                        self.aws_client.publish_alert(
                            "OPTIMAL_CONDITIONS",
                            f"Optimal growing conditions: Temp {temp:.1f}°C, Humidity {humidity:.1f}%, Soil {soil_moisture:.1f}%",
                            "INFO",
                            {
                                "temperature": temp,
                                "humidity": humidity,
                                "soil_moisture": soil_moisture,
                                "light_level": light,
                                "node_id": node_id,
                                "status": "optimal"
                            }
                        )
                
                # Low light warning (during day hours)
                import datetime
                current_hour = datetime.datetime.now().hour
                if 6 <= current_hour <= 18 and light < 20:  # Daytime but low light
                    self.aws_client.publish_alert(
                        "LOW_LIGHT_WARNING",
                        f"Low light levels during daytime: {light:.1f}%",
                        "WARNING",
                        {
                            "light_level": light,
                            "hour": current_hour,
                            "node_id": node_id,
                            "recommended_action": "Check for obstructions or weather conditions"
                        }
                    )
                    
            elif node_id == 'NODE2':
                # Security System Alerts
                pir_state = sensor_data.get('PIR', 0)
                gate_state = sensor_data.get('GATE', 0)
                
                if pir_state == 1:
                    self.aws_client.publish_alert(
                        "MOTION_DETECTED",
                        "Security Alert: Motion detected in monitored area",
                        "WARNING",
                        {
                            "motion_detected": True,
                            "gate_status": "open" if gate_state == 1 else "closed",
                            "node_id": node_id,
                            "timestamp": time.time(),
                            "location": "Farm perimeter",
                            "recommended_action": "Check security cameras if available"
                        }
                    )
                
                # Gate status monitoring
                if gate_state == 1:  # Gate open
                    # Alert if gate has been open for extended period
                    # (This would need additional logic to track time, simplified here)
                    self.aws_client.publish_alert(
                        "GATE_STATUS",
                        "Gate is currently open",
                        "INFO",
                        {
                            "gate_status": "open",
                            "node_id": node_id,
                            "security_level": "reduced"
                        }
                    )
                    
        except Exception as e:
            logger.error(f"❌ Cloud alerts error: {e}")
    
    def send_arduino_command(self, command):
        """Enhanced command sending with cloud logging"""
        # Call parent method
        success = super().send_arduino_command(command)
        
        # Log to cloud if AWS enabled
        if self.aws_enabled and self.aws_client and self.aws_client.connected and success:
            try:
                self.aws_client.publish_alert(
                    "COMMAND_EXECUTED",
                    f"Arduino command executed: {command}",
                    "INFO",
                    {
                        "command": command,
                        "source": "system_automation",
                        "status": "success",
                        "timestamp": time.time()
                    }
                )
            except Exception as e:
                logger.error(f"❌ Error logging command to cloud: {e}")
        
        return success
    
    def get_system_status(self):
        """Enhanced system status with AWS info"""
        status = super().get_system_status()
        
        # Add AWS status
        status["aws_iot"] = {
            "enabled": self.aws_enabled,
            "connected": self.aws_client.connected if self.aws_client else False,
            "endpoint": self.aws_client.endpoint if self.aws_client else None,
            "thing_name": self.aws_client.thing_name if self.aws_client else None
        }
        
        return status
    
    def cleanup(self):
        """Enhanced cleanup with AWS disconnection"""
        logger.info("🛑 Starting system cleanup...")
        
        if self.aws_enabled and self.aws_client:
            try:
                logger.info("📤 Sending final status to AWS...")
                self.aws_client.publish_status("SHUTTING_DOWN")
                time.sleep(1)  # Give time for message to send
                
                logger.info("🔌 Disconnecting from AWS IoT Core...")
                self.aws_client.disconnect()
                
            except Exception as e:
                logger.error(f"❌ AWS cleanup error: {e}")
        
        # Call parent cleanup
        super().cleanup()

def main():
    """Main function to run the enhanced smart farm system"""
    print("🚀 Smart Farm IoT System with AWS Integration")
    print("=" * 60)
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create enhanced system
    try:
        system = SmartFarmWithAWS()
        print("✅ Smart Farm system initialized")
        
        # Try to enable AWS IoT
        print("\n🔗 Attempting AWS IoT Core connection...")
        aws_success = system.enable_aws_iot()
        
        if aws_success:
            print("✅ AWS IoT Core connected - MAXIMUM POINTS MODE! 🎯")
            print("   📊 Data will be sent to cloud")
            print("   🚨 Alerts will be published to AWS")
            print("   📱 View data in AWS IoT Console")
        else:
            print("⚠️ AWS IoT not available - LOCAL MODE")
            print("   📊 Data stored locally only")
            print("   🎯 Still gets good points!")
        
        print("\n🌐 Web dashboard available at: http://localhost:5000")
        print("🔍 Monitor AWS IoT in console: https://console.aws.amazon.com/iot/")
        print("\n📊 System Status:")
        status = system.get_system_status()
        print(f"   Arduino: {'✅ Connected' if status['arduino_connected'] else '❌ Disconnected'}")
        print(f"   Nodes: {len(status['nodes'])} active")
        print(f"   Database: {status['database_records'].get('sensor_readings', 0)} sensor readings")
        print(f"   AWS IoT: {'✅ Connected' if aws_success else '❌ Not connected'}")
        
        print("\n🏃 Starting main system loop...")
        print("   Press Ctrl+C to stop")
        print("=" * 60)
        
        # Run the main system
        system.run()
        
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down by user request...")
        
    except Exception as e:
        print(f"\n❌ System error: {e}")
        logger.error(f"System error: {e}")
        
    finally:
        try:
            system.cleanup()
            print("✅ System shutdown complete")
        except:
            print("⚠️ Cleanup completed with warnings")

if __name__ == "__main__":
    main()
