
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

### Example: FlightLogPetal

The [`FlightLogPetal`](https://github.com/DroneLeaf/petal-flight-log.git) demonstrates a comprehensive petal implementation:

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
    mkdir my-petal
    cd my-petal

    # Initialize a PDM project
    pdm init
    # Answer the prompts:

    # Creating a pyproject.toml for PDM...
    # Please enter the Python interpreter to use (any python version >= 3.8 should suffice)
    # Project name (my-petal): 
    # Project version (0.1.0): 
    # Do you want to build this project for distribution(such as wheel)?
    # If yes, it will be installed by default when running `pdm install`. [y/n] (n)# : y (very important)
    # Project description (): 
    # Which build backend to use? (0. pdm-backend)
    # License(SPDX name) (MIT): or any license you want 
    # Author name (Khalil Al Handawi): 
    # Author email (khalil.alhandawi@mail.mcgill.ca): 
    # Python requires('*' to allow any) (>=3.xx): hit Enter

    # Create the source directory structure
    mkdir -p src/my_petal

    # Create the initial files
    touch src/my_petal/__init__.py
    touch src/my_petal/plugin.py

    # Add petal-app-manager as a dependency
    pdm add petal-app-manager
    ```

    Now your project structure should look like:

    ```bash
    my-petal/
    ├── pyproject.toml
    └── src/
        └── my_petal/
            ├── __init__.py
            └── plugin.py
    ```

2. Define your petal in `plugin.py`

    ```python
    from petal_app_manager.plugins.base import Petal
    from petal_app_manager.plugins.decorators import http_action, websocket_action
    from petal_app_manager.proxies.redis import RedisProxy

    class MyPetal(Petal):
        name = "my-petal"
        version = "1.0.0"
        
        @http_action(method="GET", path="/hello")
        async def hello_world(self):
            # Access proxies through self._proxies
            redis_proxy: RedisProxy = self._proxies["redis"]
            await redis_proxy.set("hello", "world")
            return {"message": "Hello World!"}
    ```

3. Register your petal in your petal's `pyproject.toml`

    ```toml
    [project.entry-points."petal.plugins"]
    my_petal = "my_petal.plugin:MyPetal"
    ```

4. (Optional) For integrated development mode with `petal-app-manager`, add a reference to your local clone of `petal-app-manager` in you petal's `pyproject.toml`:

    First clone `petal-app-manager` if you have not done so already

    ```bash
    cd .. # if in `my-petal` directory
    git clone https://github.com/DroneLeaf/petal-app-manager.git
    ```

    Next add `petal-app-manager` to your petal's dev dependancies

    ```toml
    [tool.pdm.dev-dependencies]
    dev = [
        "-e file:///path/to/petal-app-manager/#egg=petal-app-manager",
    ]
    ```

    This enables your petal's intellisense to pick up changes that you make to `petal-app-manager`

> [!TIP]
> You may use relative paths for your `petal-app-manager`
> ```toml
> local = [
>     "-e file:///${PROJECT_ROOT}/../petal-app-manager/#egg=petal-app-manager",
> ]
> ```

5. Install your petal in development mode

    ```bash
    pdm install --dev
    ```