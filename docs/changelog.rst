Changelog
=========

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

.. code-block:: json

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
