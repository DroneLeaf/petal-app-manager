# Petal App Manager

A modular application framework for building and deploying "Petals" - pluggable components that can interact with various systems through a unified proxy architecture. Built on FastAPI, Petal App Manager provides a structured way to develop applications that need to interact with external systems like MAVLink devices, Redis, local databases, and more.

## Overview

Petal App Manager serves as a backbone for developing modular applications. It:

- Provides a proxy system to interact with different backends (MAVLink, Redis, DynamoDB)
- Offers a plugin architecture for developing and loading "Petals"
- Handles HTTP, WebSocket, and MQTT (planned) endpoints automatically
- Manages the lifecycle of connections and resources

## Dependencies

### System Requirements

- **Python 3.11**: The application requires Python 3.11 specifically
- **Redis 7.2+**: For caching, message passing, and inter-process communication
- **Build tools**: Required for compiling Python packages from source
- **PDM**: Python Development Master for dependency management

### Detailed Installation Steps

#### 1. Python 3.11 Installation (via pyenv)

Python 3.11 is installed using `pyenv` to avoid conflicts with the system Python:

```bash
# Install build dependencies
sudo apt-get update
sudo apt-get install -y make build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev \
    liblzma-dev libgdbm-dev libnss3-dev software-properties-common ca-certificates

# Install pyenv
curl -sSL https://pyenv.run | bash

# Add pyenv to PATH (add to ~/.bashrc for persistence)
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"

# Install Python 3.11
pyenv install 3.11.0

# Create symlinks for system-wide access
sudo ln -sf "$HOME/.pyenv/versions/3.11.0/bin/python3.11" /usr/local/bin/python3.11
sudo ln -sf "$HOME/.pyenv/versions/3.11.0/bin/pip3.11" /usr/local/bin/pip3.11

# Verify installation
python3.11 --version
```

> [!NOTE]
> This installation method keeps the system's default Python 3 unchanged while making Python 3.11 available via the `python3.11` command.

#### 2. PDM Installation

PDM is used for dependency management and virtual environment handling:

```bash
# Install PDM using Python 3.11
curl -sSL https://pdm-project.org/install-pdm.py | python3.11 -

# Add PDM to PATH
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"

# Configure PDM to allow pip within virtual environments
pdm config venv.with_pip True

# Verify installation
pdm --version
```

#### 3. Redis Installation and Configuration

Install Redis 7.2+ with UNIX socket support:

```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y lsb-release curl gpg apt-transport-https ca-certificates gnupg

# Add Redis official repository
curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
sudo chmod 644 /usr/share/keyrings/redis-archive-keyring.gpg

DISTRO="$(lsb_release -cs)"
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $DISTRO main" | \
    sudo tee /etc/apt/sources.list.d/redis.list

# Install Redis
sudo apt-get update
sudo apt-get install -y redis

# Configure Redis for UNIX socket
sudo cp /etc/redis/redis.conf /etc/redis/redis.conf.bak

# Enable UNIX socket in configuration
sudo sed -i 's|^# *unixsocket .*|unixsocket /var/run/redis/redis-server.sock|' /etc/redis/redis.conf
sudo sed -i 's|^# *unixsocketperm .*|unixsocketperm 777|' /etc/redis/redis.conf
sudo sed -i 's|^.*daemonize.*|daemonize no|' /etc/redis/redis.conf
sudo sed -i 's|^.*supervised.*|supervised systemd|' /etc/redis/redis.conf

# Restart Redis to apply changes
sudo systemctl daemon-reload
sudo systemctl restart redis-server
sudo systemctl enable redis-server

# Set socket permissions
sudo chmod 777 /var/run/redis/redis-server.sock

# Verify installation
redis-server --version
```

#### 4. Redis Development Tools (Optional, for C++ integration)

```bash
# Install hiredis library
sudo apt-get install -y libhiredis-dev

# Install redis-plus-plus (C++ client)
mkdir -p ~/.hear-cli/redis_tmp
cd ~/.hear-cli/redis_tmp
git clone https://github.com/sewenew/redis-plus-plus.git
cd redis-plus-plus
mkdir build && cd build
cmake ..
make
sudo make install
```

