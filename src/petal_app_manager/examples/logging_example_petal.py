"""
Example Petal demonstrating the CSV signal logging tool.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import time
import math
import threading
from typing import Dict, List, Optional

from ..plugins.base import Petal
from ..plugins.decorators import petal_action
from ..utils.log_tool import open_channel


class LoggingExamplePetal(Petal):
    """Example petal that demonstrates the use of the logging tool."""
    
    name = "logging_example"
    version = "0.1.0"
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.log_channels = {}
        self.thread = None
    
    def startup(self):
        """Initialize the petal."""
        self.logger.info("LoggingExample petal starting up")
    
    def shutdown(self):
        """Clean up resources."""
        self.stop_logging()
        self.logger.info("LoggingExample petal shutting down")
    
    @petal_action(protocol="http", method="POST", path="/start_logging")
    async def start_logging(self) -> Dict[str, str]:
        """Start generating and logging sample data."""
        if self.running:
            return {"status": "already_running"}
        
        try:
            # Create log channels - timestamp is automatically included as first column (as integer ms)
            self.log_channels = {
                "sine": open_channel(
                    "sine_value", 
                    base_dir="example_logs",
                    use_ms=True  # Millisecond precision (default)
                ),
                "position": open_channel(
                    ["pos_x", "pos_y", "pos_z"], 
                    base_dir="example_logs",
                    file_name="position_data",
                    use_ms=True  # Millisecond precision (default)
                ),
                "attitude": open_channel(
                    ["roll", "pitch", "yaw"], 
                    base_dir="example_logs",
                    file_name="attitude_data",
                    use_ms=True  # Millisecond precision (default)
                )
            }
            
            self.running = True
            self.thread = threading.Thread(target=self._logging_loop)
            self.thread.daemon = True
            self.thread.start()
            
            return {
                "status": "started",
                "channels": list(self.log_channels.keys())
            }
            
        except Exception as e:
            self.logger.error(f"Error starting logging: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @petal_action(protocol="http", method="POST", path="/stop_logging")
    async def stop_logging(self) -> Dict[str, str]:
        """Stop logging and close all channels."""
        if not self.running:
            return {"status": "not_running"}
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            
        # Close all channels
        for name, channel in self.log_channels.items():
            try:
                channel.close()
            except Exception as e:
                self.logger.error(f"Error closing channel {name}: {e}")
                
        self.log_channels = {}
        return {"status": "stopped"}
    
    @petal_action(protocol="http", method="GET", path="/status")
    async def get_status(self) -> Dict[str, any]:
        """Get the current logging status."""
        return {
            "running": self.running,
            "channels": list(self.log_channels.keys()),
        }
    
    def _logging_loop(self):
        """Background thread that generates and logs sample data."""
        start_time = time.time()
        try:
            while self.running:
                # Current time in seconds since start
                t = time.time() - start_time
                
                # Generate sample values
                sine_value = math.sin(t)
                
                # Position data (simulating a circular path)
                radius = 10
                pos_x = radius * math.cos(t * 0.5)
                pos_y = radius * math.sin(t * 0.5)
                pos_z = 5 + math.sin(t * 0.2)
                
                # Attitude data (simulated)
                roll = 10 * math.sin(t * 0.3)
                pitch = 15 * math.sin(t * 0.2)
                yaw = (t * 10) % 360
                
                # Log the values
                if "sine" in self.log_channels:
                    self.log_channels["sine"].push(sine_value)
                    
                if "position" in self.log_channels:
                    self.log_channels["position"].push([pos_x, pos_y, pos_z])
                    
                if "attitude" in self.log_channels:
                    self.log_channels["attitude"].push([roll, pitch, yaw])
                
                # Sleep to control the logging rate (10 Hz)
                time.sleep(0.1)
                
        except Exception as e:
            self.logger.error(f"Error in logging thread: {e}")
            self.running = False
