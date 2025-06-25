from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # Add this import
from .proxies import cloud, localdb, redis, external
from .plugins.loader import load_petals
from .api import health, proxy_info

from .logger import setup_logging
from pathlib import Path
import os
import dotenv

# Load environment variables from .env file if it exists
dotenv.load_dotenv(dotenv.find_dotenv())

def build_app(
    log_level="INFO", 
    log_to_file=False, 
    log_file_path=None
) -> FastAPI:
    """
    Builds the FastAPI application with necessary configurations and proxies.

    Parameters
    ----------
    log_level : str, optional
        The logging level to use, by default "INFO". Options include "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL".
        This controls the verbosity of the logs.
        For example, "DEBUG" will log all messages, while "ERROR" will only log error messages.
        See https://docs.python.org/3/library/logging.html#levels for more details.
        Note that the log level can also be set via the environment variable `LOG_LEVEL`.
        If not set, it defaults to "INFO".
        If you want to set the log level via the environment variable, you can do so by
        exporting `LOG_LEVEL=DEBUG` in your terminal before running the application.
        This will override the default log level set in the code.
    log_to_file : bool, optional
        Whether to log to a file, by default False.
        If True, logs will be written to a file specified by `log_file_path`.
        If False, logs will only be printed to the console.
        Note that if `log_to_file` is True and `log_file_path` is None, the logs will be written to a default location.
        The default log file location is `~/.petal-app-manager/logs/app.log`.
        You can change this default location by setting the `log_file_path` parameter.
    log_file_path : _type_, optional
        The path to the log file, by default None.

    Returns
    -------
    FastAPI
        The FastAPI application instance with configured routers and proxies.
    """

    # Set up logging
    log_file = None
    if log_to_file:
        if log_file_path:
            log_file = Path(log_file_path)
        else:
            # Default log location
            log_file = Path(os.path.expanduser("~/.petal-app-manager/logs/app.log"))
    
    logger = setup_logging(log_level=log_level, log_file=log_file)
    logger.info("Starting Petal App Manager")


    app = FastAPI(title="PetalAppManager")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:4200"],  # Your Angular app's origin
        allow_credentials=True,
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
    )

    # ---------- start proxies ----------
    proxies = {
        "ext_mavlink": external.MavLinkExternalProxy("udp:127.0.0.1:14551"),
        # "cloud"  : cloud.CloudProxy(),
        "redis"  : redis.RedisProxy(),
        "db"     : localdb.LocalDBProxy(),
    }
    for p in proxies.values():
        app.add_event_handler("startup", p.start)
        app.add_event_handler("shutdown", p.stop)

    # ---------- core routers ----------
    app.include_router(health.router)
    app.include_router(proxy_info.router, prefix="/debug")

    # ---------- dynamic plugins ----------
    load_petals(app, proxies)

    return app

# Allow configuration through environment variables
log_level = os.environ.get("PETAL_LOG_LEVEL", "INFO")
log_to_file = os.environ.get("PETAL_LOG_TO_FILE", "").lower() in ("true", "1", "yes")
log_file_path = os.environ.get("PETAL_LOG_FILE_PATH", None)

app = build_app(
    log_level=log_level, 
    log_to_file=log_to_file, 
    log_file_path=log_file_path
)
