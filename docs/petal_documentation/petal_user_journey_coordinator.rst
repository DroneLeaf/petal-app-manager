Petal User Journey Coordinator
================================

.. note::
   This documentation is for **petal-user-journey-coordinator v0.1.12**

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

esc_calibration_single
^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/esc_calibration_single``

Initiates and controls ESC calibration for a **single motor**. This is useful when you need to calibrate ESCs individually rather than all at once. The workflow mirrors ``esc_calibration`` but targets only the specified motor.

**Payload:**

.. code-block:: json

   {
     "motor_idx": 1,
     "is_calibration_started": false,
     "safety_timeout_s": 3.0,
     "force_cancel_calibration": false,
     "esc_interface_signal_type": "PWM",
     "throttle": null,
     "safe_stop_calibration": false
   }

**Parameters:**

- ``motor_idx`` (int, required): Motor index (1-based). Cannot be changed while calibration is active.
- ``is_calibration_started`` (bool, required): Whether calibration sequence has begun
- ``safety_timeout_s`` (float, required): Safety timeout in seconds (0-3) before automatic motor shutoff
- ``force_cancel_calibration`` (bool): Force stop the motor immediately (emergency stop)
- ``esc_interface_signal_type`` (str): Signal type - ``"PWM"``, ``"OneShot125"``, ``"OneShot42"``, ``"Multishot"``, ``"DShot150"``, ``"DShot300"``, ``"DShot600"``, ``"DShot1200"``
- ``throttle`` (str|null): Throttle command - ``"maximum"``, ``"minimum"``, or ``null``
- ``safe_stop_calibration`` (bool): Gracefully stop the calibration process

**Example - Full Single-Motor Calibration Sequence:**

.. code-block:: python

   # Step 1: Initialize calibration for motor 1 (drone powered OFF)
   # Sets PWM_AUX_TIM0, PWM_AUX_MAX/MIN/FUNC for the target motor
   {
     "command": "petal-user-journey-coordinator/esc_calibration_single",
     "messageId": "esc-cal-single-001",
     "waitResponse": true,
     "payload": {
       "motor_idx": 1,
       "is_calibration_started": false,
       "safety_timeout_s": 3.0,
       "force_cancel_calibration": false,
       "esc_interface_signal_type": "PWM",
       "throttle": null
     }
   }

   # Step 2: Send maximum throttle to motor 1 (then power ON drone)
   {
     "command": "petal-user-journey-coordinator/esc_calibration_single",
     "messageId": "esc-cal-single-002",
     "waitResponse": true,
     "payload": {
       "motor_idx": 1,
       "is_calibration_started": true,
       "safety_timeout_s": 3.0,
       "throttle": "maximum"
     }
   }

   # Step 3: Send minimum throttle to motor 1 (after ESC beeps)
   {
     "command": "petal-user-journey-coordinator/esc_calibration_single",
     "messageId": "esc-cal-single-003",
     "waitResponse": true,
     "payload": {
       "motor_idx": 1,
       "is_calibration_started": true,
       "safety_timeout_s": 3.0,
       "throttle": "minimum"
     }
   }

   # Step 4: Gracefully stop calibration
   {
     "command": "petal-user-journey-coordinator/esc_calibration_single",
     "messageId": "esc-cal-single-004",
     "waitResponse": true,
     "payload": {
       "motor_idx": 1,
       "is_calibration_started": false,
       "safety_timeout_s": 3.0,
       "safe_stop_calibration": true
     }
   }

   # Alternative Step 4: Emergency stop (force cancel)
   {
     "command": "petal-user-journey-coordinator/esc_calibration_single",
     "messageId": "esc-cal-single-005",
     "waitResponse": true,
     "payload": {
       "motor_idx": 1,
       "is_calibration_started": false,
       "safety_timeout_s": 3.0,
       "force_cancel_calibration": true
     }
   }

**Response:**

.. code-block:: json

   {
     "status": "success",
     "message": "Single-motor ESC calibration state: maximum (motor 1)",
     "calibration_state": "maximum",
     "is_active": true,
     "target_motor": 1
   }

**Important Notes:**

- You **cannot change** ``motor_idx`` while a calibration is active. You will receive an error response asking you to stop the current calibration first via ``safe_stop_calibration: true``.
- The ``throttle`` value is only accepted when ``is_calibration_started`` is ``true`` and the controller is active.
- The motor will automatically stop if ``safety_timeout_s`` elapses without receiving a new command.
- Use ``force_cancel_calibration: true`` for emergency situations; use ``safe_stop_calibration: true`` for graceful shutdown.

