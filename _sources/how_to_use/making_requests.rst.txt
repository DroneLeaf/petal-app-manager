Making Requests
===============

Using the Postman Collection
-----------------------------

Petal App Manager includes a comprehensive Postman collection with pre-configured requests for all petals and proxies.

**Files Included:**

- ``PetalAppManager.postman_collection.json`` - Complete API collection
- ``local_petal-app-manager.postman_environment.json`` - Environment variables

**Setup:**

1. **Import Collection:**
   
   - Open Postman
   - Click **Import** → **Upload Files**
   - Select ``PetalAppManager.postman_collection.json``

2. **Import Environment:**
   
   - Import ``local_petal-app-manager.postman_environment.json``
   - Set as active environment (top-right dropdown)

3. **Environment Variables:**

   .. code-block:: json

      {
        "API_URL": "http://localhost:9000",
        "org_id": "e8fc2cd9-f040-4229-84c0-62ea693b99f6",
        "device_id": "Instance-a92c5505-ccdb-4ac7-b0fe-74f4fa5fc5b9"
      }

**Collection Structure:**

- **petal-leafsdk** - Mission planning and execution
- **petal-flight-log** - Flight log management and downloads
- **petal-warehouse** - Data warehousing operations
- **petal-user-journey-coordinator** - User journey management
- **Cloud** - Cloud data operations
- **bucket** - S3 bucket operations
- **mqtt** - MQTT client operations
- **mavftp** - MAVLink file transfer

**Quick Test:**

1. Select **Health Check** request
2. Click **Send**
3. Verify response: ``{"status": "ok"}``

Using the /docs Interface
--------------------------

Accessing Swagger UI
~~~~~~~~~~~~~~~~~~~~

**Primary Interface:**

http://localhost:9000/docs

**Features:**

- Interactive API documentation
- Built-in request testing
- Real-time response validation
- Automatic request formatting

Interactive API Testing
~~~~~~~~~~~~~~~~~~~~~~~

**1. Basic Health Check:**

- Navigate to **default** section
- Click **GET /health**
- Click **"Try it out"** → **"Execute"**
- View response: ``{"status": "ok"}``

**2. Detailed Health Check:**

- Find **GET /health/detailed**
- Click **"Try it out"** → **"Execute"**
- View detailed proxy status and petal information

**3. Petal Requests:**

- Expand **petal sections** (e.g., **petal-flight-log**)
- Select an endpoint (e.g., **GET /petals/flight-log-petal/flight-records**)
- Click **"Try it out"** → **"Execute"**
- View petal-specific responses

**4. Admin Controls:**

- Navigate to **petal-proxies-control** section
- Test **GET /api/petal-proxies-control/status**
- Use **POST** endpoints to enable/disable components

**5. Request Body Examples:**

For POST requests with JSON bodies:

.. code-block:: json

   {
     "petals": ["flight_records"],
     "action": "ON"
   }

Using ReDoc
-----------

**Alternative Documentation:**

http://localhost:9000/redoc

**Benefits:**

- Clean, readable API documentation
- Better for reference and understanding
- Hierarchical organization
- Detailed schema descriptions

**Use Cases:**

- Understanding API structure
- Reading detailed endpoint descriptions
- Viewing request/response schemas
- API reference during development

Example API Calls
-----------------

**Health Check:**

.. code-block:: bash

   curl http://localhost:9000/health

**Detailed Health:**

.. code-block:: bash

   curl http://localhost:9000/health/detailed

**System Status:**

.. code-block:: bash

   curl http://localhost:9000/api/petal-proxies-control/status

**Enable Petal:**

.. code-block:: bash

   curl -X POST "http://localhost:9000/api/petal-proxies-control/petals/control" \
        -H "Content-Type: application/json" \
        -d '{"petals": ["flight_records"], "action": "ON"}'

**Flight Records:**

.. code-block:: bash

   curl http://localhost:9000/petals/flight-log-petal/flight-records

**Mission Planning:**

.. code-block:: bash

   curl -X POST "http://localhost:9000/petals/petal-mission-planner/mission/plan" \
        -H "Content-Type: application/json" \
        -d '{"mission_data": "example"}'

**Cloud Operations:**

.. code-block:: bash

   curl -X POST "http://localhost:9000/cloud/scan-table" \
        -H "Content-Type: application/json" \
        -d '{"table_name": "example"}'

Quick Testing Workflow
-----------------------

**1. Verify System:**

.. code-block:: bash

   # Basic health
   curl http://localhost:9000/health
   
   # Detailed status
   curl http://localhost:9000/health/detailed

**2. Check Configuration:**

.. code-block:: bash

   # Current config
   curl http://localhost:9000/api/petal-proxies-control/status
   
   # All components
   curl http://localhost:9000/api/petal-proxies-control/components/list

**3. Test Petal Endpoints:**

.. code-block:: bash

   # Flight records
   curl http://localhost:9000/petals/flight-log-petal/flight-records
   
   # Available logs
   curl http://localhost:9000/petals/flight-log-petal/available-ulogs

**4. Use Interactive Interface:**

- Visit http://localhost:9000/docs for graphical testing
- Use http://localhost:9000/admin-dashboard for system management

.. tip::
   **Best Practice**: Start with the Admin Dashboard (http://localhost:9000/admin-dashboard) to understand system status, then use Swagger UI (http://localhost:9000/docs) for detailed API testing.
