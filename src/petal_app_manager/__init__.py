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
    ACCESS_TOKEN_URL = os.environ.get('ACCESS_TOKEN_URL', '')
    SESSION_TOKEN_URL = os.environ.get('SESSION_TOKEN_URL', '')
    S3_BUCKET_NAME   = os.environ.get('S3_BUCKET_NAME', '')
    CLOUD_ENDPOINT   = os.environ.get('CLOUD_ENDPOINT', '')

    # Local database configuration
    LOCAL_DB_HOST = os.environ.get('LOCAL_DB_HOST', 'localhost')
    LOCAL_DB_PORT = int(os.environ.get('LOCAL_DB_PORT', 3000))

    # Redis configuration (nested source of truth)
    class RedisConfig:
        HOST = os.environ.get('REDIS_HOST', 'localhost')
        PORT = int(os.environ.get('REDIS_PORT', 6379))
        DB = int(os.environ.get('REDIS_DB', 0))
        PASSWORD = os.environ.get('REDIS_PASSWORD', None)
        UNIX_SOCKET_PATH = os.environ.get('REDIS_UNIX_SOCKET_PATH', None)
        HEALTH_MESSAGE_RATE = float(os.environ.get('REDIS_HEALTH_MESSAGE_RATE', 3.0))

    # URLs for data operations
    GET_DATA_URL    = os.environ.get('GET_DATA_URL', '/drone/onBoard/config/getData')
    SCAN_DATA_URL   = os.environ.get('SCAN_DATA_URL', '/drone/onBoard/config/scanData')
    UPDATE_DATA_URL = os.environ.get('UPDATE_DATA_URL', '/drone/onBoard/config/updateData')
    SET_DATA_URL    = os.environ.get('SET_DATA_URL', '/drone/onBoard/config/setData')

    # MQTT configuration (nested source of truth)
    class MQTTConfig:
        TS_CLIENT_HOST = os.environ.get('TS_CLIENT_HOST', 'localhost')
        TS_CLIENT_PORT = int(os.environ.get('TS_CLIENT_PORT', 3004))
        CALLBACK_HOST  = os.environ.get('CALLBACK_HOST', 'localhost')
        CALLBACK_PORT  = int(os.environ.get('CALLBACK_PORT', 3005))
        ENABLE_CALLBACKS = os.environ.get('ENABLE_CALLBACKS', 'true').lower() in ('true', '1', 'yes')

    # Misc
    class PetalUserJourneyCoordinatorConfig:
        DEBUG_SQUARE_TEST = os.environ.get("DEBUG_SQUARE_TEST", "false").lower() in ("true", "1", "yes")

    class MavLinkConfig:
        ENDPOINT = os.environ.get("MAVLINK_ENDPOINT", "udp:127.0.0.1:14551")
        BAUD = int(os.environ.get("MAVLINK_BAUD", 115200))
        MAXLEN = int(os.environ.get("MAVLINK_MAXLEN", 200))
        WORKER_SLEEP_MS = int(os.environ.get('MAVLINK_WORKER_SLEEP_MS', 1))
        HEARTBEAT_SEND_FREQUENCY = float(os.environ.get('MAVLINK_HEARTBEAT_SEND_FREQUENCY', 5.0))
        ROOT_SD_PATH = os.environ.get('ROOT_SD_PATH', 'fs/microsd/log')

    class LoggingConfig:
        LEVEL = os.environ.get("PETAL_LOG_LEVEL", "INFO").upper()
        TO_FILE = os.environ.get("PETAL_LOG_TO_FILE", "true").lower() in ("true", "1", "yes")

    # ------- Backward-compatibility aliases (class attributes, not @property) -------
    # Accessing Config.MAVLINK_BAUD (etc.) now returns an int/str directly.
    MAVLINK_ENDPOINT = MavLinkConfig.ENDPOINT
    MAVLINK_BAUD = MavLinkConfig.BAUD
    MAVLINK_MAXLEN = MavLinkConfig.MAXLEN
    MAVLINK_WORKER_SLEEP_MS = MavLinkConfig.WORKER_SLEEP_MS
    MAVLINK_HEARTBEAT_SEND_FREQUENCY = MavLinkConfig.HEARTBEAT_SEND_FREQUENCY
    ROOT_SD_PATH = MavLinkConfig.ROOT_SD_PATH

    REDIS_HOST = RedisConfig.HOST
    REDIS_PORT = RedisConfig.PORT
    REDIS_DB = RedisConfig.DB
    REDIS_PASSWORD = RedisConfig.PASSWORD
    REDIS_UNIX_SOCKET_PATH = RedisConfig.UNIX_SOCKET_PATH
    REDIS_HEALTH_MESSAGE_RATE = RedisConfig.HEALTH_MESSAGE_RATE

    TS_CLIENT_HOST = MQTTConfig.TS_CLIENT_HOST
    TS_CLIENT_PORT = MQTTConfig.TS_CLIENT_PORT
    CALLBACK_HOST = MQTTConfig.CALLBACK_HOST
    CALLBACK_PORT = MQTTConfig.CALLBACK_PORT
    ENABLE_CALLBACKS = MQTTConfig.ENABLE_CALLBACKS