#### 5. Controller Dashboard Setup (Optional)

The controller dashboard can be installed using:
```bash
hear-cli local_machine run_program --p controller_dashboard_prepare
```

### Additional Dependencies

- Additional dependencies based on specific petals (e.g., MAVLink, DynamoDB clients)
- Git credentials for private repositories (if installing from source)

## Installation

### Production Installation (Automated via HEAR CLI)

For production deployments on target hardware (Raspberry Pi, Ubuntu systems, NVIDIA Orin), use the HEAR-CLI automated installation:

```bash
# This command installs all dependencies (Python 3.11, PDM, Redis 7.2+)
# and clones petal-app-manager to ~/.droneleaf/petal-app-manager
hear-cli local_machine run_program --p petal_app_manager_prepare_arm
```

This automated script performs the following:
1. Installs Python 3.11 via pyenv
2. Installs and configures PDM
3. Installs and configures Redis 7.2+ with UNIX socket support
4. Installs Redis development tools (hiredis, redis-plus-plus)
5. Clones petal-app-manager to `~/.droneleaf/petal-app-manager`
6. Configures PDM to use Python 3.11: `pdm use -f /usr/bin/python3.11`
7. Installs production dependencies: `pdm install -G prod`
8. Creates the `.env` configuration file
9. Sets up auto-start for the service

> [!NOTE]
> The installation script requires GitHub credentials for accessing private repositories. These will be requested during the installation process.

### Environment Configuration

Create a `.env` file in the project root directory:

> [!NOTE]
> All environment variables use the `PETAL_` prefix to avoid conflicts with other applications.

```bash
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
PETAL_COMMAND_EDGE_TOPIC=command/edge
PETAL_RESPONSE_TOPIC=response
PETAL_TEST_TOPIC=command
PETAL_COMMAND_WEB_TOPIC=command/web
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
```

### Installation From PyPI (for simple setups)

```bash
# Note: PyPI installation may not include all production dependencies
# For production use, follow the automated installation steps above
pip install petal-app-manager
```

You may run the server using:

```bash
uvicorn petal_app_manager.main:app --port 9000
```

> [!WARNING]
> PyPI installation is simplified and may not include all dependencies required for production deployments. For production systems, use the automated installation process described above with PDM.

### Development Installation (recommended for developers)

For development of `petal-app-manager` concurrently with petals, use the HEAR-CLI automated development setup:

```bash
# This command sets up the complete development environment
# including all petals, LeafSDK, and mavlink with pymavlink
hear-cli local_machine run_program --p petal_app_manager_prepare_sitl
```

This creates the following directory structure in `~/petal-app-manager-dev/`:

```
petal-app-manager-dev/
├── LeafSDK/                              # Drone control SDK
├── mavlink/                              # MAVLink protocol (with pymavlink)
├── petal-app-manager/                    # Main application framework
├── petal-flight-log/                     # Flight log management petal
├── petal-leafsdk/                        # LeafSDK integration petal
├── petal-qgc-mission-server/            # QGroundControl mission server petal
├── petal-user-journey-coordinator/       # User journey coordination petal
└── petal-warehouse/                      # Data warehousing petal
```

#### Manual Development Setup

If you prefer to set up the development environment manually:

> [!IMPORTANT]
> Ensure all dependencies are installed first:
> - Python 3.11 (via pyenv)
> - PDM with pip support enabled
> - Redis 7.2+ with UNIX socket configured
> See the Dependencies section above for detailed installation steps.

1. Clone all required repositories:

