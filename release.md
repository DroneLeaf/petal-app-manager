
Changelog:

:alert: petal-app-manager v0.1.43 hotfix  is released (2025-11-05)


### Main Changes to MQTTProxy (code breaking! :biohazard_sign:) please pull latest `petal-app-manager` stack and pull latest `petal-leafsdk` and `petal-user-journey-coordinator` which depend on refactored `MQTTPRoxy`

#### 1. **Handler-Based Subscription Model**

**Before:**
* Petals could subscribe to arbitrary topics using `subscribe_to_topic(topic, callback)`
* Each petal managed its own topic subscriptions

**After:**
* Petals register handlers for the `command/edge` topic using `register_handler(callback)`
* All command messages flow through registered handlers
* Single subscription per petal with command-based routing

**Removed Public Methods:**
* `subscribe_to_topic()` - Now private
* `unsubscribe_from_topic()` - Now private
* `subscribe_pattern()` - Removed (use command-based routing instead)

**New Public Methods:**
```python
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
    """Send command response with automatic topic routing"""```

=================

petal-app-manager v0.1.42  is released (2025-11-03)

**Health reporting enhancements:**

* The `/health/overview` endpoint now contains the version of each Petal component (`petal_leafsdk`, `petal_flight_log`, `petal_warehouse`, `petal_user_journey_coordinator`, `petal_qgc_mission_server`). If a component is not installed, it reports `"not installed"`.

**Dependency and version updates:**

* Updated `petal-user-journey-coordinator` dependency to version `v0.1.3` in `pyproject.toml`.
* Bumped the application version from `0.1.41` to `0.1.42` in `pyproject.toml`.

=================

petal-app-manager v0.1.41  is released (2025-11-02)
Includes:
* Fix to a bug with health publishing saying `2025-11-02 20:40:38,411 — root — ERROR — Error publishing health status: 'MavlinkProxyHealth' object has no attribute 'details'`

The bug is harmless and simply trying to state that there is a mavlink connection issue. It will not be reported as an error logging message anymore and instead provide an INFO message saying the mavlink connection is unhealthy
You do not have to upgrade your version if you do not want to continue to work

=================

petal-app-manager v0.1.39 is released (2025-10-23)
Includes:
* `health/overview` endpoint which can be used to access petal app managers version
* dynamic version retrieval using
```import petal_app_manager
print(petal_app_manager.__version__)```
* Version added to controller dashboard message `/controller-dashboard/petals-status`:
```{
  "title": "Petal App Manager",
  "component_name": "petal_app_manager",
  "status": "healthy",
  "version": "0.1.38",     <---------------- NEW
  "message": "Good conditions",
  "timestamp": "2025-10-23T14:35:30.143747",
  "services": [```

=================

Petal App Releases  

Features v0.1.38 (2025-10-23)

Business Value 

Stability improvements to MAVFTP 

Business Value 

Helps download and request file system information from Pixhawk SD card. Also improves the stability of petal app manager 

Petal-user-journey-coordinator v0.1.1 

Fixed bug in the square test not returning a json compatible response message upon test completion causing the web client front-end to timeout waiting for the response 

=================

