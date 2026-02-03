Petal User Journey Coordinator
================================

.. note::
   This documentation is for **petal-user-journey-coordinator v0.1.8**

The **petal-user-journey-coordinator** is a critical petal that provides MQTT-based command handling for drone configuration, calibration, real-time telemetry streaming, and trajectory verification. It serves as the primary interface between web/mobile applications and the drone's flight controller.

Overview
--------

This petal communicates via MQTT messages on the ``command/edge`` topic. All commands follow a standardized message format:

.. code-block:: json

   {
     "command": "petal-user-journey-coordinator/<command_name>",
     "messageId": "unique-message-id",
     "waitResponse": true,
     "payload": {
       // Command-specific payload
     }
   }

Required Proxies
----------------

- ``mqtt`` - For MQTT communication with web clients
- ``ext_mavlink`` - For MAVLink communication with the flight controller

Command Categories
------------------

.. contents:: 
   :local:
   :depth: 2

ESC Calibration Commands
------------------------

These commands handle Electronic Speed Controller (ESC) calibration and motor testing.

esc_calibration
^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/esc_calibration``

Initiates and controls the ESC calibration process. ESC calibration sets the throttle range that ESCs recognize.

**Payload:**

.. code-block:: json

   {
     "is_calibration_started": false,
     "safety_timeout_s": 3.0,
     "force_cancel_calibration": false,
     "esc_interface_signal_type": "PWM",
     "ca_rotor_count": 4,
     "throttle": null
   }

**Parameters:**

- ``is_calibration_started`` (bool): Whether calibration sequence has begun
- ``safety_timeout_s`` (float): Safety timeout in seconds before automatic motor shutoff
- ``force_cancel_calibration`` (bool): Force stop all motors immediately
- ``esc_interface_signal_type`` (str): Signal type - ``"PWM"`` or ``"DShot"``
- ``ca_rotor_count`` (int): Number of rotors (typically 4, 6, or 8)
- ``throttle`` (str|null): Throttle command - ``"maximum"``, ``"minimum"``, or ``null``

**Example - Full Calibration Sequence:**

.. code-block:: python

   # Step 1: Configure calibration (drone powered OFF)
   {
     "command": "petal-user-journey-coordinator/esc_calibration",
     "messageId": "esc-cal-001",
     "waitResponse": true,
     "payload": {
       "is_calibration_started": false,
       "safety_timeout_s": 3.0,
       "force_cancel_calibration": false,
       "esc_interface_signal_type": "PWM",
       "ca_rotor_count": 4,
       "throttle": null
     }
   }

   # Step 2: Send maximum throttle (then power ON drone)
   {
     "command": "petal-user-journey-coordinator/esc_calibration",
     "messageId": "esc-cal-002",
     "waitResponse": true,
     "payload": {
       "is_calibration_started": true,
       "throttle": "maximum"
     }
   }

   # Step 3: Send minimum throttle (after ESC beeps)
   {
     "command": "petal-user-journey-coordinator/esc_calibration",
     "messageId": "esc-cal-003",
     "waitResponse": true,
     "payload": {
       "is_calibration_started": true,
       "throttle": "minimum"
     }
   }

   # Step 4: Stop motors
   {
     "command": "petal-user-journey-coordinator/esc_calibration",
     "messageId": "esc-cal-004",
     "waitResponse": true,
     "payload": {
       "force_cancel_calibration": true
     }
   }

esc_force_run_all
^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/esc_force_run_all``

Forces all motors to run simultaneously at a specified command level for testing purposes.

**Payload:**

.. code-block:: json

   {
     "motors_common_command": 1000,
     "safety_timeout_s": 2.0,
     "force_cancel": false
   }

**Parameters:**

- ``motors_common_command`` (float): Common command value for all motors [1000..1200]
- ``safety_timeout_s`` (float): Safety timeout in seconds (0-3)
- ``force_cancel`` (bool): Force cancel operation

.. warning::
   Ensure propellers are removed before running motor tests!

esc_force_run_single
^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/esc_force_run_single``

Forces a single motor to run for individual motor testing.

**Payload:**

.. code-block:: json

   {
     "motor_idx": 1,
     "motor_command": 1000,
     "safety_timeout_s": 2.5,
     "force_cancel": false
   }

**Parameters:**

- ``motor_idx`` (int): Motor index (1-based)
- ``motor_command`` (float): Motor command value [1000..2000]
- ``safety_timeout_s`` (float): Safety timeout in seconds (0-3)
- ``force_cancel`` (bool): Force cancel operation

