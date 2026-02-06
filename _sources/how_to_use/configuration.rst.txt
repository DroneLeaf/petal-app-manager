Configuration Changes in .env
=============================

Environment Variables Overview
------------------------------

Petal App Manager uses a ``.env`` file to configure all system settings. This file is located in:

- **Development**: ``~/petal-app-manager-dev/petal-app-manager/.env``
- **Production**: ``~/.droneleaf/petal-app-manager/.env``

.. note::
   All environment variables use the ``PETAL_`` prefix to avoid conflicts with other applications.

Edit the file with any text editor and restart the application to apply changes.

General Configuration
---------------------

PETAL_LOG_LEVEL
~~~~~~~~~~~~~~~

Controls application logging verbosity.

.. code-block:: bash

   PETAL_LOG_LEVEL=INFO

**Options**: ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, ``CRITICAL``

- ``DEBUG``: Detailed information for troubleshooting
- ``INFO``: General operational messages (recommended for production)
- ``WARNING``: Warning messages only
- ``ERROR``: Error messages only

PETAL_LOG_TO_FILE
~~~~~~~~~~~~~~~~~

Enables logging to file.

.. code-block:: bash

   PETAL_LOG_TO_FILE=true

**Options**: ``true``, ``false``

PETAL_LOG_DIR
~~~~~~~~~~~~~

Directory for log files.

.. code-block:: bash

   PETAL_LOG_DIR=logs

**Default Values**:

- **Development**: ``logs`` (relative to project directory)
- **Production**: ``/home/droneleaf/.droneleaf/petal-app-manager``

MAVLink Configuration
---------------------

PETAL_MAVLINK_ENDPOINT
~~~~~~~~~~~~~~~~~~~~~~

MAVLink connection endpoint for drone communication.

.. code-block:: bash

   PETAL_MAVLINK_ENDPOINT=udp:127.0.0.1:14551

**Format**: ``udp:HOST:PORT`` or ``serial:/dev/ttyUSB0:BAUD``

**Common Values**:

- ``udp:127.0.0.1:14551`` - Local SITL simulator
- ``udp:192.168.1.100:14551`` - Remote drone IP
- ``serial:/dev/ttyUSB0:57600`` - Serial connection

PETAL_MAVLINK_BAUD
~~~~~~~~~~~~~~~~~~

Baud rate for serial MAVLink connections.

.. code-block:: bash

   PETAL_MAVLINK_BAUD=115200

**Common Values**: ``57600``, ``115200``, ``921600``

Other MAVLink Settings
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   PETAL_MAVLINK_MAXLEN=200                    # Maximum message length
   PETAL_MAVLINK_WORKER_SLEEP_MS=1             # Worker thread sleep (milliseconds)
   PETAL_MAVLINK_WORKER_THREADS=4              # Number of worker threads
   PETAL_MAVLINK_HEARTBEAT_SEND_FREQUENCY=5.0  # Heartbeat frequency (Hz)
   PETAL_ROOT_SD_PATH=fs/microsd/log           # Log storage path on drone

Cloud Configuration
-------------------

DroneLeaf cloud service integration settings.

.. code-block:: bash

   PETAL_ACCESS_TOKEN_URL=http://localhost:3001/session-manager/access-token
   PETAL_SESSION_TOKEN_URL=http://localhost:3001/session-manager/session-token
   PETAL_S3_BUCKET_NAME=devhube21f2631b51e4fa69c771b1e8107b21cb431a-dev
   PETAL_CLOUD_ENDPOINT=https://api.droneleaf.io

**PETAL_ACCESS_TOKEN_URL**: Authentication token endpoint
**PETAL_SESSION_TOKEN_URL**: Session management endpoint  
**PETAL_S3_BUCKET_NAME**: AWS S3 bucket for data storage
**PETAL_CLOUD_ENDPOINT**: Main DroneLeaf API endpoint

Redis Configuration
-------------------

PETAL_REDIS_HOST and PETAL_REDIS_PORT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Redis server connection details.

.. code-block:: bash

   PETAL_REDIS_HOST=localhost
   PETAL_REDIS_PORT=6379
   PETAL_REDIS_DB=0

**Standard Values**: ``localhost:6379`` for local Redis

PETAL_REDIS_UNIX_SOCKET_PATH
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

UNIX socket path for Redis (preferred method).

.. code-block:: bash

   PETAL_REDIS_UNIX_SOCKET_PATH=/var/run/redis/redis-server.sock

**Benefits**: Better performance than TCP, more secure

PETAL_REDIS_HEALTH_MESSAGE_RATE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Health check message frequency for Redis monitoring.