.. warning::
   Ensure propellers are removed before running ESC calibration!

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

These commands leverage the efficient bulk parameter operations for setting/getting multiple
PX4 parameters at once over potentially lossy connections. Both commands use a **two-phase
response pattern** (identical to ``reboot_autopilot``):

1. **Immediate Response** (via ``send_command_response``): Acknowledges the command was received and validated
2. **Status Publish** (via ``publish_message``): Reports the final results after all parameters are processed

bulk_set_parameters
^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/bulk_set_parameters``

Sets multiple PX4 parameters in a single operation using the lossy-link optimized bulk setter.
The command validates the payload, immediately acknowledges receipt, then executes the bulk
set and publishes the results to ``command/web``.

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

**Phase 1: Immediate Response (waitResponse)**

Sent immediately via ``send_command_response`` when ``waitResponse: true``:

.. code-block:: json

   {
     "status": "success",
     "message": "Bulk parameter set command initiated",
     "data": {
       "parameter_count": 2,
       "message": "Bulk parameter set in progress, results will be published to command/web"
     }
   }

**Phase 1: Error Responses**

Error responses are sent immediately via ``send_command_response`` when ``waitResponse: true``.

*Operation Blocked:*

.. code-block:: json

   {
     "status": "error",
     "message": "Bulk parameter configuration blocked - Active operation in progress",
     "error_code": "OPERATION_ACTIVE"
   }

*Empty Parameters:*

.. code-block:: json

   {
     "status": "error",
     "message": "No parameters provided for bulk set",
     "error_code": "NO_PARAMETERS_PROVIDED"
   }

*Validation Error:*

.. code-block:: json

   {
     "status": "error",
     "message": "Invalid bulk parameter payload: <validation details>",
     "error_code": "VALIDATION_ERROR"
   }

*Handler Error:*

.. code-block:: json

   {
     "status": "error",
     "message": "Bulk parameter handler error: <error details>",
     "error_code": "HANDLER_ERROR"
   }

**Phase 2: Status Publish (publish_message)**

After all parameters are set (or the operation fails), the petal publishes the result to the
``command/web`` MQTT topic. The front-end must subscribe to this topic and filter messages by
the ``command`` field.

**Status Publish Command Name Pattern:**

.. code-block:: text

   /<petal_name>/bulk-parameter-set

For this petal, the command will be:

.. code-block:: text

   /petal-user-journey-coordinator/bulk-parameter-set

**Front-End Handling:**

The front-end should:

1. Subscribe to the ``command/web`` MQTT topic
2. Filter incoming messages by checking if ``message.command`` equals ``/petal-user-journey-coordinator/bulk-parameter-set``
3. Use the ``messageId`` field to correlate the status with the original request

**Status Publish (Success):**

.. code-block:: json

   {
     "messageId": "bulk-set-001",
     "command": "/petal-user-journey-coordinator/bulk-parameter-set",
     "timestamp": "2026-02-12T12:00:05.000Z",
     "payload": {
       "success": true,
       "status": "success",
       "message": "Bulk parameter set completed - 2 parameters processed",
       "error_code": null,
       "data": {
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
         "timestamp": "2026-02-12T12:00:05.000Z"
       },
       "timestamp": "2026-02-12T12:00:05.000Z"
     }
   }

**Status Publish (Partial Failure):**

.. code-block:: json

   {
     "messageId": "bulk-set-001",
     "command": "/petal-user-journey-coordinator/bulk-parameter-set",
     "timestamp": "2026-02-12T12:00:05.000Z",
     "payload": {
       "success": false,
       "status": "error",
       "message": "Bulk parameter set completed - some parameters failed",
       "error_code": null,
       "data": {
         "success": false,
         "results": {
           "CA_ROTOR_COUNT": {
             "name": "CA_ROTOR_COUNT",
             "value": 4,
             "success": true
           },
           "INVALID_PARAM": {
             "name": "INVALID_PARAM",
             "error": "Parameter value could not be retrieved after set",
             "success": false
           }
         },
         "timestamp": "2026-02-12T12:00:05.000Z"
       },
       "timestamp": "2026-02-12T12:00:05.000Z"
     }
   }