Parameter Configuration Commands
--------------------------------

These commands configure drone parameters on the flight controller.

geometry
^^^^^^^^

**Command:** ``petal-user-journey-coordinator/geometry``

Configures the drone geometry (rotor count).

**Payload:**

.. code-block:: json

   {
     "rotor_count": 4
   }

**Parameters:**

- ``rotor_count`` (int): Number of rotors (4, 6, or 8)

gps_module
^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/gps_module``

Configures the GPS module type.

**Payload:**

.. code-block:: json

   {
     "gps_module": "u-blox NEO-M8N"
   }

**Parameters:**

- ``gps_module`` (str): GPS module identifier

dist_module
^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/dist_module``

Configures the distance sensor module.

**Payload:**

.. code-block:: json

   {
     "dist_module": "LiDAR Lite v3"
   }

**Supported Modules:**

- ``"LiDAR Lite v3"``
- ``"TFMini"``
- ``"Benewake TF02"``
- Other compatible distance sensors

oflow_module
^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/oflow_module``

Configures the optical flow sensor module.

**Payload:**

.. code-block:: json

   {
     "oflow_module": "ARK Flow"
   }

**Supported Modules:**

- ``"ARK Flow"``
- ``"PX4Flow"``
- Other compatible optical flow sensors

gps_spatial_offset
^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/gps_spatial_offset``

Sets the GPS antenna position offset relative to the drone's center of mass.

**Payload:**

.. code-block:: json

   {
     "gps_module_spatial_offset_x_m": 0.1,
     "gps_module_spatial_offset_y_m": 0.0,
     "gps_module_spatial_offset_z_m": -0.05
   }

**Parameters:**

- ``gps_module_spatial_offset_x_m`` (float): GPS X offset in meters
- ``gps_module_spatial_offset_y_m`` (float): GPS Y offset in meters
- ``gps_module_spatial_offset_z_m`` (float): GPS Z offset in meters

distance_spatial_offset
^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/distance_spatial_offset``

Sets the distance sensor position offset.

**Payload:**

.. code-block:: json

   {
     "dist_module_spatial_offset_x_m": 0.05,
     "dist_module_spatial_offset_y_m": 0.0,
     "dist_module_spatial_offset_z_m": -0.1
   }

**Parameters:**

- ``dist_module_spatial_offset_x_m`` (float): Distance sensor X offset in meters
- ``dist_module_spatial_offset_y_m`` (float): Distance sensor Y offset in meters
- ``dist_module_spatial_offset_z_m`` (float): Distance sensor Z offset in meters

optical_flow_spatial_offset
^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/optical_flow_spatial_offset``

Sets the optical flow sensor position offset.

**Payload:**

.. code-block:: json

   {
     "oflow_module_spatial_offset_x_m": 0.0,
     "oflow_module_spatial_offset_y_m": 0.0,
     "oflow_module_spatial_offset_z_m": -0.02
   }

**Parameters:**

- ``oflow_module_spatial_offset_x_m`` (float): Optical flow X offset in meters
- ``oflow_module_spatial_offset_y_m`` (float): Optical flow Y offset in meters
- ``oflow_module_spatial_offset_z_m`` (float): Optical flow Z offset in meters

esc_update_calibration_limits
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/esc_update_calibration_limits``

Updates ESC PWM calibration limits.

**Payload:**

.. code-block:: json

   {
     "motors_common_max_pwm": 2000,
     "motors_common_min_pwm": 1000
   }

**Parameters:**

- ``motors_common_max_pwm`` (int): Common maximum PWM value for all motors (1000-2000)
- ``motors_common_min_pwm`` (int): Common minimum PWM value for all motors (1000-2000)

Bulk Parameter Operations
-------------------------

These commands leverage the efficient bulk parameter operations for setting/getting multiple PX4 parameters at once over potentially lossy connections.

bulk_set_parameters
^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/bulk_set_parameters``

Sets multiple PX4 parameters in a single operation using the lossy-link optimized bulk setter.

**Payload:**

.. code-block:: json

   {
     "parameters": [
       {
         "parameter_name": "CA_ROTOR_COUNT",
         "parameter_value": 4,
         "parameter_type": "UINT8"
       },
       {
         "parameter_name": "VTO_LOITER_ALT",
         "parameter_value": 80.0,
         "parameter_type": "REAL32"
       }
     ]
   }

