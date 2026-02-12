Changelog
=========

Version 0.2.0 (2026-02-12)
---------------------------

**``@mqtt_action`` Decorator & MQTT Command Handler Refactor:**

- Introduced the ``@mqtt_action`` decorator in ``petal_app_manager.plugins.decorators`` for
  declarative MQTT command handler registration:

  - ``command`` parameter: specifies the command suffix (framework auto-prefixes the petal name)
  - ``cpu_heavy`` parameter (default ``False``): when ``True``, offloads handler execution to a
    thread-pool executor to prevent event-loop starvation from CPU-bound work (e.g. NumPy, image
    processing, large serialization)

- Added base-class infrastructure in ``Petal`` (``plugins/base.py``):

  - ``_collect_mqtt_actions()``: scans all instance methods/attributes for ``__mqtt_action__``
    metadata and builds the dispatch table
  - ``_mqtt_master_command_handler()``: single registered MQTT handler that dispatches incoming
    commands to the correct ``@mqtt_action`` handler, with automatic error responses for unknown
    commands and organization-ID guard logic
  - ``_setup_mqtt_actions()``: called at startup to wire everything up and register the master
    handler with the MQTT proxy
  - ``has_mqtt_actions()``: quick check for whether a petal has any decorated handlers

- Removed legacy boilerplate from all refactored petals:

  - ``_setup_command_handlers()`` methods (manual dict of command → handler)
  - ``_master_command_handler()`` methods (manual if/elif dispatch)
  - Manual ``register_handler()`` calls in ``_setup_mqtt_topics()``

**Documentation Updates:**

- Added :ref:`mqtt-action-decorator` section to *Adding a New Petal* guide covering:

  - Basic usage, handler signature, ``cpu_heavy`` parameter
  - Under-the-hood dispatch mechanism
  - Dynamic/factory handler pattern
  - Migration guide from the legacy manual dispatch pattern

- Replaced MQTTProxy placeholder in *Using Proxies* guide with full documentation:

  - ``@mqtt_action``-based command handling (recommended)
  - ``publish_message()`` and ``send_command_response()`` public API
  - Method reference table
  - ``cpu_heavy`` flag explanation
  - Status broadcasting example

**Dependency Updates:**

- Updated ``petal-flight-log`` from ``v0.2.5`` to ``v0.2.6``:

  - **Refactor**: All 10 MQTT command handlers now registered via ``@mqtt_action`` decorator,
    eliminating the manual command handler registry and master dispatch method:
    ``fetch_flight_records``, ``subscribe_fetch_flight_records``,
    ``unsubscribe_fetch_flight_records``, ``cancel_fetch_flight_records``,
    ``fetch_existing_flight_records``, ``start_sync_flight_record``,
    ``subscribe_sync_job_value_stream``, ``unsubscribe_sync_job_value_stream``,
    ``cancel_sync_job``, ``delete_flight_record``
  - **Improvement**: Redis command acknowledgment and message handling methods are now fully
    asynchronous (``async def`` / ``await``), ensuring non-blocking behavior
  - **Improvement**: Fire-and-forget scheduling of long-running Redis command handlers now uses
    ``asyncio.create_task`` instead of ``asyncio.run_coroutine_threadsafe``
  - **Fix**: ``sync_px4_time`` serial handler converted to ``async def``, aligning with the
    rest of the async codebase

- Updated ``petal-user-journey-coordinator`` from ``v0.1.10`` to ``v0.1.11``:

  - **Refactor**: Replaced manual ``_command_handlers`` registry and ``_master_command_handler``
    with automatic handler discovery and dispatch via ``@mqtt_action`` decorator and the base
    class ``Petal._mqtt_master_command_handler``
  - **Refactor**: All static handlers decorated with ``@mqtt_action``; dynamically created
    parameter and pub/sub handlers now attach ``__mqtt_action__`` metadata for automatic
    discovery and registration
  - **Improvement**: Converted internal handler functions (``_handler``, ``_position_handler``,
    ``_attitude_handler``, ``_statustext_handler``) to ``async def`` for asynchronous message
    processing
  - **Fix**: Fixed missing ``await`` on ``asyncio.sleep(0.1)`` in a test handler
  - **Cleanup**: Removed unused ``RedisProxy`` import

- Updated ``petal-leafsdk`` from ``v0.2.9`` to ``v0.2.10``:

  - **Refactor**: 3 MQTT command handlers (``mission_plan``, ``rtl``, ``goto``) now registered
    via ``@mqtt_action`` decorator, removing legacy ``_mqtt_subscribe_to_mission_plan`` and
    ``_mqtt_command_handler_master``
  - **Improvement**: All MAVLink message handler methods in ``fc_status_provider.py`` converted
    to ``async def`` for non-blocking message processing
  - **Improvement**: All Redis and MAVLink publishing functions in ``mission.py``,
    ``mission_step.py``, and ``heartbeat.py`` converted to ``async def``
  - **Improvement**: Updated type annotations for MAVLink subscription setup and teardown
    functions to require async callbacks
  - **Fix**: Fixed ``msg_id`` ``NameError`` bug in legacy master handler (caught during refactor)