**Status Publish (Error - No Parameters Confirmed):**

.. code-block:: json

   {
     "messageId": "bulk-set-001",
     "command": "/petal-user-journey-coordinator/bulk-parameter-set",
     "timestamp": "2026-02-12T12:00:05.000Z",
     "payload": {
       "success": false,
       "status": "error",
       "message": "No parameters were confirmed after bulk set",
       "error_code": "NO_PARAMETERS_CONFIRMED",
       "data": null,
       "timestamp": "2026-02-12T12:00:05.000Z"
     }
   }

**Status Payload Fields (BulkParameterStatusPayload):**

- ``success`` (bool): ``true`` if all parameters were set successfully, ``false`` otherwise
- ``status`` (str): ``"success"`` or ``"error"``
- ``message`` (str): Human-readable status message
- ``error_code`` (str|null): Error code if the operation failed entirely:

  - ``NO_PARAMETERS_CONFIRMED`` - No parameters were confirmed after the bulk set
  - ``EXECUTION_ERROR`` - Unexpected error during execution

- ``data`` (object|null): ``BulkParameterResponse`` containing per-parameter results, or ``null`` on total failure
- ``timestamp`` (str): ISO 8601 timestamp of when the operation completed

.. note::
   The ``messageId`` in both the immediate response and the status publish matches the
   original request's ``messageId``, allowing the front-end to correlate responses with
   their originating requests.

.. warning::
   The bulk set command will be rejected if any ESC calibration, motor testing, or other
   active operations are in progress. Ensure all operations are complete or cancelled
   before attempting to set parameters.

bulk_get_parameters
^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-user-journey-coordinator/bulk_get_parameters``

Retrieves multiple PX4 parameters in a single operation. The command validates the payload,
immediately acknowledges receipt, then executes the bulk get and publishes the results to
``command/web``.

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

**Phase 1: Immediate Response (waitResponse)**

Sent immediately via ``send_command_response`` when ``waitResponse: true``:

.. code-block:: json

   {
     "status": "success",
     "message": "Bulk parameter get command initiated",
     "data": {
       "parameter_count": 2,
       "message": "Bulk parameter get in progress, results will be published to command/web"
     }
   }

**Phase 1: Error Responses**

Error responses are sent immediately via ``send_command_response`` when ``waitResponse: true``.

*Operation Blocked:*

.. code-block:: json

   {
     "status": "error",
     "message": "Bulk parameter retrieval blocked - Active operation in progress",
     "error_code": "OPERATION_ACTIVE"
   }

*Empty Parameter Names:*

.. code-block:: json

   {
     "status": "error",
     "message": "No parameter names provided for bulk get",
     "error_code": "NO_PARAMETER_NAMES_PROVIDED"
   }

*Validation Error:*

.. code-block:: json

   {
     "status": "error",
     "message": "Invalid bulk parameter get payload: <validation details>",
     "error_code": "VALIDATION_ERROR"
   }

*Handler Error:*

.. code-block:: json

   {
     "status": "error",
     "message": "Bulk parameter get handler error: <error details>",
     "error_code": "HANDLER_ERROR"
   }

**Phase 2: Status Publish (publish_message)**

After all parameters are retrieved (or the operation fails), the petal publishes the result to
the ``command/web`` MQTT topic.

**Status Publish Command Name Pattern:**

.. code-block:: text

   /<petal_name>/bulk-parameter-get

For this petal, the command will be:

.. code-block:: text

   /petal-user-journey-coordinator/bulk-parameter-get

**Front-End Handling:**

The front-end should:

1. Subscribe to the ``command/web`` MQTT topic
2. Filter incoming messages by checking if ``message.command`` equals ``/petal-user-journey-coordinator/bulk-parameter-get``
3. Use the ``messageId`` field to correlate the status with the original request

**Status Publish (Success):**

.. code-block:: json

   {
     "messageId": "bulk-get-001",
     "command": "/petal-user-journey-coordinator/bulk-parameter-get",
     "timestamp": "2026-02-12T12:00:05.000Z",
     "payload": {
       "success": true,
       "status": "success",
       "message": "Bulk parameter get completed - 2 parameters processed",
       "error_code": null,
       "data": {
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
         "timestamp": "2026-02-12T12:00:05.000Z"
       },
       "timestamp": "2026-02-12T12:00:05.000Z"
     }
   }

