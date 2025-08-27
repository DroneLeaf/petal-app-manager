# Petal App Manager

A modular application framework for building and deploying "Petals" - pluggable components that can interact with various systems through a unified proxy architecture. Built on FastAPI, Petal App Manager provides a structured way to develop applications that need to interact with external systems like MAVLink devices, Redis, local databases, and more.

## Overview

Petal App Manager serves as a backbone for developing modular applications. It:

- Provides a proxy system to interact with different backends (MAVLink, Redis, DynamoDB)
- Offers a plugin architecture for developing and loading "Petals"
- Handles HTTP, WebSocket, and MQTT (planned) endpoints automatically
- Manages the lifecycle of connections and resources

## Dependencies

- Python 3.10+ and `python3-dev` package (for building some dependencies)

    ```bash
    sudo add-apt-repository ppa:deadsnakes/ppa --yes
    sudo apt update; apt-get update;
    sudo apt-get install python3.10 -y
    sudo apt-get install python3.10-dev
    ```

> [!NOTE]
> You can change `python3.10` to whatever version you like `>=3.10`

- Redis server (for caching and message passing)

    ```bash
    # Install Redis on Ubuntu/Debian
    sudo apt-get install redis-server

    # Start Redis service
    sudo systemctl start redis-server
    sudo systemctl enable redis-server  # Auto-start on boot
    ```

- Controller-dashboard setup

    The controller dashboard can be installed using
    ```bash
    hear-cli local_machine run_program --p controller_dashboard_prepare
    ```

- Additional dependencies based on specific petals

## Installation

### Dependencies Setup

- For building pymavlink from source, ensure GCC is used (see above)

```bash
export CC=gcc
pdm install -G prod
```

### Installation From PyPI (recommended for users)

```bash
pip install petal-app-manager
```

You may run the server using

```bash
# Install and run with uvicorn
uvicorn petal_app_manager.main:app --port 9000
```

> [!TIP]
> If you would like to run the server with logging to a file enabled:
> create a `.env` file and place it in the project root directory
> Below is a list of some other useful parameters
> ```ini
> # .env file for Petal App Manager configuration
> # General configuration
> PETAL_LOG_LEVEL=INFO
> PETAL_LOG_TO_FILE=true
> # MAVLink configuration
> MAVLINK_ENDPOINT=udp:127.0.0.1:14551
> MAVLINK_BAUD=115200
> MAVLINK_MAXLEN=200
> MAVLINK_WORKER_SLEEP_MS=1
> MAVLINK_HEARTBEAT_SEND_FREQUENCY=5.0
> ROOT_SD_PATH=fs/microsd/log
> # Cloud configuration
> ACCESS_TOKEN_URL=http://localhost:3001/session-manager/access-token
> SESSION_TOKEN_URL=http://localhost:3001/session-manager/session-token
> S3_BUCKET_NAME=devhube21f2631b51e4fa69c771b1e8107b21cb431a-dev
> CLOUD_ENDPOINT=https://api.droneleaf.io
> # Local database configuration
> LOCAL_DB_HOST=localhost
> LOCAL_DB_PORT=3000
> # Redis configuration
> REDIS_HOST=localhost
> REDIS_PORT=6379
> REDIS_DB=0
> REDIS_UNIX_SOCKET_PATH=/var/run/redis/redis-server.sock
> # Data operations URLs
> GET_DATA_URL=/drone/onBoard/config/getData
> SCAN_DATA_URL=/drone/onBoard/config/scanData
> UPDATE_DATA_URL=/drone/onBoard/config/updateData
> SET_DATA_URL=/drone/onBoard/config/setData
> # MQTT client
> TS_CLIENT_HOST=localhost
> TS_CLIENT_PORT=3004
> CALLBACK_HOST=localhost
> CALLBACK_PORT=3005
> POLL_INTERVAL=1.0
> ENABLE_CALLBACKS=true
> ```

### Development Installation (recommended for developers)

For development of `petal-app-manager` concurrently with your `petal`, it's recommended to use an editable installation. 

1. First clone the `petal-app-manager`

> [!NOTE]
> Please see the [petal development guide](petals.md) first

    ```bash
    git clone https://github.com/DroneLeaf/petal-app-manager.git
    git clone https://github.com/DroneLeaf/petal-flight-log.git
    git clone --recurse-submodules https://github.com/DroneLeaf/mavlink.git
    cd petal-app-manager
    ```

2. Define your dev dependancies (i.e., your petal) in [pyproject.toml](pyproject.toml) as

    ```toml
    dev = [
        # your existing dependancies
        "-e file:///${PROJECT_ROOT}/../petal-flight-log/#egg=petal-flight-log",
        "-e file:///${PROJECT_ROOT}/../mavlink/pymavlink/#egg=leaf-pymavlink",
        # ...
        "-e file:///path/to/your/my-petal/#egg=my-petal"
    ]
    ```

> [!NOTE]
> If you would like to develop mavlink or add user-defined mavlink messages, you may do so under your local clone of `mavlink` [https://github.com/DroneLeaf/mavlink.git](https://github.com/DroneLeaf/mavlink.git)
> `pymavlink` will be available at `/path/to/mavlink/pymavlink` under the mavlink directory. You can then add it to [pyproject.toml](pyproject.toml)
> ```toml
> dev = [
>     "-e file:///path/to/pymavlink/#egg=leaf-pymavlink",
> ]
> ```

> [!TIP]
> You may use relative paths intead of absolute paths like so (assuming your directories are one level higher than `petal-app-manager`)
> ```bash
> cd .. # if in the petal-app-manager directory
> git clone --recurse-submodules https://github.com/DroneLeaf/mavlink.git
> ```
> and then add them to your dependancies under [pyproject.toml](pyproject.toml)
> ```toml
> dev = [
>     # existing petals
>     "-e file:///${PROJECT_ROOT}/../mavlink/pymavlink/#egg=leaf-pymavlink",
>     "-e file:///${PROJECT_ROOT}/../my-petal/#egg=my-petal",
> ]
> ```

3. Finally, you may install your dependancies in editable mode

    ```bash
    pdm install -G dev
    ```

4. You may now run the `petal-app-manager` server

    ```bash
    source .venv/bin/activate # to activate the pdm virtual environment in which everythign is installed
    uvicorn petal_app_manager.main:app --reload --port 9000
    ```

5. Test your endpoints:
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