- Updated ``petal-warehouse`` from ``v0.1.8`` to ``v0.1.9``:

  - **Improvement**: Captured main event loop (``self._loop``) from ``MavLinkExternalProxy``
    during initialization for safe coroutine scheduling from background threads
  - **Improvement**: ``send_position`` and ``send_target_traj`` WebSocket methods now use
    ``asyncio.run_coroutine_threadsafe`` to execute in the correct event loop, preventing
    threading issues
  - **Improvement**: MAVLink message handler functions (``handler_pos``, ``handler_att``,
    ``handler_target_trajectory``) converted to ``async def``

- Updated ``petal-qgc-mission-server`` from ``v0.1.3`` to ``v0.1.4``:

  - **Refactor**: Message router refactored to support async handlers; ``route()`` method is now
    ``async`` and awaits handler results if they are coroutines
  - **Refactor**: MAVLink server main loop and message draining/handling methods converted to
    ``async`` for non-blocking message processing and routing
  - **Refactor**: Mission upload and download protocol handlers (``upload.py``, ``download.py``)
    converted to ``async``, including ``request_waypoint``, ``_finalize_upload``, and all
    mission item/count/request handlers
  - **Refactor**: Mission translation and Redis publishing logic (``translation.py``) converted
    to ``async``; all Redis interactions are now properly awaited
  - **Improvement**: All internal handler methods in bridge and connection modules converted to
    ``async`` to ensure the entire message handling pipeline is non-blocking

Version 0.1.62 (2026-02-06)
---------------------------

**New Features:**

- Added single-motor ESC calibration (``esc_calibration_single``) documentation and Postman API collection entries:

  - Detailed step-by-step workflow: initialization, maximum throttle, minimum throttle, safe stop
  - Emergency stop handling via ``force_cancel_calibration``
  - Separate Postman requests for each calibration step targeting ``{{CALLBACK_URL}}/mqtt-callback/callback``

**PX4 Reboot Workflow Improvements:**

- Enhanced ``reboot_px4`` command documentation to clarify heartbeat-based reboot confirmation:

  - Reboot is confirmed via heartbeat drop (PX4 shutting down) and heartbeat return (PX4 alive again)
  - Updated immediate response message to specify confirmed status is published to ``command/web``
  - Clarified client timing expectations: reboot confirmation can take up to ~35 seconds

- Improved Postman reboot request descriptions and payloads to reflect the confirmed reboot flow

**Documentation & Metadata Updates:**

- Updated petal-user-journey-coordinator documentation version from ``v0.1.8`` to ``v0.1.10``
- Improved Postman collection metadata and preview settings for better usability

**Dependency Updates:**

- Updated ``petal-user-journey-coordinator`` from ``v0.1.9`` to ``v0.1.10``:

  - **Feature**: Added ``ESCCalibrationSingleController`` class implementing step-by-step single-motor ESC calibration workflow with interface setup, per-motor parameter configuration, and throttle control
  - **Feature**: Introduced ``ESCCalibrationSinglePayload`` Pydantic model with motor index, calibration state, safety timeout, throttle commands, and ESC interface selection
  - **Feature**: Added ``ESC_CALIBRATION_SINGLE`` operation mode to the ``OperationMode`` enum
  - **Integration**: Registered ``ESCCalibrationSingleController`` and ``ESCCalibrationSinglePayload`` in the plugin startup routine and command handler setup

Version 0.1.61 (2026-02-03)
---------------------------

**Documentation Updates:**

- Added comprehensive MQTT Topics Reference sections to petal documentation:

  - **petal-user-journey-coordinator**: Lists all commands received on ``command/edge`` and topics published to ``command/web``
  - **petal-flight-log**: Lists all commands received on ``command/edge`` and topics published to ``command/web``

- Enhanced ``reboot_px4`` command documentation with two-phase response pattern:

  - Phase 1: Immediate ``send_command_response`` for command acknowledgement
  - Phase 2: Async ``publish_message`` to ``command/web`` with reboot status
  - Documented all error response types (``OPERATION_ACTIVE``, ``VALIDATION_ERROR``, ``HANDLER_ERROR``)
  - Added front-end handling instructions for status subscription

**Dependency Updates:**

- Updated ``petal-user-journey-coordinator`` from ``v0.1.8`` to ``v0.1.9``:

  - **Refactor**: Refactored ``_reboot_px4_message_handler`` with two-phase response pattern:

    - Immediate ``send_command_response`` acknowledges command receipt
    - Sequential ``await reboot_autopilot`` executes the reboot
    - ``publish_message`` publishes final status to ``/petal-user-journey-coordinator/reboot_px4_status``

  - **Feature**: Added ``RebootPX4StatusPayload`` Pydantic model for structured reboot status payloads
  - **Fix**: Added missing ``return`` statement after ``ValidationError`` handler to prevent fall-through execution
  - **Improvement**: All error responses (validation, handler errors) now sent immediately via ``send_command_response``

Version 0.1.60 (2026-01-30)
---------------------------

**Plugin Loading & Startup Refactor:**

- Separated petal loading into two distinct phases for finer control and clearer logging:

  - ``initialize_petals``: Loads and configures petals without starting them
  - ``startup_petals``: Starts up and mounts petals to the FastAPI app
  - Original ``load_petals`` function now wraps these two steps

- Updated main application startup logic to use new initialization pattern, ensuring petals are loaded and started sequentially and safely in the background