> [!NOTE]
> Please see the [petal development guide](petals.md) first

    ```bash
    mkdir -p ~/petal-app-manager-dev
    cd ~/petal-app-manager-dev
    
    # Clone core repositories
    git clone https://github.com/DroneLeaf/petal-app-manager.git
    git clone --recurse-submodules https://github.com/DroneLeaf/mavlink.git
    git clone https://github.com/DroneLeaf/LeafSDK.git
    
    # Clone petals
    git clone https://github.com/DroneLeaf/petal-flight-log.git
    git clone https://github.com/DroneLeaf/petal-leafsdk.git
    git clone https://github.com/DroneLeaf/petal-qgc-mission-server.git
    git clone https://github.com/DroneLeaf/petal-user-journey-coordinator.git
    git clone https://github.com/DroneLeaf/petal-warehouse.git
    
    cd petal-app-manager
    ```

2. Review dev dependencies in [pyproject.toml](pyproject.toml)

    The development dependencies are already configured with editable installations:

    ```toml
    [dependency-groups]
    dev = [
        "pytest>=8.4.0",
        "pytest-asyncio>=1.0.0",
        "anyio>=4.9.0",
        "pytest-cov>=6.2.1",
        "leaf-pymavlink @ file:///${PROJECT_ROOT}/../mavlink/pymavlink",
        "-e file:///${PROJECT_ROOT}/../petal-flight-log/#egg=petal-flight-log",
        "-e file:///${PROJECT_ROOT}/../petal-user-journey-coordinator/#egg=petal-user-journey-coordinator",
        "-e file:///${PROJECT_ROOT}/../petal-leafsdk/#egg=petal-leafsdk",
        "-e file:///${PROJECT_ROOT}/../petal-warehouse/#egg=petal-warehouse",
        "-e file:///${PROJECT_ROOT}/../LeafSDK/#egg=LeafSDK",
    ]
    ```

