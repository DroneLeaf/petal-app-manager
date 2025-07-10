#!/usr/bin/env python3
"""
Example demonstrating burst sending and duplicate message filtering
with the MAVLink External Proxy.
"""

import asyncio
import logging
from pathlib import Path
import sys

# Add the parent directory to the path to import petal_app_manager
sys.path.append(str(Path(__file__).parent.parent))

from proxies.external import MavLinkExternalProxy
from pymavlink import mavutil

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main example function demonstrating burst and filtering features."""
    
    # Create MAVLink proxy
    proxy = MavLinkExternalProxy(
        endpoint="udp:127.0.0.1:14551",  # SITL default
        maxlen=500
    )
    
    try:
        # Start the proxy
        await proxy.start()
        logger.info("MAVLink proxy started")
        
        # Example 1: Register a filtered handler for ATTITUDE messages
        # This will filter out duplicate ATTITUDE messages within 0.5 seconds
        def attitude_handler(msg):
            logger.info(f"Received ATTITUDE: roll={msg.roll:.2f}, pitch={msg.pitch:.2f}, yaw={msg.yaw:.2f}")
        
        proxy.register_handler(
            "ATTITUDE", 
            attitude_handler, 
            duplicate_filter_interval=0.5
        )
        
        # Example 2: Register a normal handler (no filtering) for comparison
        def global_pos_handler(msg):
            logger.info(f"Received GLOBAL_POSITION_INT: lat={msg.lat}, lon={msg.lon}, alt={msg.alt}")
            
        proxy.register_handler("GLOBAL_POSITION_INT", global_pos_handler)
        
        # Example 3: Send a burst of heartbeat messages
        if proxy.master:
            heartbeat_msg = proxy.master.mav.heartbeat_encode(
                mavutil.mavlink.MAV_TYPE_GCS,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                0, 0,
                mavutil.mavlink.MAV_STATE_ACTIVE
            )
            
            logger.info("Sending burst of 5 heartbeat messages with 1-second intervals")
            proxy.send("mav", heartbeat_msg, burst_count=5, burst_interval=1.0)
            
            # Example 4: Send a burst of parameter requests (immediate burst)
            param_req_msg = proxy.master.mav.param_request_list_encode(
                proxy.target_system,
                proxy.target_component
            )
            
            logger.info("Sending immediate burst of 3 parameter request messages")
            proxy.send("mav", param_req_msg, burst_count=3)
        
        # Example 5: Using the base send method with burst parameters
        if proxy.master:
            # Request ATTITUDE messages
            attitude_req = proxy.build_req_msg_long(mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE)
            
            logger.info("Requesting ATTITUDE messages with burst")
            proxy.send("mav", attitude_req, burst_count=2, burst_interval=0.5)
        
        # Let the proxy run for a while to see messages
        logger.info("Listening for messages for 30 seconds...")
        await asyncio.sleep(30)
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        # Stop the proxy
        await proxy.stop()
        logger.info("MAVLink proxy stopped")


if __name__ == "__main__":
    asyncio.run(main())