**MQTT Callback & Routing Improvements:**

- Registered MQTT callback router under ``/mqtt-callback`` path only when MQTT proxy and callbacks are enabled
- Changed default MQTT callback port to ``9000`` to match main app's port (previously used dedicated server on port 3005)
- Updated Postman collection and FastAPI launch configuration for new callback endpoint URL

**Proxy & Threading Enhancements:**

- Added explicit thread name prefixes to all proxy thread pools and background threads for easier debugging and log tracing:

  - ``S3BucketProxy``: Thread pool naming for S3 operations
  - ``CloudProxy``: Thread pool naming for cloud operations
  - ``LocalDbProxy``: Thread pool naming for database operations
  - ``MavLinkExternalProxy``: I/O and worker thread naming

- Exposed ``PETAL_REDIS_WORKER_THREADS`` environment variable to configure Redis proxy worker threads
- Increased Redis proxy ``ThreadPoolExecutor`` workers to prevent blocking listen loops from starving key/value operations
- Added ``_invoke_callback_safely()`` method in Redis proxy for proper async callback handling from worker threads using ``asyncio.run_coroutine_threadsafe()``

**Health Check Logic:**

- Simplified MavLink proxy health check to only consider main connection status, excluding ``leaf_fc_connected`` flag

**Dependency Updates:**

- Updated ``petal-warehouse`` from ``v0.1.7`` to ``v0.1.8``:

  - **Version Management**: ``PetalWarehouse.version`` attribute now dynamically references package ``__version__`` instead of being hardcoded
  - **Thread Naming**: Background thread for sending position and yaw data to Blender now named ``BlenderPositionSender`` for improved debugging and monitoring

Version 0.1.59 (2026-01-27)
---------------------------

**Dependency Updates:**

- Updated ``leaf-pymavlink`` from ``v0.1.15`` to ``v0.1.16``:

  - **Critical Fix**: Fixed PyPI wheel builds missing DroneLeaf LEAF_* MAVLink messages
  - Root cause was pip's build isolation preventing the ``MDEF`` environment variable from reaching setup.py
  - CI workflow now uses ``--no-build-isolation`` with explicit dependency installation to ensure custom message definitions are included in wheels

- Updated ``petal-leafsdk`` from ``v0.2.7`` to ``v0.2.9``:

  - Pinned ``leaf-pymavlink`` to ``v0.1.16``

Version 0.1.57 (2026-01-18)
---------------------------

**Dependency Updates:**

- Updated ``leaf-pymavlink`` to ``v0.1.15``

- Updated ``petal-leafsdk`` from ``v0.2.6`` to ``v0.2.7``:

  - Pinned ``leaf-pymavlink`` to ``v0.1.15``

Version 0.1.56 (2026-01-17)
---------------------------

**FTP Download Error Handling Improvements:**

- Improved error handling in ``external.py`` FTP download logic to ensure failed or cancelled downloads raise a ``RuntimeError``, log the error, and clean up partial files
- Added more granular error logging and FTP state reset logic after failures or cancellations, including after non-zero return codes from FTP operations
- Ensured FTP state is reset after each download attempt and after recovering from temp files, preventing state leakage between operations

**Dependency Updates:**

- Updated ``petal-flight-log`` from ``v0.2.4`` to ``v0.2.5``:

  - **Error Handling Improvements**:

    - Added specific handling for ``RuntimeError`` during MAVFTP ULog downloads, providing clearer error messages when the remote file cannot be opened
    - Changed logging for failed ULog downloads to exclude exception tracebacks for both MAVLink and MAVFTP errors, making logs less verbose

  - **Reliability Enhancements**:

    - Ensured flight record status is updated in the cloud database before exceptions are re-raised during sync job errors, improving consistency between job state and record status

  - **Logic and Workflow Adjustments**:

    - Updated ``start_sync_flight_record`` to always attempt ULog and Rosbag uploads if present, regardless of whether an S3 key already exists
    - Added handling for files from both "pixhawk" and "local" storage types

- Updated ``petal-leafsdk`` from ``v0.2.5`` to ``v0.2.6``:

  - **Mission Abort and Drone State Handling**:

    - Improved ``abort`` method to handle abort requests during takeoff or landing states
    - Mission is cancelled locally without sending stop trajectory to flight controller during these states, preventing unsafe interruptions
    - Added new ``is_drone_taking_off`` method in ``fc_status_provider.py``

  - **MQTT Communication and Error Handling**:

    - Refactored all MQTT command handlers to use new ``send_command_response`` method for sending responses and errors
    - Replaced direct calls to ``publish_message`` for more consistent and reliable client communication

  - **Startup and Proxy Initialization**:

    - Improved startup logic by separating proxy initialization from asynchronous MQTT topic setup
    - Added more robust logging and retry logic for MQTT proxy availability
    - Simplified ``async_startup`` method, delegating complex logic to the main application

  - **Mission Queue and RTL Safety**:

    - Reduced mission queue size from 10 to 1 to avoid overloading the mission manager
    - Decreased RTL (Return-To-Launch) mission return speed from 0.5 m/s to 0.1 m/s for safer drone returns

