from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # Add this import
from fastapi.staticfiles import StaticFiles  # Add this import
from .proxies import CloudDBProxy, LocalDBProxy, RedisProxy, MavLinkExternalProxy, MavLinkFTPProxy, S3BucketProxy, MQTTProxy

from .plugins.loader import load_petals
from .api import health, proxy_info, cloud_api, bucket_api, mavftp_api, mqtt_api, config_api, admin_ui
from . import api
import logging

from .logger import setup_logging
from pathlib import Path
import os
import dotenv

import json
import yaml

from contextlib import asynccontextmanager
from . import Config
from .config import load_proxies_config

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
            "petalappmanager",
            "petalappmanagerapi",
            "localdbproxy",
            "mavlinkexternalproxy",
            "mavlinkftpproxy",        # also covers mavlinkftpproxy.blockingparser
            "redisproxy",
            "clouddbproxy",
            "mqttproxy",
            "s3bucketproxy",
            "pluginsloader",
            # external “petal_*” plug-ins and friends
            "petal_",               # petal_flight_log, petal_hello_world, …
            "leafsdk",              # leaf-SDK core
        ),
        log_to_file=log_to_file,
        level_outputs=Config.get_log_level_outputs(),
    )
    logger.info("Starting Petal App Manager")
    
    with open (os.path.join(Path(__file__).parent.parent.parent, "config.json"), "r") as f:
        config = json.load(f)

    allowed_origins = config.get("allowed_origins", ["*"])  # Default to allow all origins if not specified

    app = FastAPI(title="PetalAppManager")
    
    # Mount static files for admin dashboard assets
    assets_path = Path(__file__).parent / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")
    
    # Add CORS middleware to allow all origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,  # Allow origins from the JSON file
        allow_credentials=False,  # Cannot use credentials with wildcard origin
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
    )
    # ---------- load enabled proxies from YAML ----------
    proxies_yaml_path = Path(__file__).parent.parent.parent / "proxies.yaml"
    proxies_config = load_proxies_config(proxies_yaml_path)
    enabled_proxies = set(proxies_config.get("enabled_proxies") or [])
    proxy_dependencies = proxies_config.get("proxy_dependencies", {})

    # ---------- start proxies ----------
    proxies = {}

    # Helper function to check if proxy dependencies are met
    def can_load_proxy(proxy_name, loaded_proxies, dependencies):
        required_deps = dependencies.get(proxy_name, [])
        return all(dep in loaded_proxies for dep in required_deps)

    # Load proxies in dependency order
    remaining_proxies = enabled_proxies.copy()
    max_iterations = len(remaining_proxies) * 2  # Prevent infinite loop
    iteration = 0
    
    while remaining_proxies and iteration < max_iterations:
        iteration += 1
        loaded_this_iteration = []
        
        for proxy_name in list(remaining_proxies):
            if can_load_proxy(proxy_name, proxies, proxy_dependencies):
                if proxy_name == "ext_mavlink":
                    proxies["ext_mavlink"] = MavLinkExternalProxy(
                        endpoint=Config.MAVLINK_ENDPOINT,
                        baud=Config.MAVLINK_BAUD,
                        maxlen=Config.MAVLINK_MAXLEN
                    )
                elif proxy_name == "redis":
                    proxies["redis"] = RedisProxy(
                        host=Config.REDIS_HOST,
                        port=Config.REDIS_PORT,
                        db=Config.REDIS_DB,
                        password=Config.REDIS_PASSWORD,
                        unix_socket_path=Config.REDIS_UNIX_SOCKET_PATH,
                    )
                elif proxy_name == "db":
                    proxies["db"] = LocalDBProxy(
                        host=Config.LOCAL_DB_HOST,
                        port=Config.LOCAL_DB_PORT,
                        get_data_url=Config.GET_DATA_URL,
                        scan_data_url=Config.SCAN_DATA_URL,
                        update_data_url=Config.UPDATE_DATA_URL,
                        set_data_url=Config.SET_DATA_URL,
                    )
                elif proxy_name == "mqtt" and "db" in proxies:
                    proxies["mqtt"] = MQTTProxy(
                        local_db_proxy=proxies.get("db"),  # May be None if db not loaded
                        ts_client_host=Config.TS_CLIENT_HOST,
                        ts_client_port=Config.TS_CLIENT_PORT,
                        callback_host=Config.CALLBACK_HOST,
                        callback_port=Config.CALLBACK_PORT,
                        enable_callbacks=Config.ENABLE_CALLBACKS,
                    )
                elif proxy_name == "cloud" and "db" in proxies:
                    proxies["cloud"] = CloudDBProxy(
                        endpoint=Config.CLOUD_ENDPOINT,
                        local_db_proxy=proxies.get("db"),  # May be None if db not loaded
                        access_token_url=Config.ACCESS_TOKEN_URL,
                        session_token_url=Config.SESSION_TOKEN_URL,
                        s3_bucket_name=Config.S3_BUCKET_NAME,
                        get_data_url=Config.GET_DATA_URL,
                        scan_data_url=Config.SCAN_DATA_URL,
                        update_data_url=Config.UPDATE_DATA_URL,
                        set_data_url=Config.SET_DATA_URL,
                    )
                elif proxy_name == "bucket" and "db" in proxies:
                    proxies["bucket"] = S3BucketProxy(
                        session_token_url=Config.SESSION_TOKEN_URL,
                        bucket_name=Config.S3_BUCKET_NAME,
                        local_db_proxy=proxies.get("db"),  # May be None if db not loaded
                        upload_prefix="flight_logs/"
                    )
                elif proxy_name == "ftp_mavlink" and "ext_mavlink" in proxies:
                    proxies["ftp_mavlink"] = MavLinkFTPProxy(mavlink_proxy=proxies["ext_mavlink"])
                else:
                    logger.warning(f"Unknown proxy type or missing dependencies for: {proxy_name}")
                    continue

                loaded_this_iteration.append(proxy_name)
                logger.info(f"Loaded proxy: {proxy_name}")
        
        # Remove loaded proxies from remaining list
        for proxy_name in loaded_this_iteration:
            remaining_proxies.discard(proxy_name)
        
        # If no proxies were loaded this iteration, we're stuck
        if not loaded_this_iteration:
            break
    
    # Log any proxies that couldn't be loaded due to missing dependencies
    if remaining_proxies:
        for proxy_name in remaining_proxies:
            required_deps = proxy_dependencies.get(proxy_name, [])
            missing_deps = [dep for dep in required_deps if dep not in proxies]
            if missing_deps:
                logger.error(f"Cannot load {proxy_name}: missing proxy dependencies {missing_deps}")
            else:
                logger.warning(f"Cannot load {proxy_name}: unknown proxy type or circular dependency")

    for p in proxies.values():
        app.add_event_handler("startup", p.start)
        app.add_event_handler("shutdown", p.stop)

    api.set_proxies(proxies)
    api_logger = logging.getLogger("PetalAppManagerAPI")

    # ---------- core routers ----------
    # Set the logger for health check endpoints
    health._set_logger(api_logger)  # Set the logger for health check endpoints
    app.include_router(health.router)
    # Configure health check with proxy instances
    proxy_info._set_logger(api_logger)  # Set the logger for proxy info endpoints
    app.include_router(proxy_info.router, prefix="/debug")
    # Configure cloud API with proxy instances
    cloud_api._set_logger(api_logger)  # Set the logger for cloud API endpoints
    app.include_router(cloud_api.router, prefix="/cloud")
    # Configure bucket API with proxy instances
    bucket_api._set_logger(api_logger)  # Set the logger for bucket API endpoints
    app.include_router(bucket_api.router, prefix="/test")
    # Configure MAVLink FTP API with proxy instances
    mavftp_api._set_logger(api_logger)  # Set the logger for MAVLink FTP API endpoints
    app.include_router(mavftp_api.router, prefix="/mavftp")
    
    # Configure configuration management API
    config_api._set_logger(api_logger)  # Set the logger for configuration API endpoints
    app.include_router(config_api.router)
    
    # Configure admin UI (separate from FastAPI docs)
    admin_ui._set_logger(api_logger)  # Set the logger for admin UI endpoints
    app.include_router(admin_ui.router)
    # Configure MQTT API with proxy instances
    mqtt_api._set_logger(api_logger)  # Set the logger for MQTT API endpoints
    app.include_router(mqtt_api.router, prefix="/mqtt")

    # ---------- dynamic plugins ----------
    # Set up the logger for the plugins loader
    loader_logger = logging.getLogger("pluginsloader")
    petals = load_petals(app, proxies, logger=loader_logger)

    for petal in petals:
        # Register the petal's shutdown methods
        app.add_event_handler("shutdown", petal.shutdown)

    return app

# Allow configuration through environment variables
log_level = Config.PETAL_LOG_LEVEL
log_to_file = Config.PETAL_LOG_TO_FILE

app = build_app(
    log_level=log_level, 
    log_to_file=log_to_file, 
)
