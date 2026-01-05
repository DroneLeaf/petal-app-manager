Quick Start Guide
=================

.. important::
   **Recommended Installation Methods**
   
   Use HEAR-CLI for automated installation - it handles all dependencies and configuration automatically:
   
   - **Development/Local Setup**: ``hear-cli local_machine run_program --p petal_app_manager_prepare_sitl``
   - **Production/Drone Deployment**: ``hear-cli target_machine copy_run_program --p petal_app_manager_prepare_arm``
   - **Production/Drone Testing and Development**: ``hear-cli target_machine copy_run_program --p petal_app_manager_update_arm``

Development Installation
------------------------

Using HEAR-CLI (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For local development and debugging, use the SITL (Software In The Loop) setup:

.. code-block:: bash

   hear-cli local_machine run_program --p petal_app_manager_prepare_sitl

**What this command does:**

1. **Installs all dependencies**: Python 3.11 (Miniforge), PDM, Redis 7.2+
2. **Creates development directory**: ``~/petal-app-manager-dev/``
3. **Clones all repositories**:
   
   - ``petal-app-manager`` (main framework)
   - ``LeafSDK`` (mission planning SDK)
   - ``mavlink`` (MAVLink protocol with custom messages)
   - ``petal-flight-log`` (flight log management)
   - ``petal-leafsdk`` (LeafSDK integration for mission plan execution)
   - ``petal-qgc-mission-server`` (QGroundControl integration)
   - ``petal-user-journey-coordinator`` (user journey management)
   - ``petal-warehouse`` (data warehousing)

4. **Configures development environment**: Sets up PDM virtual environments for each component
5. **Creates ``.env`` file**: Pre-configured for development use
6. **Installs development dependencies**: All petals in editable mode

.. note::
   The SITL setup creates a complete development environment with all petals linked for cross-development.

Development Directory Structure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The development setup creates the following repository structure with editable installations:

.. graphviz::
   :caption: Development Repository Structure and Dependencies

   digraph dev_structure {
       rankdir=LR;
       node [shape=folder, style=filled];
       
       // Main development directory
       dev_root [label="~/petal-app-manager-dev/", fillcolor=lightyellow, shape=box];
       
       // Repositories
       pam [label="petal-app-manager/\n(Main Framework)", fillcolor=lightblue];
       leafsdk [label="LeafSDK/\n(Mission SDK)", fillcolor=lightgreen];
       mavlink [label="mavlink/\n(Protocol)", fillcolor=orange];
       pymavlink [label="mavlink/pymavlink/\n(Python Library)", fillcolor=orange];
       
       // Petals
       flight_log [label="petal-flight-log/\n(Flight Logs)", fillcolor=palegreen];
       warehouse [label="petal-warehouse/\n(Data Warehouse)", fillcolor=palegreen];
       leafsdk_petal [label="petal-leafsdk/\n(SDK Integration)", fillcolor=palegreen];
       journey [label="petal-user-journey-coordinator/\n(Mission Coord)", fillcolor=palegreen];
       qgc [label="petal-qgc-mission-server/\n(QGC Server)", fillcolor=palegreen];
       
       // Directory structure
       dev_root -> pam;
       dev_root -> leafsdk;
       dev_root -> mavlink;
       dev_root -> flight_log;
       dev_root -> warehouse;
       dev_root -> leafsdk_petal;
       dev_root -> journey;
       dev_root -> qgc;
       
       mavlink -> pymavlink [label="contains", style=dotted];
       
       // Editable installations (development dependencies)
       pam -> flight_log [label="editable\ninstall", color=blue, style=bold];
       pam -> warehouse [label="editable\ninstall", color=blue, style=bold];
       pam -> leafsdk_petal [label="editable\ninstall", color=blue, style=bold];
       pam -> journey [label="editable\ninstall", color=blue, style=bold];
       pam -> leafsdk [label="editable\ninstall", color=blue, style=bold];
       pam -> pymavlink [label="file://\ninstall", color=red, style=bold];
       
       // Legend
       subgraph cluster_legend {
           label="Legend";
           style=filled;
           color=lightgray;
           rankdir=TB;
           
           leg_edit_a [label="", shape=point, width=0];
           leg_edit_b [label="editable install (changes reflect immediately)", shape=plaintext];
           
           leg_file_a [label="", shape=point, width=0];
           leg_file_b [label="file:// install (requires rebuild)", shape=plaintext];
           
           leg_contains_a [label="", shape=point, width=0];
           leg_contains_b [label="contains", shape=plaintext];
           
           leg_edit_a -> leg_edit_b [color=blue, style=bold, arrowhead=vee];
           leg_file_a -> leg_file_b [color=red, style=bold, arrowhead=vee];
           leg_contains_a -> leg_contains_b [style=dotted, arrowhead=vee];
       }
   }

**Key Structure Points:**

- **Main Framework** (``petal-app-manager``): Central application that loads all petals
- **Editable Installations**: Changes to petal code are immediately reflected without reinstallation
- **pymavlink**: Installed via ``file://`` path (not editable) from the mavlink submodule. You must rebuild if changes are made using ``pdm install -G dev --force-rebuild pymavlink``.
- **Independent Petals**: Each petal has its own virtual environment for isolated testing

**Typical File Locations:**

.. code-block:: text

   ~/petal-app-manager-dev/
   ├── LeafSDK/
   │   ├── src/leafsdk/          # SDK source code
   │   └── tests/                # SDK tests
   ├── mavlink/
   │   ├── pymavlink/            # Python MAVLink library
   │   │   ├── generator/        # Message generator
   │   │   └── dialects/         # MAVLink dialects
   │   ├── message_definitions/  # Python MAVLink library
   │   │   └── v1.0/             # Message definitions (.xml)
   ├── petal-app-manager/
   │   ├── src/petal_app_manager/
   │   │   ├── api/              # REST API endpoints
   │   │   ├── plugins/          # Petal loader
   │   │   └── proxies/          # Backend proxies
   │   ├── docs/                 # This documentation
   │   └── tests/                # Framework tests
   ├── petal-flight-log/
   │   ├── src/petal_flight_log/ # Flight log handling
   │   └── tests/
   ├── petal-warehouse/
   │   ├── src/petal_warehouse/  # Data warehousing
   │   └── tests/
   ├── petal-leafsdk/
   │   ├── src/petal_leafsdk/    # Mission execution
   │   └── tests/
   ├── petal-user-journey-coordinator/
   │   ├── src/petal_user_journey_coordinator/
   │   └── tests/
   └── petal-qgc-mission-server/
       ├── src/petal_qgc_mission_server/
       └── tests/

Manual Development Setup
~~~~~~~~~~~~~~~~~~~~~~~~

If you need to set up manually (requires dependencies from previous section):

**1. Create Development Directory**

.. code-block:: bash

   mkdir -p ~/petal-app-manager-dev
   cd ~/petal-app-manager-dev

**2. Clone Repositories**

.. code-block:: bash

   # Core framework
   git clone https://github.com/DroneLeaf/petal-app-manager.git
   git clone https://github.com/DroneLeaf/LeafSDK.git
   git clone --recurse-submodules https://github.com/DroneLeaf/leaf-mavlink.git mavlink
   
   # Petals
   git clone https://github.com/DroneLeaf/petal-flight-log.git
   git clone https://github.com/DroneLeaf/petal-leafsdk.git
   git clone https://github.com/DroneLeaf/petal-qgc-mission-server.git
   git clone https://github.com/DroneLeaf/petal-user-journey-coordinator.git
   git clone https://github.com/DroneLeaf/petal-warehouse.git

**3. Set Up Main Application**

.. code-block:: bash

   cd petal-app-manager
   
   # Configure PDM to use Python 3.11
   pdm use -f /usr/bin/python3.11
   
   # Install development dependencies (includes all petals in editable mode)
   pdm install -G dev

Production Installation
-----------------------

Using HEAR-CLI (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For deployment to drone companion computers or production systems:

.. code-block:: bash

   hear-cli target_machine copy_run_program --p petal_app_manager_prepare_arm

**What this command does:**

1. **Installs system dependencies**: Python 3.11 (pyenv), PDM, Redis 7.2+
2. **Sets up production environment**: ``~/.droneleaf/petal-app-manager/``
3. **Configures for production**: Optimized for resource-constrained systems
4. **Installs only production petals**: Core functionality without development tools
5. **Creates systemd service**: Auto-start on boot
6. **Configures ``.env`` file**: Production-ready configuration

.. warning::
   This command is designed for deployment to target machines (companion computers on drones).
   It requires HEAR-CLI to be configured with target machine credentials.

Custom Version Installation (Field Testing)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For testing specific combinations of Petal App Manager and petals on drones without creating formal releases:

.. code-block:: bash

   hear-cli target_machine copy_run_program --p petal_app_manager_update_arm

**Interactive Version Selection**

This command prompts you to specify versions for each component, allowing flexible combinations for field testing:

.. code-block:: console

   droneleaf@ubuntu:~/HEAR_CLI$ hear-cli target_machine copy_run_program --p petal_app_manager_update_arm
   Enter petal-app-manager version 😎 (v0.1.41): v0.1.42
   Enter petal-flight-log version 😎 (v0.1.6): master
   Enter petal-warehouse version 😎 (v0.1.7): dev
   Enter petal-leafsdk version 😎 (v0.2.0): 
   Enter petal-user-journey-coordinator version 😎 (v0.1.2): 
   ⭐ program will run in your target_machine, Are you sure? 😎 [y/n] (y):

**Version Specification Options**

- **Git Tags**: ``v0.1.42``, ``v0.2.0`` (stable releases)
- **Branch Names**: ``master``, ``dev``, ``feature/new-functionality`` (development versions)
- **Commit SHA**: ``abc123ef`` (specific commits)
- **Empty/Default**: Press Enter to use the default version shown in parentheses

**Use Cases for Custom Versions**

1. **Feature Testing**: Deploy a development branch of a specific petal while keeping others stable
2. **Bug Fixes**: Test a hotfix branch before creating an official release
3. **Integration Testing**: Combine multiple development branches for comprehensive testing
4. **Rollback Testing**: Test with older versions to isolate issues

**What this command does:**

1. **Prompts for each component version**: Interactive selection for precise control
2. **Downloads specified versions**: Clones exact git references (tags/branches/commits)
3. **Updates existing installation**: Replaces current versions without full reinstall
4. **Preserves configuration**: Keeps existing ``.env`` and ``proxies.yaml`` files
5. **Restarts services**: Automatically restarts Petal App Manager with new versions

.. tip::
   **Development Workflow**: Use this command to test your development branches on actual hardware 
   before merging to main or creating releases. It's perfect for validating changes in real-world conditions.

.. note::
   This command requires HEAR-CLI to be configured with credentials for the target drone/companion computer.

Manual Production Installation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For manual production setup:

**1. Create Production Directory**

.. code-block:: bash

   sudo mkdir -p ~/.droneleaf
   sudo chmod -R 777 ~/.droneleaf
   cd ~/.droneleaf

**2. Clone Main Repository**

.. code-block:: bash

   git clone https://github.com/DroneLeaf/petal-app-manager.git
   cd petal-app-manager

**3. Install Production Dependencies**

.. code-block:: bash

   # Configure PDM
   pdm use -f /usr/bin/python3.11
   
   # Install production dependencies only
   pdm install -G prod

Environment Configuration
-------------------------

The ``.env`` file contains all configuration for Petal App Manager:

**Automatic Configuration**

Both HEAR-CLI methods automatically create a ``.env`` file. For manual setups, create:

.. note::
   All environment variables use the ``PETAL_`` prefix to avoid conflicts with other applications.

.. code-block:: bash

   cat > .env << 'EOF'
   # .env file for Petal App Manager configuration
   # General configuration
   PETAL_LOG_LEVEL=INFO
   PETAL_LOG_TO_FILE=true
   PETAL_LOG_DIR=logs
   # MAVLink configuration
   PETAL_MAVLINK_ENDPOINT=udp:127.0.0.1:14551
   PETAL_MAVLINK_BAUD=115200
   PETAL_MAVLINK_MAXLEN=200
   PETAL_MAVLINK_WORKER_SLEEP_MS=1
   PETAL_MAVLINK_WORKER_THREADS=4
   PETAL_MAVLINK_HEARTBEAT_SEND_FREQUENCY=5.0
   PETAL_ROOT_SD_PATH=fs/microsd/log
   # Cloud configuration
   PETAL_ACCESS_TOKEN_URL=http://localhost:3001/session-manager/access-token
   PETAL_SESSION_TOKEN_URL=http://localhost:3001/session-manager/session-token
   PETAL_S3_BUCKET_NAME=devhube21f2631b51e4fa69c771b1e8107b21cb431a-dev
   PETAL_CLOUD_ENDPOINT=https://api.droneleaf.io
   # Local database configuration
   PETAL_LOCAL_DB_HOST=localhost
   PETAL_LOCAL_DB_PORT=3000
   # Redis configuration
   PETAL_REDIS_HOST=localhost
   PETAL_REDIS_PORT=6379
   PETAL_REDIS_DB=0
   PETAL_REDIS_UNIX_SOCKET_PATH=/var/run/redis/redis-server.sock
   PETAL_REDIS_HEALTH_MESSAGE_RATE=3.0
   # Data operations URLs
   PETAL_GET_DATA_URL=/drone/onBoard/config/getData
   PETAL_SCAN_DATA_URL=/drone/onBoard/config/scanData
   PETAL_UPDATE_DATA_URL=/drone/onBoard/config/updateData
   PETAL_SET_DATA_URL=/drone/onBoard/config/setData
   # MQTT client
   PETAL_TS_CLIENT_HOST=localhost
   PETAL_TS_CLIENT_PORT=3004
   PETAL_CALLBACK_HOST=localhost
   PETAL_CALLBACK_PORT=3005
   PETAL_POLL_INTERVAL=1.0
   PETAL_ENABLE_CALLBACKS=true
   PETAL_MQTT_HEALTH_CHECK_INTERVAL=10.0
   # Proxy connection retry configuration
   PETAL_MQTT_RETRY_INTERVAL=10.0
   PETAL_CLOUD_RETRY_INTERVAL=10.0
   PETAL_MQTT_STARTUP_TIMEOUT=5.0
   PETAL_CLOUD_STARTUP_TIMEOUT=5.0
   PETAL_MQTT_SUBSCRIBE_TIMEOUT=5.0
   # Petal User Journey Coordinator configuration
   PETAL_DEBUG_SQUARE_TEST=false
   EOF

**Key Configuration Options**

- ``PETAL_LOG_LEVEL``: Set to ``DEBUG`` for development, ``INFO`` for production
- ``PETAL_LOG_DIR``: Directory for log files (default: ``logs``, production: ``/home/droneleaf/.droneleaf/petal-app-manager``)
- ``PETAL_MAVLINK_ENDPOINT``: UDP endpoint for MAVLink communication
- ``PETAL_REDIS_UNIX_SOCKET_PATH``: Path to Redis UNIX socket
- ``PETAL_CLOUD_ENDPOINT``: DroneLeaf cloud API endpoint

Running the Application
-----------------------

**Development Mode**

.. code-block:: bash

   cd ~/petal-app-manager-dev/petal-app-manager
   
   # Activate PDM virtual environment
   source .venv/bin/activate
   
   # Run with auto-reload for development
   uvicorn petal_app_manager.main:app --reload --port 9000

**Development Mode with Debugging (VSCode)**

A VSCode launch configuration is provided for debugging with breakpoint support:

.. code-block:: bash

   # Location: ~/petal-app-manager-dev/petal-app-manager/.vscode/launch.json

To use the debugger:

1. Open the project in VSCode: ``code ~/petal-app-manager-dev/petal-app-manager``
2. Press ``F5`` or go to **Run and Debug** panel (Ctrl+Shift+D)
3. Select **"Petal App Manager"** from the launch configuration dropdown
4. Click the green play button or press ``F5``

The application will start with the debugger attached, allowing you to:

- Set breakpoints in your code
- Inspect variables and call stacks
- Step through code execution
- Hot-reload on file changes (``--reload`` flag is enabled)

.. tip::
   **Debugging Petals**: Since petals are installed in editable mode, you can also set breakpoints 
   in petal code (e.g., ``~/petal-app-manager-dev/petal-flight-log/src/petal_flight_log/``). 
   To debug a petal, open the petal files in the ``petal-app-manager`` workspace in VSCode 
   (they are linked via editable installation), then set breakpoints and run the debugger. 
   Changes to petal code will be reflected immediately due to editable installation.

**Production Mode**

.. code-block:: bash

   cd ~/.droneleaf/petal-app-manager
   
   # Activate PDM virtual environment
   source .venv/bin/activate
   
   # Run in production mode
   uvicorn petal_app_manager.main:app --port 9000

**Background Service (Production)**

The ARM installation script sets up a systemd service for automatic startup:

.. code-block:: bash

   # Check service status
   sudo systemctl status petal-app-manager
   
   # Start/stop service
   sudo systemctl start petal-app-manager
   sudo systemctl stop petal-app-manager
   
   # Enable/disable auto-start
   sudo systemctl enable petal-app-manager
   sudo systemctl disable petal-app-manager

Verifying the Installation
--------------------------

**1. Check Application Health**

.. code-block:: bash

   # Test basic connectivity
   curl http://localhost:9000/health
   
   # Expected response:
   # {"status": "ok"}

**2. Access API Documentation**

Open your browser and navigate to:

- **Swagger UI**: http://localhost:9000/docs
- **ReDoc**: http://localhost:9000/redoc

**3. Check Proxy Status**

.. code-block:: bash

   # Test detailed connectivity
   curl http://localhost:9000/health/detailed
   
.. code-block:: json

    // Expected response:
    {
        "status": "healthy", 
        "timestamp": "..."
        "proxies": {
            "redis": {
                "status": "healthy",
            },
            "mavlink": {
                "status": "healthy",
            },
            
        }
    }


**4. Test Redis Connection**

.. code-block:: bash

   # Direct Redis test
   redis-cli -s /var/run/redis/redis-server.sock ping
   # Should return: PONG

**5. Check Logs**

.. code-block:: bash

   # View application logs (if logging to file is enabled)
   tail -f app.log
   
   # Or check individual component logs
   ls -la app-*.log

**6. Verify Petals Loading**

.. code-block:: bash

   # Check available petals
   curl http://localhost:9000/petals/
   
   # Expected: List of loaded petals

Quick Development Workflow
---------------------------

Once installed, here's the typical development workflow:

.. code-block:: bash

   # 1. Navigate to development directory
   cd ~/petal-app-manager-dev/petal-app-manager
   
   # 2. Activate environment
   source .venv/bin/activate
   
   # 3. Start application with auto-reload
   uvicorn petal_app_manager.main:app --reload --port 9000
   
   # 4. In another terminal, start documentation auto-build
   cd docs
   sphinx-autobuild . _build/html
   
   # 5. Open browser tabs:
   # - http://localhost:9000/docs (API documentation)
   # - http://127.0.0.1:8000 (documentation preview)

.. tip::
   **VSCode Integration**: The development setup includes a ``.vscode/launch.json`` configuration.
   Press F5 in VSCode to start debugging with breakpoint support.

Troubleshooting
---------------

**Common Issues After Installation**

1. **Python 3.11 not found**: Ensure symlinks were created and PATH is updated
2. **PDM command not found**: Check that ``~/.local/bin`` is in your PATH
3. **Redis connection failed**: Verify Redis service is running and socket permissions are correct
4. **Port 9000 already in use**: This may occur if you're trying to run Petal App Manager using ``uvicorn`` while the systemd service is currently running. For debugging, you may want to stop the service first with ``sudo systemctl stop petal-app-manager``. Alternatively, kill the conflicting process. You may use the command ``sudo lsof -i :9000`` to identify the process using the port.
5. **Application errors or unexpected behavior**: Check the ``app.log`` file in the ``petal-app-manager`` directory (``~/petal-app-manager-dev/petal-app-manager/app.log`` or ``~/.droneleaf/petal-app-manager/app.log``) for detailed error messages and stack traces that can help troubleshoot issues.

**Getting Help**

- Check the :doc:`../known_issues` section for common problems
- View application logs for detailed error messages
- Ensure all dependencies are properly installed from the previous section