- Updated ``petal-qgc-mission-server`` from ``v0.1.2`` to ``v0.1.3``:

  - **Mission Translation Logic Updates**:

    - Replaced all uses of ``calculate_yaw_to_target`` with ``calculate_yaw_to_target_ENU`` in ``mission_translator.py``
    - Affects takeoff, waypoint, land, and RTL command handling to ensure yaw calculations consistently use the ENU coordinate system

  - **Logging Changes**:

    - Changed logging level for local position NED updates in ``gps.py`` from ``info`` to ``debug``, reducing log verbosity for frequent updates

Version 0.1.54 (2026-01-15)
---------------------------

**Dependency Updates:**

- Updated ``petal-leafsdk`` from ``v0.2.3`` to ``v0.2.4``:
- Pinned ``leaf-pymavlink`` to ``v0.1.13`` for MAVLink compatibility stability

Version 0.1.53 (2026-01-15)
---------------------------

**Dependency Updates:**

- Updated ``petal-flight-log`` from ``v0.2.3`` to ``v0.2.4``:

  - **Feature**: Improved progress tracking with weighted job distribution
  - ULog download now accounts for 90% of sync progress when present
  - S3 upload jobs split remaining 10% (5% each) when ULog download exists
  - S3 jobs split 100% evenly (50% each, or 100% if single job) when no ULog download
  - Added ``_calculate_job_weights()`` method for dynamic weight calculation
  - Updated ``_monitor_sub_job_progress()`` to use weight-based progress slices

Version 0.1.52 (2026-01-14)
---------------------------

**Configuration Updates:**

- Updated ``proxies.yaml`` to replace ``petal-mission-planner`` with ``petal-leafsdk``
- Updated plugin entry points for ``petal-leafsdk`` and ``petal-qgc-mission-server``
- Revised petal dependencies for more accurate service configuration

**New Proxy Functionality:**

- Added async ``head_object`` method to ``bucket.py`` for checking S3 object existence and retrieving metadata
- Added ``build_request_message_command`` method to ``external.py`` for requesting specific MAVLink messages
- Added ``build_shell_serial_control_msgs`` method to ``external.py`` for sending shell commands to PX4 via MAVLink

**Logging Improvements:**

- Enhanced application startup and shutdown logs in ``main.py`` with clearer, more prominent status messages

**Health Model Validation:**

- Migrated all Pydantic v1 ``@validator`` decorators to Pydantic v2 ``@field_validator`` in ``models/health.py``:

  - Added ``@classmethod`` decorator and proper type hints to all validators
  - Updated import from ``validator`` to ``field_validator``
  - Resolves deprecation warnings for Pydantic v2.0+ (to be removed in v3.0)

**Dependency Updates:**

- Upgraded ``leaf-pymavlink``, ``petal-leafsdk``, ``petal-user-journey-coordinator``, and ``petal-qgc-mission-server`` in ``pyproject.toml``
- Added ``petal-qgc-mission-server`` as a local editable install in development dependencies

- Updated ``petal-user-journey-coordinator`` from ``v0.1.7`` to ``v0.1.8``:

  - **Fix**: Bulk parameter setting now handles floating-point precision issues correctly
  - Uses ``math.isclose()`` with relative tolerance (1e-5) for float32/float64 comparison
  - Resolves false validation failures for parameters like ``0.2`` vs ``0.20000000298023224``

- Updated ``petal-flight-log`` from ``v0.2.1`` to ``v0.2.3``:

  - **Refactor**: Centralized table name constants (``FLIGHT_RECORD_TABLE``, ``LEAF_FC_RECORD_TABLE``)
  - Replaced all hardcoded table name strings with constants in ``jobs.py`` and ``plugin.py``
  - Plugin version now set dynamically from package ``__version__``

- Updated ``pymavlink`` to ``v0.1.14``:

  - Added MAVLink definitions for ``petal-leafsdk`` v0.2.3 mission states and actions

- Updated ``LeafSDK`` to ``v0.3.3``:

  - Refactored class naming for improved clarity
  - Distributed state synchronization
  - Mission state analysis documentation
  - Mission planning and trajectory updates
  - Refactored mission step handling
  - Joystick mode updates to match MAVLink
  - New mission configuration format support

- Updated ``petal-leafsdk`` to ``v0.2.3``:

  - **Major Refactor**: Mission flow and state management overhaul
  - Refactored mission execution logic with FSM and heartbeat modules
  - Distributed state synchronization and centralized state management
  - New MAVLink definitions integration
  - Mission behavior bug fixes
  - Enhanced mission step handling and joystick mode functionality
  - Comprehensive documentation and testing utilities
  - CI/CD pipeline integration

- Updated ``petal-qgc-mission-server`` to ``v0.1.2``:

  - **New Feature**: Working adapter for QGC mission planning and execution updates
  - Renamed ``MissionStep`` to ``MissionPlanStep`` for consistency
  - Renamed plugin class from ``QGCMissionAdapterPetal`` to ``PetalQGCMissionServer``
  - Added ``calculate_yaw_to_target`` function for NED frame yaw calculations
  - Renamed previous function to ``calculate_yaw_to_target_ENU`` for clarity

Version 0.1.51 (2026-01-08)
---------------------------

**Breaking Changes:**