**Status Publish (Partial Failure):**

.. code-block:: json

   {
     "messageId": "bulk-get-001",
     "command": "/petal-user-journey-coordinator/bulk-parameter-get",
     "timestamp": "2026-02-12T12:00:05.000Z",
     "payload": {
       "success": false,
       "status": "error",
       "message": "Bulk parameter get completed - some parameters failed",
       "error_code": null,
       "data": {
         "success": false,
         "results": {
           "CA_ROTOR_COUNT": {
             "name": "CA_ROTOR_COUNT",
             "value": 4,
             "success": true
           },
           "INVALID_PARAM": {
             "name": "INVALID_PARAM",
             "error": "Parameter value could not be retrieved",
             "success": false
           }
         },
         "timestamp": "2026-02-12T12:00:05.000Z"
       },
       "timestamp": "2026-02-12T12:00:05.000Z"
     }
   }

**Status Publish (Error - No Parameters Confirmed):**

.. code-block:: json

   {
     "messageId": "bulk-get-001",
     "command": "/petal-user-journey-coordinator/bulk-parameter-get",
     "timestamp": "2026-02-12T12:00:05.000Z",
     "payload": {
       "success": false,
       "status": "error",
       "message": "No parameters were confirmed after bulk get",
       "error_code": "NO_PARAMETERS_CONFIRMED",
       "data": null,
       "timestamp": "2026-02-12T12:00:05.000Z"
     }
   }

**Status Payload Fields (BulkParameterStatusPayload):**

- ``success`` (bool): ``true`` if all parameters were retrieved successfully, ``false`` otherwise
- ``status`` (str): ``"success"`` or ``"error"``
- ``message`` (str): Human-readable status message
- ``error_code`` (str|null): Error code if the operation failed entirely:

  - ``NO_PARAMETERS_CONFIRMED`` - No parameters were confirmed after the bulk get
  - ``EXECUTION_ERROR`` - Unexpected error during execution

- ``data`` (object|null): ``BulkParameterResponse`` containing per-parameter results, or ``null`` on total failure
- ``timestamp`` (str): ISO 8601 timestamp of when the operation completed

.. note::
   The ``messageId`` in both the immediate response and the status publish matches the
   original request's ``messageId``, allowing the front-end to correlate responses with
   their originating requests.

.. warning::
   The bulk get command will be rejected if any ESC calibration, motor testing, or other
   active operations are in progress. Ensure all operations are complete or cancelled
   before attempting to retrieve parameters.

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

**Command:** ``petal-user-journey-coordinator/reboot_autopilot``

Reboots the PX4 flight controller with full heartbeat confirmation. The command sends
``MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN``, then waits for the autopilot heartbeat to **drop**
(confirming the reboot started) and **return** (confirming the autopilot is alive again).
This uses a two-phase response pattern:

1. **Immediate Response** (via ``send_command_response``): Acknowledges the command was received
2. **Status Publish** (via ``publish_message``): Reports the **confirmed** reboot result after heartbeat returns

**Understanding ``waitResponse``:**

When ``waitResponse: true`` is set in the request, the petal will call ``send_command_response`` to deliver an immediate acknowledgement back to the client. This response is delivered via the MQTT proxy's request-response mechanism and confirms:

- The command was received and validated
- No blocking operations are in progress  
- The reboot process has been initiated

The client does **not** wait for the actual reboot to complete—that would block for up to
~35 seconds (ACK timeout + heartbeat drop window + heartbeat return window).

**Payload:** None required (empty object ``{}``)

**Phase 1: Immediate Response (waitResponse)**

Sent immediately via ``send_command_response`` when ``waitResponse: true``:

.. code-block:: json

   {
     "status": "success",
     "message": "PX4 reboot command initiated",
     "data": {
       "reboot_initiated": true,
       "message": "Reboot in progress, confirmed status will be published to command/web"
     }
   }

**Phase 1: Error Responses**

Error responses are sent immediately via ``send_command_response`` when ``waitResponse: true``.

*Operation Blocked:*

.. code-block:: json

   {
     "status": "error",
     "message": "PX4 reboot blocked - Active operation in progress",
     "error_code": "OPERATION_ACTIVE"
   }

*Validation Error:*

.. code-block:: json

   {
     "status": "error",
     "message": "Invalid PX4 reboot message: <validation details>",
     "error_code": "VALIDATION_ERROR"
   }

