# Load environment variables from .env file if it exists
import os
import dotenv

dotenv.load_dotenv(dotenv.find_dotenv())

class Config:
    # General configuration
    PETAL_LOG_LEVEL=os.environ.get("PETAL_LOG_LEVEL", "INFO").upper()
    PETAL_LOG_TO_FILE=os.environ.get("PETAL_LOG_TO_FILE", "true").lower() in ("true", "1", "yes")
    
    # Per-level logging output configuration
    # Read from config.json file in the project root
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
                    # Validate and normalize the configuration
                    normalized = {}
                    for level, output in level_outputs.items():
                        if isinstance(output, list):
                            # Validate list format
                            valid_outputs = [o for o in output if o in ("terminal", "file")]
                            if valid_outputs:
                                normalized[level] = valid_outputs
                        elif isinstance(output, str):
                            # Handle legacy string format
                            if output == "both":
                                normalized[level] = ["terminal", "file"]
                            elif output in ("terminal", "file"):
                                normalized[level] = [output]
                    
                    return normalized if normalized else None
        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            pass
        
        return None
    
    # MAVLink configuration
    MAVLINK_ENDPOINT=os.environ.get("MAVLINK_ENDPOINT", "udp:127.0.0.1:14551")
    MAVLINK_BAUD=int(os.environ.get("MAVLINK_BAUD", 115200))
    MAVLINK_MAXLEN=int(os.environ.get("MAVLINK_MAXLEN", 200))
    MAVLINK_WORKER_SLEEP_MS = int(os.environ.get('MAVLINK_WORKER_SLEEP_MS', 1))
    MAVLINK_HEARTBEAT_SEND_FREQUENCY = float(os.environ.get('MAVLINK_HEARTBEAT_SEND_FREQUENCY', 5.0))
    ROOT_SD_PATH = os.environ.get('ROOT_SD_PATH', 'fs/microsd/log')
    # Cloud configuration
    ACCESS_TOKEN_URL = os.environ.get('ACCESS_TOKEN_URL', '')
    SESSION_TOKEN_URL = os.environ.get('SESSION_TOKEN_URL', '')
    S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', '')
    CLOUD_ENDPOINT = os.environ.get('CLOUD_ENDPOINT', '')
    # Local database configuration
    LOCAL_DB_HOST = os.environ.get('LOCAL_DB_HOST', 'localhost')
    LOCAL_DB_PORT = int(os.environ.get('LOCAL_DB_PORT', 3000))
    # Redis configuration
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_DB = int(os.environ.get('REDIS_DB', 0))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
    REDIS_UNIX_SOCKET_PATH = os.environ.get('REDIS_UNIX_SOCKET_PATH', None)
    # URLs for data operations
    GET_DATA_URL = os.environ.get('GET_DATA_URL', '/drone/onBoard/config/getData')
    SCAN_DATA_URL = os.environ.get('SCAN_DATA_URL', '/drone/onBoard/config/scanData')
    UPDATE_DATA_URL = os.environ.get('UPDATE_DATA_URL', '/drone/onBoard/config/updateData')
    SET_DATA_URL = os.environ.get('SET_DATA_URL', '/drone/onBoard/config/setData')
    # MQTT configuration
    TS_CLIENT_HOST = os.environ.get('TS_CLIENT_HOST', 'localhost')
    TS_CLIENT_PORT = int(os.environ.get('TS_CLIENT_PORT', 3004))
    CALLBACK_HOST = os.environ.get('CALLBACK_HOST', 'localhost')
    CALLBACK_PORT = int(os.environ.get('CALLBACK_PORT', 3005))
    ENABLE_CALLBACKS = os.environ.get('ENABLE_CALLBACKS', 'true').lower() in ('true', '1', 'yes')