**Parameters:**

- ``parameters`` (list): List of parameter objects, each containing:
  - ``parameter_name`` (str): Name of the PX4 parameter
  - ``parameter_value`` (str|int|float): Value to set
  - ``parameter_type`` (str, optional): Parameter type - ``"UINT8"``, ``"INT8"``, ``"UINT16"``, ``"INT16"``, ``"UINT32"``, ``"INT32"``, ``"UINT64"``, ``"INT64"``, ``"REAL32"``, ``"REAL64"``

**Response:**

.. code-block:: json

   {
     "success": true,
     "results": {
       "CA_ROTOR_COUNT": {
         "name": "CA_ROTOR_COUNT",
         "value": 4,
         "raw": 4.0,
         "type": 6,
         "count": 1053,
         "index": 65535,
         "error": null,
         "success": true
       },
       "VTO_LOITER_ALT": {
         "name": "VTO_LOITER_ALT",
         "value": 80.0,
         "raw": 80.0,
         "type": 9,
         "count": 1053,
         "index": 1047,
         "error": null,
         "success": true
       }
     },
     "timestamp": "2023-01-01T00:00:00Z"
   }

bulk_get_parameters
^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/bulk_get_parameters``

Retrieves multiple PX4 parameters in a single operation.

**Payload:**

.. code-block:: json

   {
     "parameter_names": [
       "CA_ROTOR_COUNT",
       "VTO_LOITER_ALT"
     ]
   }

**Parameters:**

- ``parameter_names`` (list): List of parameter name strings to retrieve

**Response:**

.. code-block:: json

   {
     "success": true,
     "results": {
       "CA_ROTOR_COUNT": {
         "name": "CA_ROTOR_COUNT",
         "value": 4,
         "raw": 4.0,
         "type": 6,
         "count": 1053,
         "index": 65535,
         "error": null,
         "success": true
       },
       "VTO_LOITER_ALT": {
         "name": "VTO_LOITER_ALT",
         "value": 80.0,
         "raw": 80.0,
         "type": 9,
         "count": 1053,
         "index": 1047,
         "error": null,
         "success": true
       }
     },
     "timestamp": "2023-01-01T00:00:00Z"
   }

Real-Time Telemetry Streams
---------------------------

These commands subscribe/unsubscribe to real-time data streams from the flight controller.

subscribe_rc_value_stream
^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/subscribe_rc_value_stream``

Subscribes to RC (Remote Control) channel values for monitoring transmitter inputs.

**Payload:**

.. code-block:: json

   {
     "subscribed_stream_id": "px4_rc_raw",
     "data_rate_hz": 50.0
   }

**Parameters:**

- ``subscribed_stream_id`` (str): Unique identifier for this subscription
- ``data_rate_hz`` (float): Data publishing rate in Hz (1-100)

**Stream Data Format:**

.. code-block:: json

   {
     "stream_id": "px4_rc_raw",
     "timestamp": "2026-01-07T12:00:00.000Z",
     "channels": [1500, 1500, 1000, 1500, 1000, 1500, 1500, 1500],
     "rssi": 100,
     "channel_count": 8
   }

unsubscribe_rc_value_stream
^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/unsubscribe_rc_value_stream``

Unsubscribes from RC channel stream.

**Payload:**

.. code-block:: json

   {
     "unsubscribed_stream_id": "px4_rc_raw"
   }

subscribe_pose_value_stream
^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/subscribe_pose_value_stream``

Subscribes to real-time position and orientation data.

**Payload:**

.. code-block:: json

   {
     "subscribed_stream_id": "real_time_pose",
     "data_rate_hz": 20.0
   }

**Stream Data Format:**

.. code-block:: json

   {
     "stream_id": "real_time_pose",
     "timestamp": "2026-01-07T12:00:00.000Z",
     "position": {"x": 0.0, "y": 0.0, "z": -1.5},
     "velocity": {"vx": 0.0, "vy": 0.0, "vz": 0.0},
     "attitude": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0},
     "heading": 90.0
   }

unsubscribe_pose_value_stream
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/unsubscribe_pose_value_stream``

Unsubscribes from pose stream.

subscribe_ks_status_stream
^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/subscribe_ks_status_stream``

Subscribes to kill switch status monitoring.

**Payload:**

.. code-block:: json

   {
     "subscribed_stream_id": "px4_ks_status",
     "data_rate_hz": 5.0
   }

