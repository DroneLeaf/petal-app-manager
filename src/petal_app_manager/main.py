from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # Add this import
from .proxies import cloud, localdb, redis, external
from .plugins.loader import load_petals
from .api import health, proxy_info
import logging

from .logger import setup_logging
from pathlib import Path
import os
import dotenv

import json

from contextlib import asynccontextmanager

# Load environment variables from .env file if it exists
dotenv.load_dotenv(dotenv.find_dotenv())

def build_app(
    log_level="INFO", 
    log_to_file=False, 
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
    logger = setup_logging(
        log_level=log_level,
        app_prefixes=(
            # main app + sub-modules
            "localdbproxy",
            "mavlinkparser",        # also covers mavlinkparser.blockingparser
            "redisproxy",
            "pluginsloader",
            # external “petal_*” plug-ins and friends
            "petal_",               # petal_flight_log, petal_hello_world, …
            "leafsdk",              # leaf-SDK core
        ),
        log_to_file=log_to_file,
    )
    logger.info("Starting Petal App Manager")
    
    with open (os.path.join(Path(__file__).parent.parent.parent, "config.json"), "r") as f:
        config = json.load(f)

    allowed_origins = config.get("allowed_origins", ["*"])  # Default to allow all origins if not specified

    app = FastAPI(title="PetalAppManager")
    # Add CORS middleware to allow all origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,  # Allow origins from the JSON file
        allow_credentials=False,  # Cannot use credentials with wildcard origin
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
    )

    # ---------- start proxies ----------
    proxies = {
        "ext_mavlink": external.MavLinkExternalProxy(endpoint=os.environ.get("MAVLINK_ENDPOINT", "udp:127.0.0.1:14551"),
                                                     baud=int(os.environ.get("MAVLINK_BAUD", 115200)),
                                                     maxlen=int(os.environ.get("MAVLINK_MAXLEN", 200))),
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
    # Set up the logger for the plugins loader
    loader_logger = logging.getLogger("pluginsloader")
    petals = load_petals(app, proxies, logger=loader_logger)

    for petal in petals:
        # Register the petal's shutdown methods
        app.add_event_handler("shutdown", petal.shutdown)

    return app

# Allow configuration through environment variables
log_level = os.environ.get("PETAL_LOG_LEVEL", "INFO")
log_to_file = os.environ.get("PETAL_LOG_TO_FILE", "").lower() in ("true", "1", "yes")

app = build_app(
    log_level=log_level, 
    log_to_file=log_to_file, 
)