*Handler Error:*

.. code-block:: json

   {
     "status": "error",
     "message": "PX4 reboot message handler error: <error details>",
     "error_code": "HANDLER_ERROR"
   }

**Phase 2: Status Publish (publish_message)**

After the reboot completes (or fails), the petal publishes the result to the ``command/web`` MQTT topic. The front-end must subscribe to this topic and filter messages by the ``command`` field.

**Status Publish Command Name Pattern:**

.. code-block:: text

   /<petal_name>/reboot_px4_status

For this petal, the command will be:

.. code-block:: text

   /petal-user-journey-coordinator/reboot_px4_status

**Front-End Handling:**

The front-end should:

1. Subscribe to the ``command/web`` MQTT topic
2. Filter incoming messages by checking if ``message.command`` equals ``/petal-user-journey-coordinator/reboot_px4_status``
3. Use the ``messageId`` field to correlate the status with the original request

**Status Publish (Success):**

.. code-block:: json

   {
     "messageId": "reboot-001",
     "command": "/petal-user-journey-coordinator/reboot_px4_status",
     "timestamp": "2026-01-07T12:00:05.000Z",
     "payload": {
       "reboot_initiated": true,
       "reboot_success": true,
       "status": "success",
       "message": "Reboot confirmed: COMMAND_ACK accepted and heartbeat drop + return observed.",
       "error_code": null,
       "timestamp": "2026-01-07T12:00:05.000Z"
     }
   }

**Status Publish (Failed):**

.. code-block:: json

   {
     "messageId": "reboot-001",
     "command": "/petal-user-journey-coordinator/reboot_px4_status",
     "timestamp": "2026-01-07T12:00:05.000Z",
     "payload": {
       "reboot_initiated": true,
       "reboot_success": false,
       "status": "failed",
       "message": "Heartbeat drop observed but heartbeat did not return within 30.0s. Autopilot may still be rebooting.",
       "error_code": "FAIL_REBOOT_NOT_CONFIRMED_HB_NO_RETURN",
       "timestamp": "2026-01-07T12:00:05.000Z"
     }
   }

**Status Payload Fields:**

- ``reboot_initiated`` (bool): Always ``true`` if status is published (reboot was attempted)
- ``reboot_success`` (bool): ``true`` if reboot succeeded, ``false`` if it failed
- ``status`` (str): ``"success"`` or ``"failed"``
- ``message`` (str): Human-readable status message from the MAVLink response
- ``error_code`` (str|null): Error code if failed, from ``RebootStatusCode``:

  - ``FAIL_ACK_DENIED`` - Autopilot rejected the command
  - ``FAIL_ACK_TEMPORARILY_REJECTED`` - Temporarily rejected
  - ``FAIL_NO_HEARTBEAT_TRACKING`` - Heartbeat tracking unavailable
  - ``FAIL_REBOOT_NOT_CONFIRMED_NO_HB_DROP`` - Heartbeat did not drop
  - ``FAIL_REBOOT_NOT_CONFIRMED_HB_NO_RETURN`` - Heartbeat dropped but did not return
  - ``EXECUTION_ERROR`` - Unexpected error during reboot

- ``timestamp`` (str): ISO 8601 timestamp of when the reboot completed

.. warning::
   The reboot command will be rejected if any ESC calibration, motor testing, or other 
   active operations are in progress. Ensure all operations are complete or cancelled 
   before attempting to reboot.

.. note::
   The ``messageId`` in both the immediate response and the status publish matches the 
   original request's ``messageId``, allowing the front-end to correlate responses with 
   their originating requests.

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

MQTT Topics Reference
---------------------

This section provides a comprehensive reference of all MQTT topics used by the petal.

