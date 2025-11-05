The Petal App Manager Service
==============================

Admin Dashboard Interface
--------------------------

Petal App Manager includes a comprehensive web-based admin dashboard for managing petals, proxies, and monitoring system logs in real-time.

Accessing the Admin Dashboard
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Primary Admin Dashboard:**

http://localhost:9000/admin-dashboard

This provides a complete graphical interface with the following features:

**1. System Status Overview**

- Current configuration display
- Enabled petals and proxies
- Dependency relationships
- Restart status monitoring

**2. Real-time Component Management**

- **Proxy Controls**: Enable/disable proxies with visual status indicators
- **Petal Controls**: Enable/disable petals with dependency validation
- **All Components View**: Complete overview of all available components (enabled/disabled)
- **Automatic Dependency Validation**: Prevents invalid configurations

**3. Real-time Log Streaming**

- Live application logs with WebSocket connection
- Log level filtering (Debug, Info, Warning, Error, Critical)
- Recent log loading
- Connection status indicator
- Auto-scrolling log display

**4. Quick Actions**

- Refresh status and component lists
- Apply configuration changes
- Clear logs
- Load recent historical logs

Dashboard Features
~~~~~~~~~~~~~~~~~~

**Visual Status Indicators:**

- ✅ **Green**: Component enabled and healthy
- ❌ **Red**: Component disabled or unhealthy
- 🔄 **Refresh buttons**: Update component status
- 📋 **All Components**: View complete system inventory

**Proxy Management:**

Each proxy shows:

- Current status (enabled/disabled)
- Dependencies and dependents
- Toggle controls with dependency validation
- Real-time status updates

**Petal Management:**

Each petal displays:

- Current enabled/disabled state
- Required proxy dependencies
- Toggle controls with automatic validation
- Dependency conflict prevention

**Live Log Monitoring:**

- **Connection Status**: Visual indicator (Connected/Disconnected)
- **Log Filtering**: Filter by log level in real-time
- **Auto-scroll**: Automatically scroll to newest entries
- **Historical Logs**: Load recent log entries on demand
- **Clear Function**: Clear log display when needed

Using the Admin Dashboard
~~~~~~~~~~~~~~~~~~~~~~~~~

**1. Monitor System Status:**

- Visit http://localhost:9000/admin-dashboard
- Click **"Refresh Status"** to load current configuration
- View enabled petals and proxies in the status section

**2. Enable/Disable Components:**

- Use the **Proxy Controls** section to manage backend services
- Use the **Petal Controls** section to manage application modules
- Click individual toggle buttons to enable/disable components
- Changes are applied automatically with dependency validation

**3. View All Components:**

- Click **"All Components"** to see complete system inventory
- View both enabled and disabled components
- Understand dependency relationships
- See component usage statistics

**4. Monitor Logs in Real-time:**

- Use the **Real-time Application Logs** section
- Click **"Connect"** to start live log streaming
- Filter logs by level using the dropdown
- Click **"Load Recent"** for historical log entries
- Use **"Clear"** to reset the log display

**5. Handle Configuration Changes:**

- The dashboard shows if restart is required
- Apply changes are handled automatically
- Monitor restart status through the interface

Alternative Access Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Interactive API Documentation:**

1. **Swagger UI**: http://localhost:9000/docs
2. **ReDoc**: http://localhost:9000/redoc

These provide form-based API interaction for:

- Testing endpoints manually
- Understanding API request/response formats
- Experimenting with configurations
- API documentation reference

Managing Petals and Proxies via API
------------------------------------

For programmatic access or scripting, you can use the REST API directly:

Checking What's Running
~~~~~~~~~~~~~~~~~~~~~~~

To see which petals and proxies are currently enabled and their status:

**API Endpoint:**

.. code-block:: bash

   curl http://localhost:9000/api/petal-proxies-control/status

**Response:**

.. code-block:: json

   {
     "enabled_proxies": ["redis", "ext_mavlink", "db", "cloud"],
     "enabled_petals": ["petal_warehouse", "mission_planner", "flight_records"],
     "petal_dependencies": {
       "petal_warehouse": ["redis", "ext_mavlink"],
       "mission_planner": ["redis", "ext_mavlink"],
       "flight_records": ["redis", "cloud"]
     },
     "restart_required": false
   }

**Health Check:**

.. code-block:: bash

   curl http://localhost:9000/health/detailed

This shows the operational status of all enabled components.

Viewing All Available Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To see all petals and proxies (enabled and disabled):

.. code-block:: bash

   curl http://localhost:9000/api/petal-proxies-control/components/list

**Response:**

