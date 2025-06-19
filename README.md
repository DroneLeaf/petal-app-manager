# Petal App Manager

A modular application framework for building and deploying "Petals" - pluggable components that can interact with various systems through a unified proxy architecture. Built on FastAPI, Petal App Manager provides a structured way to develop applications that need to interact with external systems like MAVLink devices, Redis, local databases, and more.

## Overview

Petal App Manager serves as a backbone for developing modular applications. It:

- Provides a proxy system to interact with different backends (MAVLink, Redis, DynamoDB)
- Offers a plugin architecture for developing and loading "Petals"
- Handles HTTP, WebSocket, and MQTT (planned) endpoints automatically
- Manages the lifecycle of connections and resources

## Dependencies

- Python 3.8+
- `python3-dev` package (for building some dependencies)
- Redis server (for caching and message passing)
- Additional dependencies based on specific petals

## Installation

### From PyPI

```bash
pip install petal-app-manager
```

### Development Installation

For development, it's recommended to use an editable installation where you define your local dependancies in [pyproject.toml](pyproject.toml) as

```toml
local = [
    "-e file:///path/to/your/my-petal/#egg=my-petal",
    "-e file:///path/to/pymavlink/#egg=leaf-pymavlink",
]
```

```bash
# Clone the repository
git clone https://github.com/your-org/petal-app-manager.git
cd petal-app-manager

pdm install -G dev -G local
```

#### Dependencies Setup

- Ensure python3-dev is installed (see above)

```bash
sudo apt-get install python3-dev
# or for specific Python versions
sudo apt-get install python3.11-dev
```

- For building pymavlink from source, ensure GCC is used (see above)

```bash
export CC=gcc
pdm install -G dev  # or pip install -e .
```

- Redis server must be running

```bash
# Install Redis on Ubuntu/Debian
sudo apt-get install redis-server

# Start Redis service
sudo systemctl start redis-server
sudo systemctl enable redis-server  # Auto-start on boot
```

## Project Structure

```bash
petal_app_manager/
├── __init__.py
├── main.py            # FastAPI application setup
├── api/               # Core API endpoints
├── plugins/           # Plugin architecture
│   ├── base.py        # Base Petal class
│   ├── decorators.py  # HTTP/WebSocket decorators
│   └── loader.py      # Dynamic petal loading
├── proxies/           # Backend communication
│   ├── base.py        # BaseProxy abstract class
│   ├── external.py    # MAVLink/ROS communication
│   ├── localdb.py     # Local DynamoDB interaction
│   └── redis.py       # Redis interaction
└── utils/             # Utility functions
```

## How It Works

### Proxy System

The framework uses proxies to interact with different backends:

- `MavLinkExternalProxy`: Communicates with PX4/MAVLink devices
- `RedisProxy`: Interfaces with Redis for caching and pub/sub
- `LocalDBProxy`: Provides access to a local DynamoDB instance

Proxies are initialized at application startup and are accessible to all petals.

### Petal Architecture

Petals are pluggable components that:

- Inherit from the `Petal` base class
- Use decorators (`@http_action`, `@websocket_action`) to define endpoints
- Are discovered and loaded automatically through Python entry points
- Have access to all registered proxies

## Running the Server

### Quick Start

```bash
# Install and run with uvicorn
pip install petal-app-manager
uvicorn petal_app_manager.main:app --reload
```

<!-- ### Docker Deployment

```bash
docker build -t petal-app-manager .
docker run -p 8000:8000 petal-app-manager
``` -->

## Developing Petals

### Creating a New Petal

1. Create a new Python package with this structure

```bash
# Create a new directory for your petal
mkdir my-petal
cd my-petal

# Initialize a PDM project
pdm init
# Answer the prompts:
# - Python interpreter: Select your Python version (3.8+ recommended)
# - Project name: my-petal
# - Package name: my-petal
# - Version: 0.1.0
# - Description: My custom petal for Petal App Manager
# - License: MIT (or your preferred license)
# - Author: Your Name
# - Email: your.email@example.com
# - Do you want to build this project for redistribution as a wheel? yes

# Create the source directory structure
mkdir -p src/my-petal

# Create the initial files
touch src/my-petal/__init__.py
touch src/my-petal/plugin.py

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

> [!NOTE]
> For integrated development mode with `petal-app-manager`, add a reference to your local clone in `pyproject.toml`:
> ```toml
> [tool.pdm.dev-dependencies]
> dev = [
>     "-e file:///path/to/petal-app-manager/#egg=petal-app-manager",
> ]
> ```
> This enables you to make changes to both your petal and the framework simultaneously.


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

4. Install your petal in development mode

```bash
pdm install --dev
```

### Testing Your Petal

Once you've created your petal, you'll want to test it with the petal-app-manager:

1. Clone the `petal-app-manager` repository if you haven't already:
    ```bash
    git clone https://github.com/DroneLeaf/petal-app-manager.git
    cd petal-app-manager
    ```

2. Install your petal in development mode:
    - Add your petal to the [pyproject.toml](pyproject.toml) file

    ```toml
    # In petal-app-manager's pyproject.toml
    [dependency-groups]
    local = [
        # Add your petal in development mode
            "-e file:///path/to/your/my-petal/#egg=my-petal",  # Adjust path to your petal directory
    ]
    ```

    - From your `petal-app-manager` directory run the following

    ```bash
    pdm install -G dev -G local
    ```

    - `petal-app-manager` should automatically discover your petal through entry points defined in your petal's `pyproject.toml`

3. Run the server:
    ```bash
    uvicorn petal_app_manager.main:app --reload --port 9000
    ```

4. Test your endpoints:
    - Access your petal at: `http://localhost:9000/petals/my-petal/hello`
    - Check the API documentation: `http://localhost:9000/docs`

> [!TIP]
> For debugging, you can use VSCode's launch configuration:
> 1. Add this to `.vscode/launch.json`:
>    ```json
>    {
>        "version": "0.2.0",
>        "configurations": [
>            {
>                "name": "Petal App Manager",
>                "type": "python",
>                "request": "launch",
>                "module": "uvicorn",
>                "args": [
>                    "petal_app_manager.main:app",
>                    "--reload",
>                    "--port", "9000"
>                ],
>                "jinja": true,
>                "justMyCode": false
>            }
>        ]
>    }
>    ```
> 2. Start debugging with F5 or the Run and Debug panel

### Available Decorators

- `@http_action(method="GET|POST", path="/endpoint")`: Define HTTP endpoints
- `@websocket_action(path="/ws/endpoint")`: Define WebSocket endpoints
- `@mqtt_action(topic="topic/name")`: Define MQTT handlers (planned)

### Example: FlightLogPetal

The FlightLogPetal demonstrates a comprehensive petal implementation:

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

## Accessing the API

Once running, access:

- API documentation: [http://localhost:9000/docs](http://localhost:9000/docs)
- ReDoc documentation: [http://localhost:9000/redoc](http://localhost:9000/redoc)
- Petal endpoints: [http://localhost:9000/petals/{petal-name}/{endpoint}](http://localhost:9000/petals/{petal-name}/{endpoint})

## Troubleshooting

### Common Issues

- **Redis Connection Errors**:
    - Ensure Redis server is running: `sudo systemctl status redis-server`
    - Check default connection settings in [main.py](src/petal_app_manager/main.py)

- **MAVLink Connection Issues**:
    - Verify the connection string