Commands (Received on ``command/edge``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Commands are received on the ``command/edge`` topic with the following format:
``petal-user-journey-coordinator/<command_name>``

**ESC Calibration:**

- ``petal-user-journey-coordinator/esc_calibration`` - ESC calibration control (all motors)
- ``petal-user-journey-coordinator/esc_calibration_single`` - ESC calibration control (single motor)
- ``petal-user-journey-coordinator/esc_force_run_all`` - Force run all motors
- ``petal-user-journey-coordinator/esc_force_run_single`` - Force run single motor
- ``petal-user-journey-coordinator/esc_update_calibration_limits`` - Update ESC calibration limits

**Geometry & Sensor Configuration:**

- ``petal-user-journey-coordinator/geometry`` - Set drone geometry
- ``petal-user-journey-coordinator/gps_module`` - Configure GPS module
- ``petal-user-journey-coordinator/dist_module`` - Configure distance sensor module
- ``petal-user-journey-coordinator/oflow_module`` - Configure optical flow module
- ``petal-user-journey-coordinator/gps_spatial_offset`` - Set GPS spatial offset
- ``petal-user-journey-coordinator/distance_spatial_offset`` - Set distance sensor offset
- ``petal-user-journey-coordinator/optical_flow_spatial_offset`` - Set optical flow offset

**Parameter Management:**

- ``petal-user-journey-coordinator/bulk_set_parameters`` - Bulk set PX4 parameters
- ``petal-user-journey-coordinator/bulk_get_parameters`` - Bulk get PX4 parameters

**Telemetry Stream Subscriptions:**

- ``petal-user-journey-coordinator/subscribe_rc_value_stream`` - Subscribe to RC stream
- ``petal-user-journey-coordinator/unsubscribe_rc_value_stream`` - Unsubscribe from RC stream
- ``petal-user-journey-coordinator/subscribe_pose_value_stream`` - Subscribe to pose stream
- ``petal-user-journey-coordinator/unsubscribe_pose_value_stream`` - Unsubscribe from pose stream
- ``petal-user-journey-coordinator/subscribe_ks_status_stream`` - Subscribe to kill switch status
- ``petal-user-journey-coordinator/unsubscribe_ks_status_stream`` - Unsubscribe from kill switch status
- ``petal-user-journey-coordinator/subscribe_mfs_a_status_stream`` - Subscribe to MFS A status
- ``petal-user-journey-coordinator/unsubscribe_mfs_a_status_stream`` - Unsubscribe from MFS A status
- ``petal-user-journey-coordinator/subscribe_mfs_b_status_stream`` - Subscribe to MFS B status
- ``petal-user-journey-coordinator/unsubscribe_mfs_b_status_stream`` - Unsubscribe from MFS B status
- ``petal-user-journey-coordinator/unsubscribeall`` - Unsubscribe from all streams

**Verification Commands:**

- ``petal-user-journey-coordinator/verify_pos_yaw_directions`` - Start position/yaw verification
- ``petal-user-journey-coordinator/verify_pos_yaw_directions_complete`` - Complete position/yaw verification

**Network Configuration:**

- ``petal-user-journey-coordinator/connect_to_wifi_and_verify_optitrack`` - Connect WiFi and verify OptiTrack
- ``petal-user-journey-coordinator/set_static_ip_address`` - Set static IP address

**System Commands:**

- ``petal-user-journey-coordinator/reboot_autopilot`` - Reboot the PX4 autopilot

Published Topics (Sent to ``command/web``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The petal publishes status updates and async results to ``command/web`` with the following topics:

**System Status:**

- ``/petal-user-journey-coordinator/reboot_px4_status`` - Reboot operation status (success/failure)

**Bulk Parameter Results:**

- ``/petal-user-journey-coordinator/bulk-parameter-set`` - Bulk parameter set results (success/partial failure/error)
- ``/petal-user-journey-coordinator/bulk-parameter-get`` - Bulk parameter get results (success/partial failure/error)

**Telemetry Streams:**

- ``/petal-user-journey-coordinator/publish_rc_value_stream`` - RC value stream data
- ``/petal-user-journey-coordinator/publish_pose_value_stream`` - Pose value stream data
- ``/petal-user-journey-coordinator/publish_ks_status_stream`` - Kill switch status stream data
- ``/petal-user-journey-coordinator/publish_mfs_a_status_stream`` - MFS A status stream data
- ``/petal-user-journey-coordinator/publish_mfs_b_status_stream`` - MFS B status stream data

**Verification Results:**

- ``/petal-user-journey-coordinator/verify_pos_yaw_directions_results`` - Position/yaw verification results

**Acknowledgments:**

- ``petal-user-journey-coordinator/acknowledge`` - Generic command acknowledgment
- ``petal-user-journey-coordinator/set_static_ip_address_ack`` - Static IP address set acknowledgment

See Also
--------

- :doc:`../development_contribution/using_proxies` - Proxy usage documentation
- :doc:`../changelog` - Version history and changes