.. code-block:: json

   {
     "petals": [
       {
         "name": "flight_records",
         "enabled": true,
         "dependencies": ["redis", "cloud"]
       },
       {
         "name": "petal_warehouse", 
         "enabled": true,
         "dependencies": ["redis", "ext_mavlink"]
       }
     ],
     "proxies": [
       {
         "name": "redis",
         "enabled": true,
         "dependencies": [],
         "dependents": ["petal:flight_records", "petal:petal_warehouse"]
       },
       {
         "name": "cloud",
         "enabled": false,
         "dependencies": [],
         "dependents": ["petal:flight_records"]
       }
     ]
   }

Petal Control via API
---------------------

Enabling Petals
~~~~~~~~~~~~~~~~

.. code-block:: bash

   curl -X POST "http://localhost:9000/api/petal-proxies-control/petals/control" \
        -H "Content-Type: application/json" \
        -d '{
          "petals": ["flight_records"],
          "action": "ON"
        }'

Disabling Petals
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   curl -X POST "http://localhost:9000/api/petal-proxies-control/petals/control" \
        -H "Content-Type: application/json" \
        -d '{
          "petals": ["petal_warehouse"],
          "action": "OFF"
        }'

Proxy Control via API
----------------------

Enabling Proxies
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   curl -X POST "http://localhost:9000/api/petal-proxies-control/proxies/control" \
        -H "Content-Type: application/json" \
        -d '{
          "petals": ["cloud", "ext_mavlink"],
          "action": "ON"
        }'

Disabling Proxies
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   curl -X POST "http://localhost:9000/api/petal-proxies-control/proxies/control" \
        -H "Content-Type: application/json" \
        -d '{
          "petals": ["cloud"],
          "action": "OFF"
        }'

.. note::
   The API validates dependencies automatically. You cannot enable a petal without its required proxies, 
   or disable a proxy that other components depend on.

Common Use Cases
----------------

**Lightweight Setup** (Redis only):

**Via Admin Dashboard:**

1. Go to http://localhost:9000/admin-dashboard
2. Use **Proxy Controls** to disable unnecessary proxies
3. Use **Petal Controls** to disable dependent petals
4. Monitor changes in the **System Status** section

**Via API:**

1. Go to Swagger UI: http://localhost:9000/docs
2. Disable unnecessary proxies via ``/proxies/control``
3. Disable dependent petals via ``/petals/control``
4. Restart if needed via ``/restart``

**MAVLink Development:**

**Via Admin Dashboard:**

1. Enable ``ext_mavlink`` proxy using toggle controls
2. Enable MAVLink-dependent petals (``petal_warehouse``, ``mission_planner``)
3. Monitor system status and logs for connectivity

**Via API:**

1. Enable ``ext_mavlink`` proxy
2. Enable MAVLink-dependent petals (``petal_warehouse``, ``mission_planner``)
3. Monitor health via ``/health/detailed``

**Cloud Integration:**

**Via Admin Dashboard:**

1. Enable ``cloud`` proxy using the dashboard controls
2. Enable cloud-dependent petals (``flight_records``)
3. Monitor real-time logs for cloud connectivity status

**Via API:**

1. Enable ``cloud`` proxy
2. Enable cloud-dependent petals (``flight_records``)
3. Verify connectivity through health endpoints

Restart Management
------------------

Configuration changes require a restart to take effect on actual petal/proxy loading.

**Check Restart Status:**

.. code-block:: bash

   curl http://localhost:9000/api/petal-proxies-control/restart-status

**Trigger Restart:**

.. code-block:: bash

   curl -X POST "http://localhost:9000/api/petal-proxies-control/restart"

.. tip::
   **Development Mode**: If running with ``uvicorn --reload``, the server restarts automatically.
   
   **Production Mode**: Manual restart may be required depending on your deployment setup.

Service Files and Locations
----------------------------

**Development Setup:**

- Configuration: ``~/petal-app-manager-dev/petal-app-manager/proxies.yaml``
- Logs: ``~/petal-app-manager-dev/petal-app-manager/app.log``
- Admin Dashboard: http://localhost:9000/admin-dashboard

**Production Setup:**

- Installation: ``~/.droneleaf/petal-app-manager/``
- Configuration: ``~/.droneleaf/petal-app-manager/proxies.yaml``
- Logs: ``~/.droneleaf/petal-app-manager/app.log``
- Service: ``systemctl status petal-app-manager``
- Admin Dashboard: http://localhost:9000/admin-dashboard

**Service Management (Production):**

.. code-block:: bash

   # Check service status
   sudo systemctl status petal-app-manager
   
   # Start/stop service
   sudo systemctl start petal-app-manager
   sudo systemctl stop petal-app-manager
   
   # View service logs
   sudo journalctl -u petal-app-manager -f