- Renamed ``flight-log-petal`` to ``petal-flight-log`` throughout the codebase for naming consistency:

  - Updated all references in ``proxies.yaml`` (enabled petals, proxy mappings, dependencies)
  - Updated API documentation and example requests
  - Updated Postman collection and environment files

**Dependency Updates:**

- Updated ``petal-flight-log`` from ``v0.2.0`` to ``v0.2.1``:

  - **Critical Fix**: Corrected MQTT topic prefix from ``flight-log-petal`` to ``petal-flight-log`` to match petal naming convention
  - **Critical Fix**: Corrected MQTT topic prefix from ``petal-user-journey-coordinator`` to ``petal-flight-log`` to match petal naming convention: was causing a conflict with user journey coordinator
  - Resolves MQTT subscription issues where topics were not matching expected patterns

- Updated ``petal-user-journey-coordinator`` from ``v0.1.6`` to ``v0.1.7``:

  - **Critical Fix**: Added MQTT topic prefix from ``petal-user-journey-coordinator`` to ``petal-user-journey-coordinator`` for consistency
  - Ensures proper MQTT message routing and subscription handling

- Updated ``petal-qgc-mission-server`` mapping and dependencies in ``proxies.yaml``

**MAVLink Proxy Configuration:**

- Added required MAVLink system identification parameters:

  - ``SOURCE_SYSTEM_ID``: System ID for MAVLink messages (default: ``1``)
  - ``SOURCE_COMPONENT_ID``: Component ID for MAVLink messages (default: ``1``)
  - Exposed via environment variables and ``ProxyConfig`` in ``src/petal_app_manager/__init__.py``
  - Passed to ``MavLinkExternalProxy`` constructor in ``main.py`` and ``external.py``

- Changed default log directory from ``/var/log/petal-app-manager`` to ``logs`` for development convenience

**Health Model Validation:**

- Refactored all Pydantic health models in ``models/health.py`` to use Pydantic v2's ``@field_validator`` decorator:

  - Updated validators for ``SystemHealthStatus``, ``PetalHealthStatus``, ``RedisHealthStatus``
  - Updated validators for ``MqttHealthStatus``, ``MavLinkHealthStatus``, ``HealthStatus``
  - Ensures compatibility with Pydantic v2 and removes deprecation warnings
  - Maintains backward compatibility with existing health status enumeration values

**Testing Improvements:**

- Fixed unit tests in ``test_external_proxy.py`` to include required ``source_system_id`` and ``source_component_id`` parameters
- Fixed unit tests in ``test_mavlink_proxy.py`` to use updated ``MavLinkExternalProxy`` constructor signature
- Updated Postman environment file with new test variables (``test_flight_record``, ``CALLBACK_URL``, ``TS_CLIENT_URL``)

**Migration Guide:**

If you have existing configurations or integrations referencing ``flight-log-petal``, update them to ``petal-flight-log``:

- Environment variable names
- MQTT topic subscriptions
- API endpoint references
- Configuration files

Version 0.1.50 (2026-01-05)
---------------------------

**Configuration Enhancements:**

- All environment variables now use the ``PETAL_`` prefix to avoid conflicts with other applications.
- Added ``PETAL_LOG_DIR`` environment variable for configuring log file directory:

  - **Development**: ``logs`` (relative to project directory)
  - **Production**: ``/home/droneleaf/.droneleaf/petal-app-manager``

**MAVLink Proxy Improvements:**

- Added ``set_params_bulk_lossy`` async method for efficient bulk parameter setting over lossy links:

  - Windowed sends with configurable ``max_in_flight`` parameter
  - Automatic periodic resend of unconfirmed parameters
  - Retry cap with configurable ``max_retries``
  - Optional parameter type specification (``UINT8``, ``INT16``, ``REAL32``, etc.)
  - Confirmation via echoed ``PARAM_VALUE`` messages

- Added ``get_params_bulk_lossy`` async method for efficient bulk parameter retrieval:

  - Uses ``PARAM_REQUEST_READ`` by name with windowed requests
  - Periodic resend of pending requests up to retry limit
  - Returns partial results on timeout for resilience

- Added ``reboot_autopilot`` async method to ``MavLinkExternalProxy`` for rebooting the autopilot (PX4/ArduPilot):

  - Sends ``MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN`` command and waits for ``COMMAND_ACK``
  - Optional ``reboot_onboard_computer`` parameter to also reboot the onboard computer
  - Returns structured ``RebootAutopilotResponse`` with success status, status code, and reason
  - Fallback verification via heartbeat drop/return detection when no ACK is received
  - Comprehensive status codes for all failure scenarios (denied, rejected, unsupported, etc.)

**Petal Loading Architecture:**

- Updated ``proxies.yaml`` configuration to support two distinct petal loading strategies:

  - **startup_petals**: Petals loaded synchronously during server startup (blocking)
    
    - Critical petals that must be available before the server accepts requests
    - Server waits for these petals to fully initialize
    - Example: ``petal-user-journey-coordinator``

  - **enabled_petals**: Petals loaded asynchronously after server startup (non-blocking)
    
    - Background task spawned after server is ready to accept requests
    - Loads petals one-by-one without blocking the main event loop
    - Reduces server startup time and improves responsiveness
    - Example: ``flight-log-petal``, ``petal-warehouse``, ``petal-mission-planner``

