from __future__ import annotations
import asyncio, sys, time
from pathlib import Path
from types import SimpleNamespace

import pytest
from pymavlink import mavutil
from pymavlink.dialects.v10 import common as mavlink

# --------------------------------------------------------------------------- #
# package under test                                                          #
# --------------------------------------------------------------------------- #
from petal_app_manager.proxies.external import (
    MavLinkExternalProxy
)

@pytest.mark.hardware
def test_external_proxy():
    # Use a pytest fixture to run async test
    asyncio.run(_test_mavlink_proxy())

async def _test_mavlink_proxy():
    # Create proxy (use a local connection - adjust as needed)
    proxy = MavLinkExternalProxy(endpoint="udp:127.0.0.1:14551")
    
    # Track received heartbeats
    heartbeats_received = []
    
    # Register handler for HEARTBEAT messages
    def heartbeat_handler(msg):
        print(f"Received HEARTBEAT: {msg}")
        heartbeats_received.append(msg)
    
    proxy.register_handler("HEARTBEAT", heartbeat_handler)
    
    # Start the proxy
    await proxy.start()
    
    try:
        # Wait up to 5 seconds for a heartbeat
        print("Waiting for HEARTBEAT messages...")
        timeout = time.time() + 5
        while time.time() < timeout and not heartbeats_received:
            await asyncio.sleep(0.1)
        
        # Verify we got at least one heartbeat
        assert len(heartbeats_received) > 0, "No HEARTBEAT messages received"
        
        # Create and send a GPS_RAW_INT message
        print("Sending GPS_RAW_INT message...")
        mav = mavlink.MAVLink(None)
        gps_msg = mav.gps_raw_int_encode(
            time_usec=int(time.time() * 1e6),
            fix_type=3,  # 3D fix
            lat=int(45.5017 * 1e7),  # Montreal latitude
            lon=int(-73.5673 * 1e7),  # Montreal longitude
            alt=50 * 1000,  # Altitude in mm (50m)
            eph=100,  # GPS HDOP
            epv=100,  # GPS VDOP
            vel=0,  # Ground speed in cm/s
            cog=0,  # Course over ground
            satellites_visible=10,  # Number of satellites
        )
        
        # Send the message
        proxy.send("mav", gps_msg)
        
        # Wait a bit for the message to be sent
        await asyncio.sleep(0.5)
        
        print("Test complete.")
        
    finally:
        # Always stop the proxy
        await proxy.stop()