petal-app-manager v0.1.37  is released (2025-10-22)
Includes:
* Cloud proxy error message fix
* Fixed MAVFTP reliability (which affects overall reliability of petal-app-manager)
* Fixed `petal-user-journey-coordinator` bug (please pull latest for all SITL devices in yout `petal-app-manager-dev/petal-user-journey-coordinator` dir

=================

Features v0.1.31 (2025-09-25)

MQTT Middleware proxy 

Business Value 

Stability improvements to server startup and shutdown sequence (avoid dead-locks) 

Added Organization Manager which fetches organization ID without relying on DynamoDB on a provisioned drone 

Added leafFC heartbeat check to logs and health/detailed endpoint 

Where to find the feature/how to interact with the feature 

Demo link (when relevant) 

Petal User Journey Coordinator 

Business Value 

Allows for seamless integration with web client application via MQTT to deliver various user journey elements directly from the web 

Features 

Multiple handlers with business logic for the following: 

Setting and updating PX4 paramaters 

Perform ESC calibration with a keep-alive streaming signal (for safety) 

Stream real-time telemetry data to the web client for visualization, user-interaction 

Added debug flag for square test in .env file to allow for debugging the test results in the field (produces a plot and data dump in the root directory) 

===============

Features v0.1.29 (2025-08-28)

MQTT Middleware proxy 

Business Value 

Reduces integration complexity for local applications by providing a unified interface to MQTT communications 

Enables faster development cycles as apps don't need to handle MQTT protocol details directly 

Centralizes communication logic, making system maintenance and updates more efficient 

Allows easy addition of new local applications without reconfiguring the MQTT server 

Where to find the feature/how to interact with the feature 

Demo link (when relevant) 

Petal & Proxy Control 

Business Value 

Unified Control & Transparency: Single dashboard to manage all proxies and petals with real-time health monitoring and dependency tracking. 

Faster Development & Maintenance: Centralized enable/disable controls, API testing, and real-time logs reduce debugging effort and accelerate iteration. 

Scalable & Flexible Operations: Easily expand with new components and manage them independently without disrupting the whole system. 

Reduces overhead of Petal-app-manager 

Where to find the feature/how to interact with the feature 

Access the Petals and Proxies Control Dashboard in your browser. 

Use Refresh Proxies/Petals for overall health and connectivity checks. 

Manage Proxy Controls and Petal Controls to: 

View dependencies and connections. 

Enable/disable individual services. 

Refresh or restart components as needed. 

Stream Real-time Application Logs to: 

Monitor live activity. 

Filter by log level. 

Test APIs and reset displays for clean debugging. 

Demo link (when relevant) 

The dashboard is available locally at: http://localhost/home/petals-proxies-control 

===============

Features v0.1.28 (2025-08-17)

Redis pattern pubsub support and compatibility with LeafFC v1.4.0 

Business Value 

Improved communication reliability between internal droneleaf systems on the companion computer 

Example communication between LeafFC and LeafSDK 

Add log output configuration inside `config.json` which allows devs to redirect output of each to level to either the terminal or the app.log file 

Minor bugfix with S3 bucket access (not updating credentials from session manager) 

Minor fix in HEAR_CLI petal-app-manager-prepare-arm and petal-app-manager-prepare-sitl 

Where to find the feature/how to interact with the feature 

Run the latest HEAR_CLI commands to install latest version of petal-app-manager 

Demo link (when relevant) 

===============

Petal App Releases  

Features 

PetalAppManager (v0.1.23) (2025-07-31)

Business Value 

Major updates: 

Includes full implementation of cloud dynamoDB and S3 bucket proxies 

Utilizes latest petal-flight-log v0.1.4 for cloud syncing endpoints 

Includes routes for clearing error flags from the edge device 

Enhances mavlink proxy communication to use threading locks for non-thread safe operations 

Minor updates: 

Centralized configuration management 

Uses petal-warehouse v0.1.3 which fixes some pymavlink bugs 

Where to find the feature/how to interact with the feature 

Demo link (when relevant) 

 

petal-flight-log v(0.1.4) 

Business Value 

Allows for the easy management and recording of flight records within the edge device and syncing with the cloud 

Where to find the feature/how to interact with the feature 

Demo link (when relevant) 

 

LeafSDK Support for Mission Flow Control and Progress Updates (v0.1.5) 

Business Value 

LeafSDK will allow users to safely pause, resume and cancel missions, and update the co-operating application about the progress and the status of the mission. This will allow user to have complete control and visibility on the mission progress. 

Where to find the feature/how to interact with the feature 

Demo link (when relevant) 

 

 

Cloud and S3 Bucket proxies (v0.1.23) 

Business Value 

Allows for seamless communication with AWS dynamoDB and S3 Bucket services 

Allows developers to quickly levergage these services for their cloud needs 

Where to find the feature/how to interact with the feature 

Under the proxies section of petal-app-manager 

Demo link (when relevant) 

===============

PetalApp Manager (v0.1.18) (2025-07-29)

Minor update: 

Includes ability to optionally send burst messages 

Control timeout of recieved messages to reduce CPU overhead 

Include a detailed health check endpoint for in-the-field status checks 

Template for initializing new petals in HEAR_CLI 

 

hear-cli local_machine run_program --p petal_init 

 

Leaf SDK Petal (v0.1.5) 

Upgraded trajectory polynomial coefficient generation to avoid possible ‘ringing’ and use burst MAVLink messages for better communication reliability 

Business Value 

Address lack of robustness in LeafSDK functionalities carried over mavlink. 

🐞 Bug Fixes 

N/A 

 

Known Limitations 

LeafSDK does the trajectory sampling which results in jitter. The trajectory sampling needs to be done from the LeafFC side. 

MAVLink communication over the mavlink-router lacks reliability. Redis is suggested as a reliable and efficient alternative for Petals <---> LeafFC communication. 


===============

Petal App Manager first stable release v0.1.5 (2025-07-03)

Business Value 

Where to find the feature/how to interact with the feature 

https://pypi.org/project/petal-app-manager/ 

It can be setup in development mode using HEAR_CLI 

It can be setup on a target machine in production mode using HEAR_CLI 

 

Demo link (when relevant) 

 

Flight Log Petal (v0.1.1) 

Business Value 

Features 

Added ability to cancel downloads from the Pixhawk to avoid interrupting mavlink connection 

Where to find the feature/how to interact with the feature: https://github.com/DroneLeaf/petal-flight-log 

 

Demo link (when relevant) 

 

Leaf SDK Petal (v0.1.0) 

Business Value 

Leaf SDK petal application makes mission planning library easily integratable with other external and DroneLeaf applications such as Warehouse Management Petal. I will also allow us to deploy LeafSDK Mission Planner easily and smoothly in our ecosystem. 

Where to find the feature/how to interact with the feature: https://github.com/DroneLeaf/petal-leafsdk 

 

Demo link (when relevant) 

 

Warehouse Management Petal (v0.1.0) 

Business Value 

This petal is responsible is responsible of publishing the real-time drone using MAVLink over websocket that is received and visualized by Blender. 

Where to find the feature/how to interact with the feature: https://github.com/DroneLeaf/petal-warehouse 

 

Demo link (when relevant) 


=================

Petal App Manager passed initial testing v0.1.0 (2025-06-22)

Business Value 

The Petal App Manager will speed up development and reduce cost by abstracting away a lot of the low-level code related to managing Mavlink connections, writing the Local DynamoDB database, Redis Caches, communicating with cloud infrastructure, and working with ROS1 topics 

Where to find the feature/how to interact with the feature 

PyPi: https://pypi.org/project/petal-app-manager/ 

GitHub: https://github.com/DroneLeaf/petal-app-manager.git 

Demo: 

Part 1: demo petal-app-manager-20250620_073657-Meeting Recording.mp4 

Part 2: demo petal-app-manager-20250620_074319-Meeting Recording.mp4 

 