- Refactored petal async startup into reusable ``_handle_petal_async_startup()`` helper

**Health Monitoring Enhancements:**

- Added ``PetalHealthInfo`` model to track individual petal status:

  - ``name``: Petal identifier
  - ``status``: One of ``loaded``, ``loading``, ``failed``, ``not_loaded``
  - ``version``: Petal version if available
  - ``is_startup_petal``: Whether this is a critical startup petal
  - ``load_time``: ISO timestamp when petal was loaded
  - ``error``: Error message if petal failed to load

- Extended ``HealthMessage`` to include ``petals`` array with real-time petal loading status
- Health publisher now reports petal loading progress during background loading phase

**S3 Bucket Proxy Improvements:**

- Added ``move_file`` async method to ``bucket.py`` for moving (renaming) files within the S3 bucket, which performs a copy followed by a delete operation.
- Enhanced ``upload_file`` method to accept an optional ``custom_s3_key`` parameter, allowing callers to specify the exact S3 key for uploads.

**Redis Proxy Improvements:**

- Added ``scan_keys`` async method to ``redis.py`` to efficiently scan and return keys matching a given pattern, supporting pagination via the ``count`` parameter.
- Changed Redis set operation logging from info to debug level to reduce log verbosity for routine key writes.

Version 0.1.49 (2025-01-05)
---------------------------

**Bug Fixes:**

- Remove redundant log streaming utility files and references:

  - Deleted ``log_streamer.py`` from ``utils/`` directory
  - Removed import and endpoint registration for log streaming in ``config_api.py`` and ``main.py``

Version 0.1.48 (2025-12-31)
---------------------------

**Bug Fixes:**
- Added mqtt as a dependency for `petal-mission-planner` in `proxies.yaml`

Version 0.1.47 (2025-12-31)
---------------------------

**Bug Fixes:**

- Fix all Petal plugin keys in ``proxies.yaml`` to match correct ``__name__`` attribute in ``plugin.py``:

  - flight_records → flight-log-petal
  - petal_warehouse → petal-warehouse
  - mission_planner → petal-mission-planner
  - petal_user_journey_coordinator → petal-user-journey-coordinator
  - qgc_petal → petal-qgc-mission-server

Version 0.1.46 (2025-12-31)
---------------------------

**Bug Fixes:**
- Made the robot_type_id field in the `LocalDbMachineInfo` model (`health.py`) optional, allowing it to be `None` if not provided.

Version 0.1.45 (2025-11-23)
---------------------------

**Architecture Enhancements:**

- **Multi-Threaded MAVLink Processing** - Significant performance improvements for MAVLink message handling:
  
  - **ExternalProxy and MavLinkExternalProxy**: Now use I/O thread + multiple worker threads architecture
  - **I/O Thread**: Dedicated thread for reading/writing MAVLink messages (non-blocking)
  - **Worker Threads**: Configurable pool of threads for processing handlers in parallel (default: 4)
  - **Thread-Safe Message Buffer**: Deque-based buffer with thread-safe enqueue/dequeue operations
  - **Configuration**: ``MAVLINK_WORKER_THREADS`` environment variable (default: 4)
  - **Performance**: 2x throughput improvement with parallel handler processing

- **Resilient Proxy Startup** - Enhanced reliability and stability:
  
  - **Non-Blocking Startup**: MQTT and Cloud proxies no longer crash the FastAPI server on connection failures
  - **Graceful Degradation**: Proxies log warnings and remain inactive until dependencies are available
  - **Background Monitoring**: Automatic retry tasks monitor and reconnect failed proxies
  - **Configurable Retry Intervals**: All timeout/retry values centralized in ``ProxyConfig`` class
  - **Environment Control**: Override timeouts via environment variables without code changes

**Configuration Management:**

- **Centralized ProxyConfig Class** - New configuration section for proxy connection management:
  
  - ``MQTT_RETRY_INTERVAL`` - Monitoring task retry interval (default: 10.0 seconds)
  - ``CLOUD_RETRY_INTERVAL`` - Cloud proxy retry interval (default: 10.0 seconds)
  - ``MQTT_STARTUP_TIMEOUT`` - MQTT startup timeout (default: 5.0 seconds)
  - ``CLOUD_STARTUP_TIMEOUT`` - Cloud token fetch timeout (default: 5.0 seconds)
  - ``MQTT_SUBSCRIBE_TIMEOUT`` - Topic subscription timeout (default: 5.0 seconds)

- **Hybrid Petal Loading** - Massive performance improvement for petal initialization:
  
  - **Direct Path Import**: Load petals from ``module.submodule:ClassName`` paths (~0.002ms)
  - **Entry Point Fallback**: Falls back to traditional entry point discovery if path fails (~67ms)
  - **4355x Speedup**: Direct path loading is 4355 times faster than entry point discovery
  - **Configuration**: Define petal paths in ``proxies.yaml`` under ``petals`` section

**Health Monitoring Updates:**

- **Enhanced Thread Tracking** - Updated health check models for multi-threaded architecture:
  
  - ``MavlinkWorkerThreadInfo``: Separate tracking for I/O thread and worker threads
  - ``io_thread_running``: Boolean status for I/O thread
  - ``io_thread_alive``: Health status for I/O thread
  - ``worker_threads_running``: Boolean status for worker threads
  - ``worker_thread_count``: Number of configured worker threads
  - ``worker_threads_alive``: Count of healthy worker threads