**Stream Data Format:**

.. code-block:: json

   {
     "stream_id": "px4_ks_status",
     "timestamp": "2026-01-07T12:00:00.000Z",
     "kill_switch_engaged": false,
     "channel_value": 1000
   }

unsubscribe_ks_status_stream
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/unsubscribe_ks_status_stream``

Unsubscribes from kill switch stream.

subscribe_mfs_a_status_stream / subscribe_mfs_b_status_stream
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Commands:**

- ``petal-user-journey-coordinator/subscribe_mfs_a_status_stream``
- ``petal-user-journey-coordinator/subscribe_mfs_b_status_stream``

Subscribes to multi-functional switch A or B status streams.

**Payload:**

.. code-block:: json

   {
     "subscribed_stream_id": "px4_mfs_a_raw",
     "data_rate_hz": 10.0
   }

unsubscribeall
^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/unsubscribeall``

Unsubscribes from all active telemetry streams.

**Payload:** None required

**Response:**

.. code-block:: json

   {
     "status": "success",
     "message": "Unsubscribed from 3 streams",
     "unsubscribed_streams": [
       {"stream_name": "rc_value_stream", "stream_id": "px4_rc_raw"},
       {"stream_name": "pose_value_stream", "stream_id": "real_time_pose"},
       {"stream_name": "ks_status_stream", "stream_id": "px4_ks_status"}
     ]
   }

Trajectory Verification Commands
--------------------------------

These commands support automated trajectory verification for drone movement testing.

verify_pos_yaw_directions
^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/verify_pos_yaw_directions``

Starts a trajectory verification sequence where the drone follows a predefined rectangular path to verify position and yaw accuracy.

**Payload:**

.. code-block:: json

   {
     "rectangle_width": 3.0,
     "rectangle_height": 3.0,
     "points_per_edge": 10
   }

**Parameters:**

- ``rectangle_width`` (float): Width of test rectangle in meters
- ``rectangle_height`` (float): Height of test rectangle in meters
- ``points_per_edge`` (int): Number of waypoints per edge

verify_pos_yaw_directions_complete
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/verify_pos_yaw_directions_complete``

Completes the trajectory verification and retrieves results.

**Response:**

.. code-block:: json

   {
     "status": "success",
     "verification_result": {
       "total_points": 40,
       "matched_points": 38,
       "accuracy_percent": 95.0,
       "max_position_error_m": 0.15,
       "max_yaw_error_deg": 5.2,
       "trajectory_data": []
     }
   }

WiFi & OptiTrack Commands
-------------------------

These commands manage WiFi connectivity and OptiTrack motion capture system integration.

connect_to_wifi_and_verify_optitrack
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/connect_to_wifi_and_verify_optitrack``

Connects to a WiFi network and verifies OptiTrack motion capture connectivity.

**Payload:**

.. code-block:: json

   {
     "positioning_system_network_wifi_ssid": "OptiTrack_Network",
     "positioning_system_network_wifi_pass": "password123",
     "positioning_system_network_wifi_subnet": "192.168.1.0/24",
     "positioning_system_network_server_ip_address": "192.168.1.100",
     "positioning_system_network_server_multicast_address": "239.255.42.99",
     "positioning_system_network_server_data_port": "1511"
   }

**Parameters:**

- ``positioning_system_network_wifi_ssid`` (str): WiFi SSID to connect to
- ``positioning_system_network_wifi_pass`` (str): WiFi password
- ``positioning_system_network_wifi_subnet`` (str): Expected subnet (e.g., '192.168.1.0/24')
- ``positioning_system_network_server_ip_address`` (str): OptiTrack server IP address to ping
- ``positioning_system_network_server_multicast_address`` (str): Multicast address for OptiTrack
- ``positioning_system_network_server_data_port`` (str): Data port for OptiTrack communication

**Response:**

.. code-block:: json

   {
     "was_successful": true,
     "status_message": "Successfully connected to WiFi and verified OptiTrack server connectivity",
     "assigned_ip_address": "192.168.1.45"
   }

set_static_ip_address
^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/set_static_ip_address``

Sets a static IP address within the OptiTrack network.

**Payload:**

.. code-block:: json

   {
     "positioning_system_network_wifi_subnet": "255.255.255.0",
     "positioning_system_network_server_ip_address": "10.0.0.27"
   }

**Parameters:**

