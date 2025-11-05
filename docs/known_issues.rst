Known Issues
============

Petal Issues
------------

.. _petal-naming-convention:

Petal Name Must Start with "petal-*"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**

- Petal loads but logging doesn't work properly
- Log messages don't appear in expected log files
- Petal functionality seems degraded or incomplete
- Logger instances return incorrect or missing information

**Cause:**

The Petal App Manager framework expects all petals to follow the ``petal-*`` naming convention (kebab-case). Internal systems rely on this naming pattern for proper initialization, logging configuration, and other core functionality.

**Solutions:**

1. **Rename your petal to follow the convention:**

   ❌ **Incorrect names:**
   
   - ``example-petal``
   - ``telemetry``
   - ``my-plugin``
   
   ✅ **Correct names:**
   
   - ``petal-example``
   - ``petal-telemetry``
   - ``petal-my-plugin``

2. **Update all references:**

    .. code-block:: toml

        # pyproject.toml
        [project]
        name = "petal-example"  # Must start with petal-
        
        [project.entry-points."petal.plugins"]
        petal_example = "petal_example.plugin:PetalExample"

3. **Reinstall the petal:**

    .. code-block:: bash

        cd ~/petal-app-manager-dev/petal-app-manager
        pdm remove old-name
        pdm add -e ../petal-example --group dev

.. _petal-not-loading:

Petal Not Getting Loaded
~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**

- Petal doesn't appear in ``/health/detailed`` endpoint
- Endpoints defined in your petal return 404
- No log messages from your petal during startup
- ``curl http://localhost:9000/your-petal/health`` returns 404

**Cause:**

The most common cause is that the petal is not registered in the ``proxies.yaml`` configuration file. Petal App Manager only loads petals that are explicitly enabled in this file.

**Solutions:**

1. **Check if petal is registered in proxies.yaml:**

    .. code-block:: bash

        cd ~/petal-app-manager-dev/petal-app-manager
        # or for production: cd ~/.droneleaf/petal-app-manager
        cat proxies.yaml

2. **Add your petal to enabled_petals:**

    .. code-block:: yaml

        enabled_petals:
        - flight_records
        - petal_warehouse
        - mission_planner
        - petal_user_journey_coordinator
        - petal_example  # Add your petal here (use entry point name)

3. **Verify entry point name matches:**

   The name in ``enabled_petals`` must match the entry point key in your ``pyproject.toml``:
   
    .. code-block:: toml

        [project.entry-points."petal.plugins"]
        petal_example = "petal_example.plugin:PetalExample"
        # ^^^^^^^^^^^^
        # This name goes in proxies.yaml

4. **Ensure required proxies are enabled:**

   Check that all proxies listed in your petal's ``get_required_proxies()`` are enabled:
   
    .. code-block:: yaml

        enabled_proxies:
        - redis  # If your petal requires redis
        - ext_mavlink
        - db
        
        petal_dependencies:
        petal_example:
        - redis  # List the same proxies here

5. **Verify petal is installed:**

    .. code-block:: bash

        pdm list | grep petal-example

6. **Restart Petal App Manager:**

    .. code-block:: bash

        # If running manually
        # Stop with Ctrl+C and restart
        uvicorn petal_app_manager.main:app --reload --port 9000
        
        # If running as a service
        sudo systemctl restart petal-app-manager

Python 3.11 Issues
------------------

Python 3.11 Not Found
~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**

- ``python3.11: command not found``
- PDM fails with "No Python interpreter found"
- Installation scripts fail at Python detection step

**Solutions:**

1. **Verify Python 3.11 installation:**

    .. code-block:: bash

        which python3.11
        python3.11 --version

2. **Check symlinks:**

    .. code-block:: bash

        ls -la /usr/bin/python3.11
        ls -la /usr/local/bin/python3.11

3. **Recreate symlinks if missing:**

    .. code-block:: bash

        sudo ln -sf /home/$USER/miniforge3/bin/python3.11 /usr/bin/python3.11
        sudo ln -sf /home/$USER/miniforge3/bin/python3.11 /usr/local/bin/python3.11

4. **If any of the above fails, Rerun HEAR_CLI command:**

    .. code-block:: bash

        hear-cli local_machine run_program --p petal_app_manager_prepare_arm

    or for x86_64:

    .. code-block:: bash

        hear-cli local_machine run_program --p petal_app_manager_prepare_sitl


PDM Issues
----------

PDM Installation Fails
~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**

- ``pdm: command not found``
- PDM installation script completes but command not available
- Permission errors during PDM installation

**Solutions:**

1. **Verify PDM installation:**

    .. code-block:: bash

        which pdm
        pdm --version

2. **Rerun HEAR_CLI command:**

    .. code-block:: bash

        hear-cli local_machine run_program --p petal_app_manager_prepare_arm

    or for x86_64:

    .. code-block:: bash

        hear-cli local_machine run_program --p petal_app_manager_prepare_sitl

PDM Lock File Issues
~~~~~~~~~~~~~~~~~~~~

**Symptoms:**