**Stability Improvements:**

- Fixed server freeze during startup when TypeScript MQTT client is unavailable
- Fixed 30-second timeout blocking in MQTT proxy subscription operations
- Improved error handling for missing organization IDs during proxy startup
- Enhanced monitoring tasks with proper timeout protection
- All proxy operations respect configurable timeout values

**Developer Benefits:**

- Faster petal loading during development (4355x speedup)
- No server crashes when cloud/MQTT services are unavailable
- Easy timeout/retry configuration via environment variables
- Better visibility into proxy connection status via health endpoints
- Improved multi-threading performance for high-throughput scenarios

Version 0.1.44 (2025-11-07)
---------------------------

**Configuration Enhancements:**

- **MQTTProxy Topic Configuration** - MQTT topic names now configurable via environment variables
  
  - Added environment-configurable topic parameters to MQTTProxy class:
    
    - ``command_edge_topic`` - Configurable via ``COMMAND_EDGE_TOPIC`` (default: ``command/edge``)
    - ``response_topic`` - Configurable via ``RESPONSE_TOPIC`` (default: ``response``)
    - ``test_topic`` - Configurable via ``TEST_TOPIC`` (default: ``command``)
    - ``command_web_topic`` - Configurable via ``COMMAND_WEB_TOPIC`` (default: ``command/web``)

  - Topics now read from ``Config`` class enabling direct environment control
  - Improved deployment flexibility across different MQTT broker configurations

**Developer Benefits:**
- Simplified MQTT topic customization for different environments
- Enhanced configuration management without code changes
- Better separation of configuration from implementation

Version 0.1.43 (2025-11-05) - Hotfix
------------------------------------

**Breaking Changes:**

- **MQTTProxy Refactoring** ⚠️ **Code Breaking Changes** ⚠️
  - Handler-based subscription model replaces arbitrary topic subscriptions
  - Petals now register handlers for ``command/edge`` topic using ``register_handler(callback)``
  - All command messages flow through registered handlers with command-based routing
  - Single subscription per petal with command-based routing

**Removed Public Methods:**
- ``subscribe_to_topic()`` - Now private
- ``unsubscribe_from_topic()`` - Now private  
- ``subscribe_pattern()`` - Removed (use command-based routing instead)

**New Public Methods:**

.. code-block:: python

  # Register a handler for command/edge topic
  def register_handler(handler: Callable) -> str:
    """Returns subscription_id for later unregistration"""

  # Unregister a handler
  def unregister_handler(subscription_id: str) -> bool:
    """Remove handler using its subscription_id"""

  # Publish to command/web topic
  async def publish_message(payload: Dict[str, Any], qos: int = 1) -> bool:
    """Publish message to command/web topic"""

  # Send response to response topic
  async def send_command_response(message_id: str, response_data: Dict[str, Any]) -> bool:
    """Send command response with automatic topic routing"""

**Dependencies Updated:**
- Latest ``petal-leafsdk`` compatibility
- Latest ``petal-user-journey-coordinator`` compatibility

Version 0.1.42 (2025-11-03)
---------------------------

**Health Reporting Enhancements:**

- ``/health/overview`` endpoint now contains version information for each Petal component:

  - ``petal_leafsdk``
  - ``petal_flight_log``
  - ``petal_warehouse``
  - ``petal_user_journey_coordinator``
  - ``petal_qgc_mission_server``

- Components report ``"not installed"`` when not available

**Dependency Updates:**
- Updated ``petal-user-journey-coordinator`` dependency to version ``v0.1.3``
- Bumped application version from ``0.1.41`` to ``0.1.42``

Version 0.1.41 (2025-11-02)
---------------------------

**Bug Fixes:**
- Fixed health publishing error: ``'MavlinkProxyHealth' object has no attribute 'details'``
- Mavlink connection issues now report INFO messages instead of ERROR logs
- Improved error handling for unhealthy mavlink connections

Version 0.1.39 (2025-10-23)
---------------------------

**New Features:**
- ``/health/overview`` endpoint for accessing Petal App Manager version
- Dynamic version retrieval using ``import petal_app_manager; print(petal_app_manager.__version__)``
- Version information added to controller dashboard message ``/controller-dashboard/petals-status``

**API Enhancements:**
- Controller dashboard now includes version field in status responses:

.. code-block:: javascript

   {
     "title": "Petal App Manager",
     "component_name": "petal_app_manager", 
     "status": "healthy",
     "version": "0.1.39",
     "message": "Good conditions",
     "timestamp": "2025-10-23T14:35:30.143747",
     "services": [...]
   }

Version 0.1.38 (2025-10-23)
---------------------------

**Stability Improvements:**
- MAVFTP reliability improvements for Pixhawk SD card file system operations
- Enhanced download and file system information request stability
- Overall Petal App Manager stability improvements

**Related Releases:**
- ``petal-user-journey-coordinator`` v0.1.1 - Fixed square test JSON response compatibility bug

Version 0.1.37 (2025-10-22)
---------------------------