- ``positioning_system_network_wifi_subnet`` (str): Subnet mask (e.g., '255.255.255.0' or '10.0.0.0/24')
- ``positioning_system_network_server_ip_address`` (str): OptiTrack server IP address for gateway calculation

**Response:**

.. code-block:: json

   {
     "assigned_static_ip": "10.0.0.25",
     "was_successful": true
   }

System Commands
---------------

These commands provide system-level operations for the flight controller.

reboot_px4
^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/reboot_px4``

Reboots the PX4 flight controller. This command is blocked if any active operation (ESC calibration, motor testing, etc.) is in progress.

**Payload:** None required (empty object ``{}``)

**Response (Success):**

.. code-block:: json

   {
     "status": "success",
     "message": "PX4 reboot command successful",
     "data": {
       "success": true,
       "message": "Reboot command acknowledged"
     }
   }

**Response (Error - Operation Active):**

.. code-block:: json

   {
     "status": "error",
     "message": "PX4 reboot blocked - Active operation in progress",
     "error_code": "OPERATION_ACTIVE"
   }

**Response (Error - Reboot Failed):**

.. code-block:: json

   {
     "status": "error",
     "message": "PX4 reboot command failed or timed out",
     "error_code": "REBOOT_FAILED",
     "data": {
       "success": false,
       "message": "Timeout waiting for reboot acknowledgment"
     }
   }

**Example:**

.. code-block:: python

   # Reboot the PX4 flight controller
   {
     "command": "petal-user-journey-coordinator/reboot_px4",
     "messageId": "reboot-001",
     "waitResponse": true,
     "payload": {}
   }

.. warning::
   The reboot command will be rejected if any ESC calibration, motor testing, or other 
   active operations are in progress. Ensure all operations are complete or cancelled 
   before attempting to reboot.

Complete Usage Example
----------------------

Here's a complete example of configuring a drone using multiple commands:

.. code-block:: python

   import json
   import paho.mqtt.client as mqtt

   # Connect to MQTT broker
   client = mqtt.Client()
   client.connect("localhost", 1883)

   def send_command(command, payload, message_id):
       msg = {
           "command": command,
           "messageId": message_id,
           "waitResponse": True,
           "payload": payload
       }
       client.publish("command/edge", json.dumps(msg))

   # 1. Configure geometry
   send_command(
       "petal-user-journey-coordinator/geometry",
       {"rotor_count": 4},
       "config-001"
   )

   # 2. Set GPS offset
   send_command(
       "petal-user-journey-coordinator/gps_spatial_offset",
       {
           "gps_module_spatial_offset_x_m": 0.05,
           "gps_module_spatial_offset_y_m": 0.0,
           "gps_module_spatial_offset_z_m": -0.02
       },
       "config-002"
   )

   # 3. Bulk set flight parameters
   send_command(
       "petal-user-journey-coordinator/bulk_set_parameters",
       {
           "parameters": [
               {"parameter_name": "NAV_ACC_RAD", "parameter_value": 2.0, "parameter_type": "REAL32"},
               {"parameter_name": "MPC_XY_VEL_MAX", "parameter_value": 12.0, "parameter_type": "REAL32"},
               {"parameter_name": "MPC_Z_VEL_MAX_UP", "parameter_value": 3.0, "parameter_type": "REAL32"}
           ]
       },
       "config-003"
   )

   # 4. Subscribe to pose stream for verification
   send_command(
       "petal-user-journey-coordinator/subscribe_pose_value_stream",
       {"subscribed_stream_id": "verification_pose", "data_rate_hz": 20.0},
       "stream-001"
   )

   # 5. Cleanup - unsubscribe all
   send_command(
       "petal-user-journey-coordinator/unsubscribeall",
       {},
       "cleanup-001"
   )

Error Handling
--------------

All commands return error responses in a consistent format:

.. code-block:: json

   {
     "status": "error",
     "message": "Detailed error description",
     "error_code": "ERROR_CODE",
     "timestamp": "2026-01-07T12:00:00.000Z"
   }

**Common Error Codes:**

- ``UNKNOWN_COMMAND`` - Command not recognized
- ``VALIDATION_ERROR`` - Invalid payload format
- ``TIMEOUT_ERROR`` - Operation timed out
- ``MAVLINK_ERROR`` - MAVLink communication failed
- ``NOT_INITIALIZED`` - Petal not fully initialized

See Also
--------

- :doc:`../development_contribution/using_proxies` - Proxy usage documentation
- :doc:`../changelog` - Version history and changes