> [!NOTE]
> If you would like to develop mavlink or add user-defined mavlink messages, you can do so under your local clone of `mavlink` [https://github.com/DroneLeaf/mavlink.git](https://github.com/DroneLeaf/mavlink.git). The `pymavlink` package will be available at `../mavlink/pymavlink` and is already configured as a dependency.

> [!TIP]
> To add your own custom petal for development:
> ```toml
> dev = [
>     # existing dependencies...
>     "-e file:///${PROJECT_ROOT}/../my-custom-petal/#egg=my-custom-petal",
> ]
> ```

3. Configure PDM to use Python 3.11 and install dependencies

    ```bash
    # Ensure PDM is configured to use Python 3.11
    pdm use -f /usr/bin/python3.11
    
    # Install dependencies in editable mode
    pdm install -G dev
    ```

4. Create the `.env` configuration file (see Environment Configuration section above)

5. Run the `petal-app-manager` server

    ```bash
    # Activate the PDM virtual environment
    source .venv/bin/activate
    
    # Run the server with auto-reload for development
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
src/petal_app_manager/
├── api/                           # Core API endpoints
│   ├── admin_ui.py                # Admin dashboard UI
│   ├── bucket_api.py              # S3 bucket operations
│   ├── cloud_api.py               # Cloud service integration
│   ├── config_api.py              # Configuration management
│   ├── health.py                  # Health check endpoints
│   ├── mavftp_api.py              # MAVLink FTP operations
│   ├── mqtt_api.py                # MQTT integration
│   └── proxy_info.py              # Proxy information endpoints
├── assets/                        # Static assets
│   ├── css/
│   │   └── admin-dashboard.css
│   └── js/
│       └── admin-dashboard.js
├── config.py                      # Configuration management
├── examples/                      # Usage examples
│   ├── example_mqtt_usage.py
│   ├── example_redis_petal.py
│   ├── hear_fc_communication_example.py
│   ├── integration_test_hear_fc.py
│   ├── logging_example_petal.py
│   ├── mavlink_burst_filtering_example.py
│   ├── proxy_usage_example.py
│   ├── redis_usage_examples.py
│   └── simple_redis_petal.py
├── health_service.py              # Health monitoring service
├── logger.py                      # Logging configuration
├── main.py                        # FastAPI application setup
├── models/                        # Data models
│   ├── health.py
│   └── __init__.py
├── organization_manager.py        # Organization management
├── plugins/                       # Plugin architecture
│   ├── base.py                    # Base Petal class
│   ├── decorators.py              # HTTP/WebSocket decorators
│   └── loader.py                  # Dynamic petal loading
├── proxies/                       # Backend communication
│   ├── base.py                    # BaseProxy abstract class
│   ├── bucket.py                  # S3 bucket proxy
│   ├── cloud.py                   # Cloud database proxy
│   ├── external.py                # MAVLink communication
│   ├── localdb.py                 # Local DynamoDB proxy
│   ├── mqtt.py                    # MQTT proxy
│   ├── org_utils.py               # Organization utilities
│   └── redis.py                   # Redis proxy
├── templates/                     # HTML templates
│   └── admin-dashboard.html
└── utils/                         # Utility functions
    ├── log_tool.py                # Log management tool
    ├── machineid_arm              # Machine ID binary (ARM)
    └── machineid_x86              # Machine ID binary (x86)
```

## Available Petals

The framework includes the following production petals (installed via `pdm install -G prod`):

- **petal-flight-log** ([v0.1.6](https://github.com/DroneLeaf/petal-flight-log)): Flight log management and uploading
- **petal-warehouse** ([v0.1.7](https://github.com/DroneLeaf/petal-warehouse)): Data warehousing and analytics
- **petal-leafsdk** ([v0.1.12](https://github.com/DroneLeaf/petal-leafsdk)): LeafSDK integration for drone control
- **petal-user-journey-coordinator** ([v0.1.2](https://github.com/DroneLeaf/petal-user-journey-coordinator)): User journey and mission coordination

Additional petals for development:
- **petal-qgc-mission-server**: QGroundControl mission server integration

### Activating Petals

Petals must be activated in the `proxies.yaml` configuration file to be loaded at runtime. Add your petal to the `enabled_petals` list and specify its proxy dependencies:

```yaml
enabled_petals:
  - flight_records
  - petal_warehouse
  - mission_planner
  - petal_user_journey_coordinator
  - my_custom_petal  # Add your petal here

petal_dependencies:
  my_custom_petal:
    - redis          # List required proxies
    - ext_mavlink
```

> [!TIP]
> After adding a new petal to your dependencies in `pyproject.toml`, remember to:
> 1. Run `pdm install -G dev` (or `-G prod` for production petals)
> 2. Add the petal name to `enabled_petals` in `proxies.yaml`
> 3. Specify any proxy dependencies in `petal_dependencies`
> 4. Restart the application

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

- **Python 3.11 Not Found**:
    - Verify pyenv installation: `pyenv versions`
    - Check symlinks: `ls -la /usr/bin/python3.11 /usr/local/bin/python3.11`
    - Ensure pyenv is in PATH: `export PATH="$HOME/.pyenv/bin:$PATH"`
    - Try sourcing bashrc: `source ~/.bashrc`

- **PDM Installation Fails**:
    - Ensure Python 3.11 pip is available: `python3.11 -m pip --version`
    - Check that `~/.local/bin` is in PATH
    - Verify venv module: `python3.11 -m venv --help`

- **Redis Connection Errors**:
    - Ensure Redis server is running: `sudo systemctl status redis-server`
    - Verify Redis version: `redis-server --version` (should be 7.2+)
    - Check UNIX socket exists: `ls -la /var/run/redis/redis-server.sock`
    - Verify socket permissions: `sudo chmod 777 /var/run/redis/redis-server.sock`
    - Check Redis configuration: `sudo grep -E "^unixsocket|^unixsocketperm" /etc/redis/redis.conf`
    - Test Redis connection: `redis-cli -s /var/run/redis/redis-server.sock ping`

- **Redis Configuration Issues**:
    - Backup exists at `/etc/redis/redis.conf.bak` if you need to restore
    - Ensure `daemonize no` and `supervised systemd` are set correctly
    - After config changes, restart: `sudo systemctl restart redis-server`

- **MAVLink Connection Issues**:
    - Verify the connection string in `.env` file
    - Check that the MAVLink endpoint is accessible