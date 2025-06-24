
## Developing Petals

### Petal Architecture

Petals are pluggable components that:

- Inherit from the `Petal` base class
- Use decorators (`@http_action`, `@websocket_action`) to define endpoints
- Are discovered and loaded automatically through Python entry points
- Have access to all registered proxies

### Available Decorators

- `@http_action(method="GET|POST", path="/endpoint")`: Define HTTP endpoints
- `@websocket_action(path="/ws/endpoint")`: Define WebSocket endpoints
- `@mqtt_action(topic="topic/name")`: Define MQTT handlers (planned)

### Example: petal-hello-world

The [`petal-hello-world`](https://github.com/DroneLeaf/petal-hello-world.git) demonstrates a basic skeleton that you can clone and modify to quickly get started with petal development

> [!WARNING]
> Remember to change the origin when pushing to GitHub
> ```bash
> git remote set-url origin https://github.com/DroneLeaf/your-petal-name.git
> ```

### Example: petal-flight-log

The [`petal-flight-log`](https://github.com/DroneLeaf/petal-flight-log.git) demonstrates a comprehensive petal implementation:

- Downloads and manages flight logs from a PX4 drone
- Provides HTTP endpoints for retrieving and storing flight records
- Uses WebSockets for real-time download progress updates
- Interacts with multiple proxies (MAVLink, Redis, LocalDB)

Key endpoints include:

- `GET /flight-records:` Retrieve all flight records
- `POST /save-record:` Save a new flight record
- `GET /available-px4-ulogs:` List available ULog files from PX4
- `GET /download-ulog-pixhawk:` Download a ULog file from Pixhawk
- `GET /get-px4-time:` Get PX4 system time

### Creating a New Petal (Hello World)

1. Create a new Python package with this structure

    ```bash
    # Create a new directory for your petal
    mkdir petal-hello-world
    cd petal-hello-world

    # Initialize a PDM project
    pdm init
    # Answer the prompts:

    # Creating a pyproject.toml for PDM...
    # Please enter the Python interpreter to use (any python version >= 3.8 should suffice)
    # Project name (petal-hello-world): 
    # Project version (0.1.0): 
    # Do you want to build this project for distribution(such as wheel)?
    # If yes, it will be installed by default when running `pdm install`. [y/n] (n)# : y (very important)
    # Project description (): 
    # Which build backend to use? (0. pdm-backend)
    # License(SPDX name) (MIT): or any license you want 
    # Author name (Khalil Al Handawi): 
    # Author email (khalil.alhandawi@mail.mcgill.ca): 
    # Python requires('*' to allow any) (>=3.xx): hit Enter

    # Create the initial files
    touch src/petal_hello_world/__init__.py
    cat > src/petal-hello-world/__init__.py <<'PY'
    import logging

    logger = logging.getLogger(__name__)
    PY

    touch src/petal_hello_world/plugin.py

    # Add petal-app-manager as a dependency
    pdm add petal-app-manager
    ```

    Now your project structure should look like:

    ```bash
    my-petal/
    ├── pyproject.toml
    └── src/
        └── petal_hello_world/
            ├── __init__.py
            └── plugin.py
    ```

2. Define your petal in `plugin.py`

    ```python
    from . import logger

    from petal_app_manager.plugins.base import Petal
    from petal_app_manager.plugins.decorators import http_action, websocket_action
    from petal_app_manager.proxies.redis import RedisProxy
    from petal_app_manager.proxies.localdb import LocalDBProxy
    from petal_app_manager.proxies.external import MavLinkExternalProxy

    from pymavlink import mavutil, mavftp
    from pymavlink.dialects.v10 import common
    import asyncio

    import time

    class PetalHelloWorld(Petal):
        name = "petal-hello-world"
        version = "1.0.0"
        
        @http_action(
            method="GET", 
            path="/hello", 
            description="Returns a Hello World message and stores it in Redis"
        )
        async def hello_world(self):
            # Access proxies through self._proxies
            redis_proxy: RedisProxy = self._proxies["redis"]
            localdb_proxy: LocalDBProxy = self._proxies["db"]
            mavlink_proxy: MavLinkExternalProxy = self._proxies["ext_mavlink"]

            # Create and send a GPS_RAW_INT message
            logger.info("Sending GPS_RAW_INT message...")

            try:
                mav = common.MAVLink(None)
                gps_msg = mav.gps_raw_int_encode(
                    time_usec=int(time.time() * 1e6),
                    fix_type=3,  # 3D fix
                    lat=int(45.5017 * 1e7),  # Montreal latitude
                    lon=int(-73.5673 * 1e7),  # Montreal longitude
                    alt=50 * 1000,  # Altitude in mm (50m)
                    eph=100,  # GPS HDOP
                    epv=100,  # GPS VDOP
                    vel=0,  # Ground speed in cm/s
                    cog=0,  # Course over ground
                    satellites_visible=10,  # Number of satellites
                )
                
                # Send the message
                mavlink_proxy.send("mav", gps_msg)
            except Exception as e:
                logger.error(f"Failed to send GPS_RAW_INT message: {e}")
                return {"error": "Failed to send GPS message"}
            
            # Wait a bit for the message to be sent
            await asyncio.sleep(0.5)

            try:
                await redis_proxy.set("hello", "world")
            except Exception as e:
                logger.error(f"Failed to store message in Redis: {e}")
                return {"error": "Failed to store message in Redis"}

            logger.info("Hello World message sent and stored in Redis.")
            return {"message": "Hello World!"}

    ```

3. Register your petal in your petal's `pyproject.toml`

    ```toml
    [project.entry-points."petal.plugins"]
    hello_world = "petal_hello_world.plugin:PetalHelloWorld"
    ```

4. (Optional) For integrated development mode with `petal-app-manager`, add a reference to your local clone of `petal-app-manager` in you petal's `pyproject.toml`:

    First clone `petal-app-manager` if you have not done so already

    ```bash
    cd .. # if in `my-petal` directory
    git clone https://github.com/DroneLeaf/petal-app-manager.git
    git clone --recurse-submodules https://github.com/DroneLeaf/leaf-mavlink.git mavlink
    ```

    Next add `petal-app-manager` and `leaf-pymavlink` to your petal's dev dependancies

    ```toml
    [dependency-groups]
    dev = [
        "pytest-cov>=6.2.1",
        "-e file:///${PROJECT_ROOT}/../mavlink/pymavlink/#egg=leaf-pymavlink",
        "-e file:///${PROJECT_ROOT}/../petal-app-manager/#egg=petal-app-manager",
    ]
    ```

    This enables your petal's intellisense to pick up changes that you make to `petal-app-manager` and/or `leaf-pymavlink`

> [!TIP]
> You may use relative paths for your `petal-app-manager`
> ```toml
> local = [
>     "-e file:///${PROJECT_ROOT}/../petal-app-manager/#egg=petal-app-manager",
> ]
> ```

5. Install your petal in development mode

    ```bash
    pdm install -G dev
    ```

6. Debugging your petal

    You may use the provided debug launch configuration in [.vscode/launch.json](.vscode/launch.json) to debug your petal. It will launch the `petal-app-manager` and will stop at breakpoints you set within your `plugin.py` file