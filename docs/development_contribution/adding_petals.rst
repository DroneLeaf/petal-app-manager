Adding a New Petal Guide
========================

What is a Petal?
----------------

A **Petal** is a pluggable module in the Petal App Manager ecosystem that extends the framework's functionality. Petals are self-contained components that can:

- Expose HTTP endpoints via FastAPI
- Provide WebSocket endpoints for real-time communication
- Access backend services through proxies (Redis, MAVLink, Database, etc.)
- Declare their dependencies on proxies
- Be loaded/unloaded dynamically

Petals follow a standardized structure and use Python's entry point system for automatic discovery.

Creating a New Petal
--------------------

Using HEAR-CLI (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The fastest way to create a new petal is using the HEAR-CLI initialization script:

.. code-block:: bash

   hear-cli local_machine run_program --p petal_init

This will interactively guide you through creating a new petal with:

- Standard directory structure
- Entry point configuration in ``pyproject.toml``
- Health endpoint that reports proxy requirements
- Basic test structure
- VS Code debugging configuration

**Example Session:**

.. code-block:: console

   $ hear-cli local_machine run_program --p petal_init
   Enter petal name (e.g., petal-telemetry): petal-telemetry
   Enter target directory [current directory]: ~/petal-app-manager-dev
   🚀 Initializing petal 'petal-telemetry' in ~/petal-app-manager-dev/petal-telemetry
   ✅ Petal created successfully!

Manual Setup
~~~~~~~~~~~~

If you prefer to create a petal manually, follow these steps:

**1. Create Directory Structure**

.. code-block:: bash

   mkdir -p petal-example/{src/petal_example,tests,.vscode}
   cd petal-example

.. important::
   **Naming Convention**: Petal names **must** start with ``petal-*`` (kebab-case).
   The Python module name uses underscores: ``petal_example``.
   
   See :ref:`petal-naming-issues` for troubleshooting if your petal isn't working.

**2. Create pyproject.toml**

.. code-block:: toml

   [project]
   name = "petal-example"
   version = "0.1.0"
   description = "An example petal for the DroneLeaf ecosystem"
   authors = [
       {name = "Your Name", email = "your.email@example.com"},
   ]
   dependencies = []
   requires-python = ">=3.10"
   readme = "README.md"
   license = {text = "MIT"}

   [build-system]
   requires = ["pdm-backend"]
   build-backend = "pdm.backend"

   [tool.pdm]
   distribution = true

   # ⚠️ CRITICAL: Entry point for petal discovery
   [project.entry-points."petal.plugins"]
   petal_example = "petal_example.plugin:PetalExample"

   [dependency-groups]
   dev = [
       "pytest>=8.4.0",
       "pytest-asyncio>=1.0.0",
       "anyio>=4.9.0",
       "pytest-cov>=6.2.1",
       "-e file:///${PROJECT_ROOT}/../petal-app-manager/#egg=petal-app-manager",
       "-e file:///${PROJECT_ROOT}/../mavlink/pymavlink/#egg=leaf-pymavlink",
   ]

The entry point ``[project.entry-points."petal.plugins"]`` is how Petal App Manager discovers your petal.

**3. Create src/petal_example/__init__.py**

This file handles version detection:

.. code-block:: python

   """
   petal-example - A DroneLeaf Petal
   ==================================

   This petal provides example functionality for the DroneLeaf ecosystem.
   """

   import logging
   from importlib.metadata import PackageNotFoundError, version as _pkg_version

   logger = logging.getLogger(__name__)

   try:
       # ⚠️ Use the *distribution* name from pyproject.toml
       __version__ = _pkg_version("petal-example")
   except PackageNotFoundError:
       # Fallback during local development before install
       __version__ = "0.0.0"

**4. Create src/petal_example/plugin.py**

This is the main petal implementation:

.. code-block:: python

   """
   Main plugin module for petal-example
   """

   import logging
   from typing import Dict, Any, List
   from datetime import datetime

   from . import logger
   from petal_app_manager.plugins.base import Petal
   from petal_app_manager.plugins.decorators import http_action, websocket_action
   from petal_app_manager.proxies.redis import RedisProxy
   from petal_app_manager.proxies.localdb import LocalDBProxy
   from petal_app_manager.proxies.external import MavLinkExternalProxy


   class PetalExample(Petal):
       """
       Main petal class for petal-example.
       """
       
       name = "petal-example"
       version = "0.1.0"
       
       def __init__(self):
           super().__init__()
           self._startup_time = None
           
       def startup(self) -> None:
           """Called when the petal is started."""
           super().startup()
           self._startup_time = datetime.now()
           logger.info(f"{self.name} petal started successfully")
           
       def shutdown(self) -> None:
           """Called when the petal is stopped."""
           super().shutdown()
           logger.info(f"{self.name} petal shut down")
       
       def get_required_proxies(self) -> List[str]:
           """
           Return list of proxy names that this petal requires.
           
           Available proxies: 'redis', 'db', 'ext_mavlink', 'cloud', 'bucket', 'mqtt'
           """
           return ["redis"]
       
       def get_optional_proxies(self) -> List[str]:
           """Return list of proxy names that this petal can optionally use."""
           return ["ext_mavlink"]
       
       @http_action(
           method="GET",
           path="/health",
           description="Health check endpoint"
       )
       async def health_check(self):
           """Health check endpoint."""
           return {
               "petal": self.name,
               "version": self.version,
               "status": "healthy",
               "required_proxies": self.get_required_proxies(),
               "optional_proxies": self.get_optional_proxies()
           }
       
       @http_action(
           method="GET",
           path="/hello",
           description="Simple hello world endpoint"
       )
       async def hello_world(self):
           """Simple hello world endpoint."""
           return {
               "message": "Hello from petal-example!",
               "timestamp": datetime.now().isoformat()
           }

Petal Structure
~~~~~~~~~~~~~~~

A properly structured petal follows this layout:

.. code-block:: text

   petal-example/
   ├── src/
   │   └── petal_example/
   │       ├── __init__.py          # Version detection
   │       └── plugin.py             # Main petal implementation
   ├── tests/
   │   ├── __init__.py
   │   └── test_petal_example.py    # Unit tests
   ├── .vscode/
   │   └── launch.json               # VS Code debug config
   ├── pyproject.toml                # Project metadata & entry point
   ├── README.md                     # Documentation
   └── .gitignore

Key Components
~~~~~~~~~~~~~~

**Entry Point (pyproject.toml)**

The entry point tells Petal App Manager where to find your petal:

.. code-block:: toml

   [project.entry-points."petal.plugins"]
   petal_example = "petal_example.plugin:PetalExample"

Format: ``<module_name> = "<package>.<module>:<ClassName>"``

**Plugin Class (plugin.py)**

Must inherit from ``Petal`` base class and can override:

- ``startup()`` - Called when petal starts
- ``shutdown()`` - Called when petal stops
- ``get_required_proxies()`` - List of required proxy names
- ``get_optional_proxies()`` - List of optional proxy names

**Decorators**

Use decorators to expose endpoints:

- ``@http_action`` - HTTP endpoint (GET, POST, PUT, DELETE, etc.)
- ``@websocket_action`` - WebSocket endpoint

Registering the Petal
---------------------

After creating your petal, you must register it in the Petal App Manager configuration.

Adding to proxies.yaml
~~~~~~~~~~~~~~~~~~~~~~

Edit ``~/petal-app-manager-dev/petal-app-manager/proxies.yaml`` (or ``~/.droneleaf/petal-app-manager/proxies.yaml`` for production):

.. code-block:: yaml

   enabled_petals:
   - flight_records
   - petal_warehouse
   - mission_planner
   - petal_user_journey_coordinator
   - petal_example  # Add your petal here

   enabled_proxies:
   - mqtt
   - db
   - ext_mavlink
   - redis
   - cloud
   - bucket

   petal_dependencies:
     flight_records:
     - redis
     - cloud
     mission_planner:
     - redis
     - ext_mavlink
     petal_warehouse:
     - redis
     - ext_mavlink
     petal_user_journey_coordinator:
     - mqtt
     - ext_mavlink
     petal_example:  # Add your petal's dependencies
     - redis

.. warning::
   **Critical**: If your petal is not loading, check that it's registered in ``proxies.yaml``.
   See :ref:`petal-not-loading-guide` for troubleshooting.

**Petal Name Mapping**

The name in ``enabled_petals`` should match your entry point name in ``pyproject.toml``:

- Entry point: ``petal_example = "petal_example.plugin:PetalExample"``
- proxies.yaml: ``petal_example`` (uses the entry point key, not the class name)

Adding to pyproject.toml (for Production)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For production deployment, add your petal to Petal App Manager's ``pyproject.toml``:

.. code-block:: toml

   [dependency-groups]
   prod = [
       "petal-flight-log @ git+https://github.com/DroneLeaf/petal-flight-log.git@v0.1.6",
       "petal-warehouse @ git+https://github.com/DroneLeaf/petal-warehouse.git@v0.1.7",
       "petal-example @ git+https://github.com/YourOrg/petal-example.git@v0.1.0",
   ]

This ensures your petal is installed when deploying to production.

Installing Your Petal
---------------------

Development Installation (Editable)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For local development with live code changes:

.. code-block:: bash

   cd ~/petal-app-manager-dev/petal-app-manager
   
   # Install your petal in editable mode
   pdm add -e ../petal-example --group dev
   
   # Verify installation
   pdm list | grep petal-example

Production Installation (Git Tag)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For production deployment:

.. code-block:: bash

   cd ~/.droneleaf/petal-app-manager
   
   # Install from git tag
   pdm add "petal-example @ git+https://github.com/YourOrg/petal-example.git@v0.1.0" --group prod

Testing Your Petal
------------------

Unit Tests
~~~~~~~~~~

Create tests in ``tests/test_petal_example.py``:

.. code-block:: python

   """
   Tests for petal-example
   """

   import pytest
   from petal_example.plugin import PetalExample


   class TestPetalExample:
       """Test suite for petal-example."""
       
       def setup_method(self):
           """Setup test fixtures."""
           self.petal = PetalExample()
           
       def test_petal_initialization(self):
           """Test that petal initializes correctly."""
           assert self.petal.name == "petal-example"
           assert self.petal.version == "0.1.0"
           
       def test_required_proxies(self):
           """Test that required proxies are declared."""
           required = self.petal.get_required_proxies()
           assert "redis" in required
           
       @pytest.mark.asyncio
       async def test_health_check_endpoint(self):
           """Test the health check endpoint."""
           response = await self.petal.health_check()
           assert response["petal"] == "petal-example"
           assert response["status"] == "healthy"

Run tests with:

.. code-block:: bash

   cd ~/petal-app-manager-dev/petal-example
   pdm run pytest
   
   # With coverage
   pdm run pytest --cov=src --cov-report=html

Integration Testing
~~~~~~~~~~~~~~~~~~~

Test your petal with Petal App Manager:

.. code-block:: bash

   # Start Petal App Manager in development mode
   cd ~/petal-app-manager-dev/petal-app-manager
   source .venv/bin/activate
   uvicorn petal_app_manager.main:app --reload --port 9000
   
   # In another terminal, test your endpoints
   curl http://localhost:9000/petal-example/health
   curl http://localhost:9000/petal-example/hello

Debugging
~~~~~~~~~

Use VS Code debugging with the provided launch configuration:

1. Open your petal directory in VS Code
2. Set breakpoints in ``plugin.py``
3. Press ``F5`` to start debugging
4. Your petal runs within the Petal App Manager context

Best Practices
--------------

Naming Conventions
~~~~~~~~~~~~~~~~~~

- **Distribution name**: ``petal-example`` (kebab-case) in ``pyproject.toml``
- **Module name**: ``petal_example`` (snake_case) for Python imports
- **Class name**: ``PetalExample`` (PascalCase) for the plugin class
- **Entry point key**: ``petal_example`` (snake_case) matches module name

Proxy Management
~~~~~~~~~~~~~~~~

- Declare all required proxies in ``get_required_proxies()``
- Declare optional proxies in ``get_optional_proxies()``
- Always check proxy availability before use
- Handle proxy failures gracefully

Error Handling
~~~~~~~~~~~~~~

.. code-block:: python

   @http_action(method="GET", path="/data")
   async def get_data(self):
       """Get data from Redis."""
       try:
           redis_proxy: RedisProxy = self.get_proxy("redis")
           data = await redis_proxy.get("my_key")
           return {"data": data}
       except Exception as e:
           logger.error(f"Failed to get data: {e}")
           return {"error": str(e)}, 500

Logging
~~~~~~~

Use the logger from your ``__init__.py``:

.. code-block:: python

   from . import logger
   
   logger.info("Petal started")
   logger.warning("Something might be wrong")
   logger.error("An error occurred")
   logger.debug("Debug information")

Versioning
~~~~~~~~~~

- Use semantic versioning: ``MAJOR.MINOR.PATCH``
- Update version in ``pyproject.toml``
- Create git tags for releases: ``v0.1.0``
- Follow the :doc:`contribution_guidelines` for release process

Documentation
~~~~~~~~~~~~~

- Document all endpoints with clear descriptions
- Provide examples in your README
- Document proxy requirements
- Include setup and installation instructions

Common Pitfalls
---------------

.. _petal-naming-issues:

Petal Name Must Start with ``petal-*``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your petal name doesn't follow the ``petal-*`` naming convention, logging and other functionality may not work properly. Always use:

- ✅ ``petal-example``
- ✅ ``petal-telemetry``
- ❌ ``example-petal``
- ❌ ``telemetry``

.. _petal-not-loading-guide:

Petal Not Loading
~~~~~~~~~~~~~~~~~

If your petal isn't loading, check:

1. **Is it registered in proxies.yaml?**
   
   .. code-block:: yaml
   
      enabled_petals:
      - your_petal_name  # Must be here!

2. **Does the entry point name match?**
   
   The name in ``proxies.yaml`` must match the entry point key in ``pyproject.toml``.

3. **Are all required proxies enabled?**
   
   Check that proxies listed in ``get_required_proxies()`` are in ``enabled_proxies``.

4. **Is the petal installed?**
   
   .. code-block:: bash
   
      pdm list | grep petal-example

Entry Point Errors
~~~~~~~~~~~~~~~~~~~

If you get "No module named..." errors, verify:

- Entry point syntax in ``pyproject.toml`` is correct
- Module path matches your directory structure
- Petal is installed (``pdm install`` or ``pdm add -e``)

Next Steps
----------

- Review existing petals for examples: ``petal-flight-log``, ``petal-warehouse``
- Read the :doc:`contribution_guidelines` for release workflow
- Explore the :doc:`../api_reference/index` for available proxies and utilities
- Check :doc:`../known_issues` for troubleshooting