**Bug Fixes:**
- Cloud proxy error message improvements
- Fixed MAVFTP reliability issues affecting overall system reliability
- Fixed ``petal-user-journey-coordinator`` bugs

**Stability:**
- Improved overall reliability of petal-app-manager
- Enhanced MAVFTP communication stability

Version 0.1.31 (2025-09-25)
---------------------------

**New Features:**
- **MQTT Middleware Proxy** - Unified interface for MQTT communications
- **Organization Manager** - Fetches organization ID without DynamoDB dependency
- **LeafFC Heartbeat Check** - Added to logs and ``/health/detailed`` endpoint

**Stability Improvements:**
- Enhanced server startup and shutdown sequence (avoiding dead-locks)
- Improved system reliability and error handling

**Related Releases:**

- **Petal User Journey Coordinator** - MQTT integration for web client applications:

  - Multiple handlers for PX4 parameter management
  - ESC calibration with keep-alive streaming
  - Real-time telemetry streaming to web client
  - Debug flag for square test with plotting and data dump

Version 0.1.29 (2025-08-28)
---------------------------

**New Features:**

- **MQTT Middleware Proxy**:

  - Reduces integration complexity for local applications
  - Unified interface to MQTT communications
  - Enables faster development cycles
  - Centralizes communication logic for easier maintenance

- **Petal & Proxy Control Dashboard**:

  - Unified control and transparency for all proxies and petals
  - Real-time health monitoring and dependency tracking
  - Centralized enable/disable controls and API testing
  - Real-time log streaming and filtering
  - Accessible at ``http://localhost/home/petals-proxies-control``

**Business Value:**
- Faster development and maintenance cycles
- Scalable and flexible operations
- Reduced Petal App Manager overhead

Version 0.1.28 (2025-08-17)
---------------------------

**New Features:**
- **Redis Pattern PubSub Support** - Enhanced communication reliability
- **LeafFC v1.4.0 Compatibility** - Improved internal DroneLeaf system communication
- **Log Output Configuration** - Configurable log level routing via ``config.json``

**Bug Fixes:**
- S3 bucket access credential refresh from session manager
- HEAR_CLI ``petal-app-manager-prepare-arm`` and ``petal-app-manager-prepare-sitl`` fixes

**Improvements:**
- Enhanced communication between LeafFC and LeafSDK
- Improved log management and debugging capabilities

Version 0.1.23 (2025-07-31)
---------------------------

**Major Updates:**
- **Cloud Integration**: Full implementation of cloud DynamoDB and S3 bucket proxies
- **Flight Log Integration**: Latest ``petal-flight-log`` v0.1.4 for cloud syncing endpoints
- **Error Management**: Routes for clearing error flags from edge devices
- **MAVLink Improvements**: Enhanced proxy communication with threading locks for non-thread safe operations

**Minor Updates:**
- Centralized configuration management
- Updated ``petal-warehouse`` v0.1.3 with pymavlink bug fixes

**Related Releases:**
- ``petal-flight-log`` v0.1.4 - Flight record management and cloud syncing
- ``LeafSDK`` v0.1.5 - Mission flow control and progress updates (pause, resume, cancel)

Version 0.1.18 (2025-07-29)
---------------------------

**New Features:**
- **Burst Message Support** - Optional burst message capability
- **Message Timeout Control** - Configurable timeouts to reduce CPU overhead
- **Detailed Health Check** - ``/health/detailed`` endpoint for field status checks
- **Petal Template** - HEAR_CLI petal initialization template

**HEAR_CLI Integration:**

.. code-block:: bash

   hear-cli local_machine run_program --p petal_init

**Related Releases:**

- ``LeafSDK Petal`` v0.1.5:

  - Upgraded trajectory polynomial coefficient generation
  - Burst MAVLink messages for improved communication reliability
  - Addressed robustness issues in LeafSDK functionalities

**Known Limitations:**
- Trajectory sampling causes jitter (needs LeafFC-side implementation)
- MAVLink communication over mavlink-router lacks reliability (Redis recommended)

Version 0.1.5 (2025-07-03) - First Stable Release
--------------------------------------------------

**Milestone Release:**
- First stable release of Petal App Manager
- Available on PyPI: https://pypi.org/project/petal-app-manager/
- HEAR_CLI support for development and production deployment

**Related Petal Releases:**

- **Flight Log Petal** v0.1.1:
  - Added ability to cancel Pixhawk downloads
  - Prevents mavlink connection interruption

- **LeafSDK Petal** v0.1.0:
  - Mission planning library integration
  - Easy deployment in DroneLeaf ecosystem
  - External application compatibility

- **Warehouse Management Petal** v0.1.0:
  - Real-time drone publishing via MAVLink over WebSocket
  - Blender visualization integration

Version 0.1.0 (2025-06-22) - Initial Release
--------------------------------------------

**Milestone:**
- Passed initial testing phase
- First public release

**Core Capabilities:**
- MAVLink connection management abstraction
- Local DynamoDB database integration
- Redis cache support
- Cloud infrastructure communication
- ROS1 topic integration

**Availability:**
- PyPI: https://pypi.org/project/petal-app-manager/
- GitHub: https://github.com/DroneLeaf/petal-app-manager.git

**Business Value:**
- Accelerated development cycles
- Reduced implementation costs
- Low-level code abstraction
- Simplified drone application development