- ``pdm install`` fails with lock file errors
- Dependency resolution takes very long
- Version conflicts during installation

**Solutions:**

1. **Update lock file:**

    .. code-block:: bash

        pdm lock --update-reuse

2. **Clear cache and reinstall:**

    .. code-block:: bash

        pdm cache clear
        rm -f pdm.lock
        pdm install

Redis Issues
------------

Redis Connection Errors
~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**

- ``Connection refused`` errors
- ``redis.exceptions.ConnectionError``
- Petal App Manager health check shows Redis as unhealthy

**Solutions:**

1. **Check if Redis is running:**

    .. code-block:: bash

        sudo systemctl status redis-server

2. **Start Redis if not running:**

    .. code-block:: bash

        sudo systemctl start redis-server
        sudo systemctl enable redis-server

3. **Verify socket permissions:**

    .. code-block:: bash

        ls -la /var/run/redis/redis-server.sock

4. **Fix socket permissions if needed:**

    .. code-block:: bash

        sudo chmod 777 /var/run/redis/redis-server.sock

Redis Configuration Issues
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**

- Redis starts but Petal App Manager can't connect via UNIX socket
- ``No such file or directory`` for socket path
- Permission denied on socket

**Solutions:**

1. **Verify UNIX socket is enabled in Redis config:**

    .. code-block:: bash

        grep unixsocket /etc/redis/redis.conf

2. **Expected configuration:**

    .. code-block:: text

        unixsocket /var/run/redis/redis-server.sock
        unixsocketperm 777

3. **Update configuration and restart:**

    .. code-block:: bash

        sudo nano /etc/redis/redis.conf
        sudo systemctl restart redis-server

4. **Test socket connection:**

    .. code-block:: bash

        redis-cli -s /var/run/redis/redis-server.sock ping
        # Should return: PONG

5. **If any of the above fails, Rerun HEAR_CLI command:**

    .. code-block:: bash

        hear-cli local_machine run_program --p petal_app_manager_prepare_arm

    or for x86_64:

    .. code-block:: bash

        hear-cli local_machine run_program --p petal_app_manager_prepare_sitl


MAVLink Issues
--------------

MAVLink Connection Issues
~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**

- ``ext_mavlink`` proxy shows as unhealthy
- No telemetry data received
- MAVLink endpoints timeout

**Solutions:**

1. **Verify MAVLink endpoint configuration:**

    .. code-block:: bash

        grep MAVLINK_ENDPOINT .env

2. **Ensure correct endpoint set in mavlink master configuration:**

    .. code-block:: bash

        cat /etc/mavlink-router/main.conf

    Ensure the following ``UdpEndpoint`` is set correctly

    .. code-block:: bash

        [UdpEndpoint droneleaf]

        Mode = Normal

        Address = 127.0.0.1

        Port = 14551

3. **Check if simulation/drone is running:**

    For SITL:

    .. code-block:: bash

        # Check if SITL simulator is running
        ps aux | grep px4

    Launch SITL if not running:

    .. code-block:: bash

        cd ~/software-stack/PX4-Autopilot
        make px4_sitl gazebo-classic

4. **Test UDP connection:**

    .. code-block:: bash

        # Listen on MAVLink port
        nc -ul 14551

5. **Verify pymavlink installation:**

    .. code-block:: bash

        pdm list | grep pymavlink

Port Conflicts
--------------

Port 9000 Already in Use
~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**

- ``Address already in use`` error when starting Petal App Manager
- Cannot start uvicorn server
- Application fails to bind to port

**Cause:**

This typically occurs when trying to run Petal App Manager using ``uvicorn`` while the systemd service is already running, or when another process is using port 9000.

**Solutions:**

1. **Check what's using port 9000:**

    .. code-block:: bash

        sudo lsof -i :9000

2. **Stop the systemd service (if running):**

    .. code-block:: bash

        sudo systemctl stop petal-app-manager
        sudo systemctl status petal-app-manager

3. **Kill the conflicting process:**

    .. code-block:: bash

        # Find the process ID (PID) from lsof output
        sudo kill <PID>

Reporting Issues
----------------

If you encounter issues not covered here:

**GitHub Issues**

Report bugs and request features at:

- Petal App Manager: https://github.com/DroneLeaf/petal-app-manager/issues
- Individual petals: Check respective repository issue trackers

**Include in Your Report**

1. **Environment information:**

    .. code-block:: bash

        python3.11 --version
        pdm --version
        redis-server --version

2. **Log files:**

    .. code-block:: bash

        # Application logs
        tail -100 app.log
        
        # System logs
        sudo journalctl -u petal-app-manager -n 100

3. **Configuration:**

    .. code-block:: bash

        # Sanitize sensitive data before sharing
        cat proxies.yaml
        cat .env | grep -v TOKEN | grep -v PASSWORD

4. **Steps to reproduce the issue**

5. **Expected vs actual behavior**

**Getting Help**

- Check :doc:`getting_started/quickstart` for setup guidance
- Review :doc:`development_contribution/adding_petals` for petal development
- See :doc:`development_contribution/contribution_guidelines` for version management