.. code-block:: bash

   PETAL_REDIS_HEALTH_MESSAGE_RATE=3.0

**Value**: Messages per second (Hz)

Database Configuration
----------------------

Local database settings for petal storage.

.. code-block:: bash

   PETAL_LOCAL_DB_HOST=localhost
   PETAL_LOCAL_DB_PORT=3000

**Purpose**: Local data storage and caching

Data Operations URLs
--------------------

API endpoints for drone data operations.

.. code-block:: bash

   PETAL_GET_DATA_URL=/drone/onBoard/config/getData
   PETAL_SCAN_DATA_URL=/drone/onBoard/config/scanData
   PETAL_UPDATE_DATA_URL=/drone/onBoard/config/updateData
   PETAL_SET_DATA_URL=/drone/onBoard/config/setData

**Purpose**: Define API paths for drone configuration management

MQTT Configuration
------------------

Message queue settings for real-time communication.

.. code-block:: bash

   PETAL_TS_CLIENT_HOST=localhost
   PETAL_TS_CLIENT_PORT=3004
   PETAL_CALLBACK_HOST=localhost
   PETAL_CALLBACK_PORT=3005
   PETAL_POLL_INTERVAL=1.0
   PETAL_ENABLE_CALLBACKS=true
   PETAL_MQTT_HEALTH_CHECK_INTERVAL=10.0

**PETAL_TS_CLIENT_HOST/PORT**: Time series client connection
**PETAL_CALLBACK_HOST/PORT**: Callback service endpoint
**PETAL_POLL_INTERVAL**: Polling frequency (seconds)
**PETAL_ENABLE_CALLBACKS**: Enable/disable callback functionality

Proxy Connection Retry Configuration
------------------------------------

Settings for proxy connection retry behavior.

.. code-block:: bash

   PETAL_MQTT_RETRY_INTERVAL=10.0
   PETAL_CLOUD_RETRY_INTERVAL=10.0
   PETAL_MQTT_STARTUP_TIMEOUT=5.0
   PETAL_CLOUD_STARTUP_TIMEOUT=5.0
   PETAL_MQTT_SUBSCRIBE_TIMEOUT=5.0

**PETAL_MQTT_RETRY_INTERVAL**: MQTT monitoring task retry interval (seconds)
**PETAL_CLOUD_RETRY_INTERVAL**: Cloud proxy retry interval (seconds)
**PETAL_MQTT_STARTUP_TIMEOUT**: MQTT startup timeout (seconds)
**PETAL_CLOUD_STARTUP_TIMEOUT**: Cloud token fetch timeout (seconds)
**PETAL_MQTT_SUBSCRIBE_TIMEOUT**: Topic subscription timeout (seconds)

Petal-Specific Configuration
----------------------------

Individual petal settings.

.. code-block:: bash

   PETAL_DEBUG_SQUARE_TEST=false    # Petal User Journey Coordinator debug mode

Applying Configuration Changes
------------------------------

**1. Edit the .env file:**

.. code-block:: bash

   # Development
   nano ~/petal-app-manager-dev/petal-app-manager/.env
   
   # Production
   nano ~/.droneleaf/petal-app-manager/.env

**2. Restart the application:**

**Development:**

.. code-block:: bash

   # If running manually, stop with Ctrl+C and restart
   uvicorn petal_app_manager.main:app --reload --port 9000

**Production:**

.. code-block:: bash

   sudo systemctl restart petal-app-manager

**3. Verify changes:**

.. code-block:: bash

   # Check logs for configuration loading
   curl http://localhost:9000/health/detailed

Configuration Examples
----------------------

**SITL Development Setup:**

.. code-block:: bash

   PETAL_LOG_LEVEL=DEBUG
   PETAL_MAVLINK_ENDPOINT=udp:127.0.0.1:14551
   PETAL_CLOUD_ENDPOINT=https://api.droneleaf.io

**Production Drone Setup:**

.. code-block:: bash

   PETAL_LOG_LEVEL=INFO
   PETAL_MAVLINK_ENDPOINT=serial:/dev/ttyUSB0:57600
   PETAL_CLOUD_ENDPOINT=https://api.droneleaf.io

**Lightweight Local Testing:**

.. code-block:: bash

   PETAL_LOG_LEVEL=DEBUG
   PETAL_MAVLINK_ENDPOINT=udp:127.0.0.1:14551
   PETAL_ENABLE_CALLBACKS=false

.. tip::
   **Configuration Validation**: Use the Admin Dashboard at http://localhost:80/home/petals-proxies-control or http://localhost:9000/admin-dashboard to monitor configuration status and verify that all services are connecting properly after changes.
