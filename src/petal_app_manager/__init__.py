# Load environment variables from .env file if it exists
import os
import dotenv
dotenv.load_dotenv(dotenv.find_dotenv())

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    # ⚠️ Use the *distribution* name (what you put in pyproject.toml), not necessarily the import name
    __version__ = _pkg_version("petal-app-manager")
except PackageNotFoundError:
    # Useful during local development before install; pick what you prefer here
    __version__ = "0.0.0"

class Config:
    # General configuration
    PETAL_LOG_LEVEL = os.environ.get("PETAL_LOG_LEVEL", "INFO").upper()
    PETAL_LOG_TO_FILE = os.environ.get("PETAL_LOG_TO_FILE", "true").lower() in ("true", "1", "yes")
    PETAL_LOG_DIR = os.environ.get("PETAL_LOG_DIR", "logs")

    # Per-level logging output configuration
    @staticmethod
    def get_log_level_outputs():
        import json
        from pathlib import Path
        try:
            config_path = Path(__file__).parent.parent.parent / "config.json"
            with open(config_path, 'r') as f:
                config = json.load(f)
                logging_config = config.get("logging", {})
                level_outputs = logging_config.get("level_outputs")
                if level_outputs:
                    normalized = {}
                    for level, output in level_outputs.items():
                        if isinstance(output, list):
                            valid_outputs = [o for o in output if o in ("terminal", "file")]
                            if valid_outputs:
                                normalized[level] = valid_outputs
                        elif isinstance(output, str):
                            if output == "both":
                                normalized[level] = ["terminal", "file"]
                            elif output in ("terminal", "file"):
                                normalized[level] = [output]
                    return normalized if normalized else None
        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            pass
        return None

    # Cloud configuration
    ACCESS_TOKEN_URL = os.environ.get('PETAL_ACCESS_TOKEN_URL', '')
    SESSION_TOKEN_URL = os.environ.get('PETAL_SESSION_TOKEN_URL', '')
    S3_BUCKET_NAME   = os.environ.get('PETAL_S3_BUCKET_NAME', '')
    CLOUD_ENDPOINT   = os.environ.get('PETAL_CLOUD_ENDPOINT', '')

    # Local database configuration
    LOCAL_DB_HOST = os.environ.get('PETAL_LOCAL_DB_HOST', 'localhost')
    LOCAL_DB_PORT = int(os.environ.get('PETAL_LOCAL_DB_PORT', 3000))

    # Redis configuration (nested source of truth)
    class RedisConfig:
        HOST = os.environ.get('PETAL_REDIS_HOST', 'localhost')
        PORT = int(os.environ.get('PETAL_REDIS_PORT', 6379))
        DB = int(os.environ.get('PETAL_REDIS_DB', 0))
        PASSWORD = os.environ.get('PETAL_REDIS_PASSWORD', None)
        UNIX_SOCKET_PATH = os.environ.get('PETAL_REDIS_UNIX_SOCKET_PATH', None)
        HEALTH_MESSAGE_RATE = float(os.environ.get('PETAL_REDIS_HEALTH_MESSAGE_RATE', 3.0))
        WORKER_THREADS = int(os.environ.get('PETAL_REDIS_WORKER_THREADS', 4))

    # URLs for data operations
    GET_DATA_URL    = os.environ.get('PETAL_GET_DATA_URL', '/drone/onBoard/config/getData')
    SCAN_DATA_URL   = os.environ.get('PETAL_SCAN_DATA_URL', '/drone/onBoard/config/scanData')
    UPDATE_DATA_URL = os.environ.get('PETAL_UPDATE_DATA_URL', '/drone/onBoard/config/updateData')
    SET_DATA_URL    = os.environ.get('PETAL_SET_DATA_URL', '/drone/onBoard/config/setData')

    # MQTT configuration (nested source of truth)
    class MQTTConfig:
        TS_CLIENT_HOST = os.environ.get('PETAL_TS_CLIENT_HOST', 'localhost')
        TS_CLIENT_PORT = int(os.environ.get('PETAL_TS_CLIENT_PORT', 3004))
        CALLBACK_HOST  = os.environ.get('PETAL_CALLBACK_HOST', 'localhost')
        CALLBACK_PORT  = int(os.environ.get('PETAL_CALLBACK_PORT', 9000))
        ENABLE_CALLBACKS = os.environ.get('PETAL_ENABLE_CALLBACKS', 'true').lower() in ('true', '1', 'yes')
        COMMAND_EDGE_TOPIC = os.environ.get('PETAL_COMMAND_EDGE_TOPIC', 'command/edge')
        RESPONSE_TOPIC = os.environ.get('PETAL_RESPONSE_TOPIC', 'response')
        TEST_TOPIC = os.environ.get('PETAL_TEST_TOPIC', 'command')
        COMMAND_WEB_TOPIC = os.environ.get('PETAL_COMMAND_WEB_TOPIC', 'command/web')
        HEALTH_CHECK_INTERVAL = float(os.environ.get('PETAL_MQTT_HEALTH_CHECK_INTERVAL', 10.0))
    # Misc
    class PetalUserJourneyCoordinatorConfig:
        DEBUG_SQUARE_TEST = os.environ.get("PETAL_DEBUG_SQUARE_TEST", "false").lower() in ("true", "1", "yes")

    class MavLinkConfig:
        ENDPOINT = os.environ.get("PETAL_MAVLINK_ENDPOINT", "udp:127.0.0.1:14551")
        BAUD = int(os.environ.get("PETAL_MAVLINK_BAUD", 115200))
        SOURCE_SYSTEM_ID = int(os.environ.get("PETAL_MAVLINK_SOURCE_SYSTEM_ID", 2))
        SOURCE_COMPONENT_ID = int(os.environ.get("PETAL_MAVLINK_SOURCE_COMPONENT_ID", 140)) # MAV_COMP_ID_USER1–USER4 140–143
        MAXLEN = int(os.environ.get("PETAL_MAVLINK_MAXLEN", 200))
        WORKER_SLEEP_MS = float(os.environ.get('PETAL_MAVLINK_WORKER_SLEEP_MS', 1))
        WORKER_THREADS = int(os.environ.get('PETAL_MAVLINK_WORKER_THREADS', 4))
        HEARTBEAT_SEND_FREQUENCY = float(os.environ.get('PETAL_MAVLINK_HEARTBEAT_SEND_FREQUENCY', 5.0))
        ROOT_SD_PATH = os.environ.get('PETAL_ROOT_SD_PATH', 'fs/microsd/log')
    class LoggingConfig:
        LEVEL = os.environ.get("PETAL_LOG_LEVEL", "INFO").upper()
        TO_FILE = os.environ.get("PETAL_LOG_TO_FILE", "true").lower() in ("true", "1", "yes")

    # Proxy connection configuration
    class ProxyConfig:
        # Retry intervals for proxy connection monitoring (seconds)
        MQTT_RETRY_INTERVAL = float(os.environ.get('PETAL_MQTT_RETRY_INTERVAL', 10.0))
        CLOUD_RETRY_INTERVAL = float(os.environ.get('PETAL_CLOUD_RETRY_INTERVAL', 10.0))
        
        # Timeouts for proxy startup operations (seconds)
        MQTT_STARTUP_TIMEOUT = float(os.environ.get('PETAL_MQTT_STARTUP_TIMEOUT', 5.0))
        CLOUD_STARTUP_TIMEOUT = float(os.environ.get('PETAL_CLOUD_STARTUP_TIMEOUT', 5.0))
        MQTT_SUBSCRIBE_TIMEOUT = float(os.environ.get('PETAL_MQTT_SUBSCRIBE_TIMEOUT', 5.0))

    # ------- Backward-compatibility aliases (class attributes, not @property) -------
    # Accessing Config.MAVLINK_BAUD (etc.) now returns an int/str directly.
    MAVLINK_ENDPOINT = MavLinkConfig.ENDPOINT
    MAVLINK_BAUD = MavLinkConfig.BAUD
    MAVLINK_SOURCE_SYSTEM_ID = MavLinkConfig.SOURCE_SYSTEM_ID
    MAVLINK_SOURCE_COMPONENT_ID = MavLinkConfig.SOURCE_COMPONENT_ID # MAV_COMP_ID_USER1–USER4 140–143
    MAVLINK_MAXLEN = MavLinkConfig.MAXLEN
    MAVLINK_WORKER_SLEEP_MS = MavLinkConfig.WORKER_SLEEP_MS
    MAVLINK_WORKER_THREADS = MavLinkConfig.WORKER_THREADS
    MAVLINK_HEARTBEAT_SEND_FREQUENCY = MavLinkConfig.HEARTBEAT_SEND_FREQUENCY
    ROOT_SD_PATH = MavLinkConfig.ROOT_SD_PATH

    REDIS_HOST = RedisConfig.HOST
    REDIS_PORT = RedisConfig.PORT
    REDIS_DB = RedisConfig.DB
    REDIS_PASSWORD = RedisConfig.PASSWORD
    REDIS_UNIX_SOCKET_PATH = RedisConfig.UNIX_SOCKET_PATH
    REDIS_HEALTH_MESSAGE_RATE = RedisConfig.HEALTH_MESSAGE_RATE
    REDIS_WORKER_THREADS = RedisConfig.WORKER_THREADS

    TS_CLIENT_HOST = MQTTConfig.TS_CLIENT_HOST
    TS_CLIENT_PORT = MQTTConfig.TS_CLIENT_PORT
    CALLBACK_HOST = MQTTConfig.CALLBACK_HOST
    CALLBACK_PORT = MQTTConfig.CALLBACK_PORT
    ENABLE_CALLBACKS = MQTTConfig.ENABLE_CALLBACKS
    COMMAND_EDGE_TOPIC = MQTTConfig.COMMAND_EDGE_TOPIC
    RESPONSE_TOPIC = MQTTConfig.RESPONSE_TOPIC
    TEST_TOPIC = MQTTConfig.TEST_TOPIC
    COMMAND_WEB_TOPIC = MQTTConfig.COMMAND_WEB_TOPIC
    MQTT_HEALTH_CHECK_INTERVAL = MQTTConfig.HEALTH_CHECK_INTERVAL

    MQTT_RETRY_INTERVAL = ProxyConfig.MQTT_RETRY_INTERVAL
    CLOUD_RETRY_INTERVAL = ProxyConfig.CLOUD_RETRY_INTERVAL
    MQTT_STARTUP_TIMEOUT = ProxyConfig.MQTT_STARTUP_TIMEOUT
    CLOUD_STARTUP_TIMEOUT = ProxyConfig.CLOUD_STARTUP_TIMEOUT
    MQTT_SUBSCRIBE_TIMEOUT = ProxyConfig.MQTT_SUBSCRIBE_TIMEOUT
