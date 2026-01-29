from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # Add this import
from fastapi.staticfiles import StaticFiles  # Add this import

import logging
import asyncio
from typing import Optional

from pathlib import Path
import os
import dotenv

import json
import yaml
import time
from datetime import datetime

from contextlib import asynccontextmanager

from petal_app_manager.plugins.loader import startup_petals

def build_app() -> FastAPI:
    """
    Builds the FastAPI application with necessary configurations and proxies.

    Returns
    -------
    FastAPI
        The FastAPI application instance with configured routers and proxies.
    """

    from . import Config
    from .proxies import CloudDBProxy, LocalDBProxy, RedisProxy, MavLinkExternalProxy, MavLinkFTPProxy, S3BucketProxy, MQTTProxy
    from .api import health, proxy_info, cloud_api, bucket_api, mavftp_api, mqtt_api, config_api
    from . import api
    from .logger import setup_logging
    from .organization_manager import get_organization_manager
    from .config import load_proxies_config

    # Allow configuration through environment variables
    log_level = Config.PETAL_LOG_LEVEL 
    log_to_file = Config.PETAL_LOG_TO_FILE

    # Set up logging
    logger = setup_logging(
        log_level=log_level,
        base_dir=Config.PETAL_LOG_DIR,
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
                        source_system_id=Config.MAVLINK_SOURCE_SYSTEM_ID,
                        source_component_id=Config.MAVLINK_SOURCE_COMPONENT_ID,
                        maxlen=Config.MAVLINK_MAXLEN,
                        mavlink_worker_sleep_ms=Config.MAVLINK_WORKER_SLEEP_MS,
                        mavlink_heartbeat_send_frequency=Config.MAVLINK_HEARTBEAT_SEND_FREQUENCY,
                        root_sd_path=Config.ROOT_SD_PATH,
                        worker_threads=Config.MAVLINK_WORKER_THREADS
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
                elif proxy_name == "mqtt":
                    proxies["mqtt"] = MQTTProxy(
                        ts_client_host=Config.TS_CLIENT_HOST,
                        ts_client_port=Config.TS_CLIENT_PORT,
                        callback_host=Config.CALLBACK_HOST,
                        callback_port=Config.CALLBACK_PORT,
                        enable_callbacks=Config.ENABLE_CALLBACKS,
                        command_edge_topic=Config.COMMAND_EDGE_TOPIC,
                        response_topic=Config.RESPONSE_TOPIC,
                        test_topic=Config.TEST_TOPIC,
                        command_web_topic=Config.COMMAND_WEB_TOPIC,
                        health_check_interval=Config.MQTT_HEALTH_CHECK_INTERVAL,
                    )
                elif proxy_name == "cloud":
                    proxies["cloud"] = CloudDBProxy(
                        endpoint=Config.CLOUD_ENDPOINT,
                        access_token_url=Config.ACCESS_TOKEN_URL,
                        session_token_url=Config.SESSION_TOKEN_URL,
                        s3_bucket_name=Config.S3_BUCKET_NAME,
                        get_data_url=Config.GET_DATA_URL,
                        scan_data_url=Config.SCAN_DATA_URL,
                        update_data_url=Config.UPDATE_DATA_URL,
                        set_data_url=Config.SET_DATA_URL,
                    )
                elif proxy_name == "bucket":
                    proxies["bucket"] = S3BucketProxy(
                        session_token_url=Config.SESSION_TOKEN_URL,
                        bucket_name=Config.S3_BUCKET_NAME,
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

    # Note: Proxy startup will be handled in startup_all() after OrganizationManager is ready
    # for p in proxies.values():
    #     app.add_event_handler("startup", p.start)
    #     # Note: proxy shutdown handlers will be registered later in shutdown_all

    # ---------- dynamic plugins ----------
    # Set up the logger for the plugins loader
    loader_logger = logging.getLogger("pluginsloader")
   
    # Store petals list to manage them during startup/shutdown
    petals = []
    
    # Track petals currently being loaded (for health reporting)
    loading_petals: set = set()
    
    # Health status publisher task
    health_publisher_task = None
    
    # Background petal loading task
    background_petal_loader_task = None
    
    async def publish_health_status():
        """Background task to publish health status to Redis channel."""
        redis_proxy = proxies.get("redis")
        if not redis_proxy:
            logger.warning("Redis proxy not available for health status publishing")
            return
            
        logger.info(f"Starting health status publisher (interval: {Config.REDIS_HEALTH_MESSAGE_RATE}s)")
        
        # Import the unified health service
        from .health_service import get_health_service
        health_service = get_health_service(logger)
        
        # Get petal names from config
        startup_petal_names = list(proxies_config.get("startup_petals") or [])
        enabled_petal_names = list(proxies_config.get("enabled_petals") or [])
            
        while True:
            try:
                # Get validated health message using unified service (with petal info)
                health_message = await health_service.get_health_message(
                    proxies_dict=proxies,
                    petals_list=petals,
                    startup_petal_names=startup_petal_names,
                    enabled_petal_names=enabled_petal_names,
                    loading_petal_names=list(loading_petals)
                )
                
                # Publish to Redis channel
                channel = "/controller-dashboard/petals-status"
                message_json = health_message.model_dump_json(indent=2)
                
                # Use the publish method from Redis proxy
                result = redis_proxy.publish(channel, message_json)
                
                if result > 0:
                    logger.debug(f"Published health status to {channel} ({result} subscribers)")
                else:
                    logger.debug(f"Published health status to {channel} (no subscribers)")
                
            except Exception as e:
                logger.error(f"Error publishing health status: {e}")
            
            # Wait for the configured interval
            await asyncio.sleep(Config.REDIS_HEALTH_MESSAGE_RATE)
    
    async def startup_all():
        """Initialize OrganizationManager, then start proxies, then load petals"""
        nonlocal health_publisher_task
        
        # Step 0: Initialize health service with logger
        from .health_service import set_health_service_logger
        set_health_service_logger(logger)
        
        # Step 1: Start OrganizationManager first
        logger.info("Starting OrganizationManager...")
        org_manager = get_organization_manager()
        await org_manager.start()
        
        # Step 2: Start proxies after OrganizationManager is ready
        logger.info("Starting proxies...")
        # start MQTT proxy, then Mavlink external proxy then FTP proxies last to ensure they have org info
        order = {'mqtt': 0, 'ext_mavlink': 1, 'ftp_mavlink': 2}

        sorted_proxies = dict(
            sorted(
                proxies.items(),
                key=lambda kv: (kv[0] in order, order.get(kv[0], 0))
            )
        )
        for proxy_name, proxy in sorted_proxies.items():
            try:
                await proxy.start()
                logger.info(f"Started proxy: {proxy_name}")
            except Exception as e:
                logger.error(f"Failed to start proxy {proxy_name}: {e}")
                logger.warning(f"Proxy {proxy_name} will retry connection on demand")
        
        # Step 3: Load petals after proxies are started
        await load_petals_on_startup()
        
        # Step 4: Start health status publisher if Redis is available
        if "redis" in proxies:
            logger.info("Starting health status publisher...")
            health_publisher_task = asyncio.create_task(publish_health_status())
            logger.info("Health status publisher started")
        else:
            logger.warning("Redis proxy not available, health status publisher not started")
        
        # Step 5: Start background loading of enabled petals (non-blocking)
        logger.info("Spawning background task to load enabled petals...")
        background_petal_loader_task = asyncio.create_task(load_enabled_petals_background())
        
        # Step 6: Log completion
        logger.info("============================================")
        logger.info("=== STARTUP_ALL() COMPLETED SUCCESSFULLY ===")
        logger.info("============================================")
        logger.info("=" * 80)
        logger.info("=" * 80)
        logger.info("===                                                                          ===")
        logger.info("===          🚀 APPLICATION IS NOW READY TO RECEIVE REQUESTS 🚀              ===")
        logger.info("===                                                                          ===")
        logger.info("=" * 80)
        logger.info("=" * 80)
        logger.info("Enabled petals will continue loading in the background...")
    
    from .plugins.loader import load_petals, initialize_petals, startup_petals

    async def load_petals_on_startup():
        """Load startup petals during server initialization (blocking)"""
        nonlocal petals
        critical_petals = list(proxies_config.get("startup_petals") or [])
        
        if not critical_petals:
            logger.info("No startup petals configured")
            return
            
        logger.info(f"Loading {len(critical_petals)} startup petals: {critical_petals}")
        
        new_petals = load_petals(
            app=app, 
            petal_name_list=critical_petals, 
            proxies=proxies, 
            logger=loader_logger
        )
        petals.extend(new_petals)
        
        # Handle async startup for each petal
        for petal in new_petals:
            await _handle_petal_async_startup(petal)
        
        logger.info(f"Startup petals loaded: {len(new_petals)}/{len(critical_petals)}")

    async def load_enabled_petals_background():
        """Load enabled petals in background after server startup (non-blocking)"""
        nonlocal petals
        
        # Small delay to ensure server is fully ready
        await asyncio.sleep(0.5)
        
        # Get list of already loaded petal names
        loaded_petal_names = {p.name for p in petals}
        
        # Get enabled petals from config
        enabled_petals_list = list(proxies_config.get("enabled_petals") or [])
        
        # Filter out already loaded petals (startup_petals may overlap with enabled_petals)
        petals_to_load = [p for p in enabled_petals_list if p not in loaded_petal_names]
        
        if not petals_to_load:
            logger.info("No additional enabled petals to load in background")
            return
        
        logger.info(f"Background loading {len(petals_to_load)} enabled petals: {petals_to_load}")
        
        for petal_name in petals_to_load:
            try:
                # Mark petal as loading (for health reporting)
                loading_petals.add(petal_name)
                
                # Run initialization in a separate thread (sequentially)
                petal_list = await asyncio.to_thread(
                    initialize_petals,
                    petal_name_list=[petal_name],
                    proxies=proxies,
                    logger=loader_logger
                )
                
                new_petals = startup_petals(
                    app=app,
                    petal_list=petal_list,
                    logger=loader_logger
                )

                # Small delay between loads to prevent resource contention
                await asyncio.sleep(0.1)
                
                if new_petals:
                    petals.extend(new_petals)
                    
                    # Clear cached OpenAPI schema so new routes appear in /docs
                    app.openapi_schema = None
                    
                    # Handle async startup for newly loaded petal
                    for petal in new_petals:
                        await _handle_petal_async_startup(petal)
                    
                    logger.info(f"Background loaded petal '{petal_name}' successfully")
                else:
                    logger.warning(f"Background loading failed for petal '{petal_name}'")
                    
            except Exception as e:
                logger.error(f"Error background loading petal '{petal_name}': {e}")
            finally:
                # Remove from loading set regardless of success/failure
                loading_petals.discard(petal_name)
        
        logger.info(f"Background petal loading completed. Total petals: {len(petals)}")

    async def _handle_petal_async_startup(petal):
        """Handle async startup for a single petal including dependency setup"""
        async_startup_method = getattr(petal, 'async_startup', None)
        if not async_startup_method or not asyncio.iscoroutinefunction(async_startup_method):
            return
        
        logger.info(f"Starting async_startup for petal: {petal.name}")
        
        # Get petal dependencies from YAML
        petal_dependencies = proxies_config.get("petal_dependencies", {})
        petal_deps = petal_dependencies.get(petal.name, [])
        uses_mqtt = 'mqtt' in petal_deps
        uses_cloud = 'cloud' in petal_deps
        
        # Set the event loop for safe task creation
        try:
            petal._loop = asyncio.get_running_loop()
        except RuntimeError:
            petal._loop = asyncio.get_event_loop()
        
        # Handle MQTT proxy dependency
        if uses_mqtt:
            logger.info(f"Petal {petal.name} depends on MQTT proxy, setting up MQTT-aware startup...")
            try:
                await _setup_mqtt_for_petal(petal)
                logger.info(f"Completed MQTT setup for petal: {petal.name}")
            except Exception as e:
                logger.error(f"Error during MQTT setup for petal {petal.name}: {e}")
                logger.warning(f"MQTT setup will continue in background for petal {petal.name}")
        
        # Handle Cloud proxy dependency
        if uses_cloud:
            logger.info(f"Petal {petal.name} depends on Cloud proxy, setting up Cloud-aware startup...")
            try:
                await _setup_cloud_for_petal(petal)
                logger.info(f"Completed Cloud setup for petal: {petal.name}")
            except Exception as e:
                logger.error(f"Error during Cloud setup for petal {petal.name}: {e}")
                logger.warning(f"Cloud setup will continue in background for petal {petal.name}")
        
        # Standard async startup
        try:
            await async_startup_method()
            logger.info(f"Completed async_startup for petal: {petal.name}")
        except Exception as e:
            logger.error(f"Error during async_startup for petal {petal.name}: {e}")
            logger.warning(f"Petal {petal.name} async_startup failed, but server will continue")
    
    async def _setup_mqtt_for_petal(petal):
        """Setup MQTT proxy for petal with organization ID monitoring and retry logic."""
        logger.info(f"Setting up MQTT for petal: {petal.name}")
        
        mqtt_proxy = proxies.get('mqtt')
        if not mqtt_proxy:
            logger.warning(f"MQTT proxy not available for petal {petal.name}, skipping MQTT setup")
            return
        
        # Try to get organization ID
        logger.info(f"Checking for organization ID availability for petal {petal.name}...")
        organization_id = mqtt_proxy._get_organization_id()
        
        if organization_id:
            # Organization ID is available
            logger.info(f"Organization ID available: {organization_id}")
            
            # Try to start/reconnect MQTT proxy if not connected
            if not mqtt_proxy.is_connected:
                logger.info(f"MQTT proxy not connected, attempting to start...")
                try:
                    # Add timeout to prevent freezing
                    await asyncio.wait_for(mqtt_proxy.start(), timeout=Config.MQTT_STARTUP_TIMEOUT)
                    logger.info(f"MQTT proxy started successfully for petal {petal.name}")
                except asyncio.TimeoutError:
                    logger.error(f"Timeout waiting for MQTT proxy to start")
                    logger.info(f"Starting MQTT monitoring task for petal {petal.name}...")
                    petal._loop.create_task(_monitor_mqtt_connection(petal, mqtt_proxy))
                    return
                except Exception as e:
                    logger.error(f"Failed to start MQTT proxy: {e}")
                    logger.info(f"Starting MQTT monitoring task for petal {petal.name}...")
                    petal._loop.create_task(_monitor_mqtt_connection(petal, mqtt_proxy))
                    return
            
            # Setup MQTT topics for petal
            setup_mqtt_topics_method = getattr(petal, '_setup_mqtt_topics', None)
            if setup_mqtt_topics_method and asyncio.iscoroutinefunction(setup_mqtt_topics_method):
                await setup_mqtt_topics_method()
                logger.info(f"MQTT topics setup completed for petal: {petal.name}")
            else:
                logger.debug(f"Petal {petal.name} has no _setup_mqtt_topics method")
        else:
            # Organization ID not available yet - start monitoring
            logger.info(f"Organization ID not yet available for {petal.name}, starting monitoring task...")
            petal._loop.create_task(_monitor_mqtt_connection(petal, mqtt_proxy))
        
        logger.info(f"MQTT setup completed for petal: {petal.name}")
    
    async def _setup_cloud_for_petal(petal):
        """Setup Cloud proxy for petal with organization ID monitoring and retry logic."""
        logger.info(f"Setting up Cloud proxy for petal: {petal.name}")
        
        cloud_proxy = proxies.get('cloud')
        if not cloud_proxy:
            logger.warning(f"Cloud proxy not available for petal {petal.name}, skipping Cloud setup")
            return
        
        org_manager = get_organization_manager()
        organization_id = org_manager.organization_id
        
        if organization_id:
            # Organization ID is available - try to connect to cloud
            logger.info(f"Organization ID available: {organization_id}")
            
            try:
                # Try to get access token to verify connection (with timeout)
                await asyncio.wait_for(cloud_proxy._get_access_token(), timeout=Config.CLOUD_STARTUP_TIMEOUT)
                logger.info(f"Cloud proxy connection verified for petal {petal.name}")
                
                # Setup cloud-specific petal functionality if needed
                setup_cloud_method = getattr(petal, '_setup_cloud', None)
                if setup_cloud_method and asyncio.iscoroutinefunction(setup_cloud_method):
                    await setup_cloud_method()
                    logger.info(f"Cloud setup completed for petal: {petal.name}")
                else:
                    logger.debug(f"Petal {petal.name} has no _setup_cloud method")
                    
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for Cloud proxy connection")
                logger.info(f"Starting Cloud monitoring task for petal {petal.name}...")
                petal._loop.create_task(_monitor_cloud_connection(petal, cloud_proxy))
            except Exception as e:
                logger.error(f"Failed to connect to Cloud proxy: {e}")
                logger.info(f"Starting Cloud monitoring task for petal {petal.name}...")
                petal._loop.create_task(_monitor_cloud_connection(petal, cloud_proxy))
        else:
            # Organization ID not available yet - start monitoring
            logger.info(f"Organization ID not yet available for {petal.name}, starting Cloud monitoring task...")
            petal._loop.create_task(_monitor_cloud_connection(petal, cloud_proxy))
        
        logger.info(f"Cloud setup completed for petal: {petal.name}")
    
    async def _monitor_mqtt_connection(petal, mqtt_proxy: MQTTProxy):
        """Monitor MQTT connection and retry when organization ID becomes available."""
        logger.info(f"Starting MQTT connection monitoring for petal: {petal.name}")
        retry_interval = Config.MQTT_RETRY_INTERVAL
        
        while True:
            try:
                await asyncio.sleep(retry_interval)
                
                # Check if organization ID is now available
                organization_id = mqtt_proxy._get_organization_id()
                if not organization_id:
                    logger.debug(f"Organization ID still not available for {petal.name}, waiting...")
                    continue
                
                # Organization ID is available - try to subscribe to device topics (connection attempt)
                if not mqtt_proxy.is_connected:
                    logger.info(f"Organization ID available: {organization_id}, attempting to subscribe to MQTT device topics...")
                    try:
                        # Subscribe to device topics - this is the actual connection attempt
                        await asyncio.wait_for(
                            mqtt_proxy._subscribe_to_device_topics(), 
                            timeout=Config.MQTT_SUBSCRIBE_TIMEOUT
                        )
                        mqtt_proxy.is_connected = True
                        logger.info(f"MQTT proxy connected successfully for petal {petal.name}")
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout subscribing to MQTT device topics for {petal.name}")
                        logger.info(f"Will retry in {retry_interval}s...")
                        continue
                    except Exception as e:
                        logger.error(f"Failed to subscribe to MQTT device topics for {petal.name}: {e}")
                        logger.info(f"Will retry in {retry_interval}s...")
                        continue
                
                # MQTT is connected - setup petal-specific topics
                logger.info(f"Setting up MQTT topics for petal {petal.name}...")
                setup_mqtt_topics_method = getattr(petal, '_setup_mqtt_topics', None)
                if setup_mqtt_topics_method and asyncio.iscoroutinefunction(setup_mqtt_topics_method):
                    await setup_mqtt_topics_method()
                    logger.info(f"MQTT topics setup completed for petal: {petal.name}")
                else:
                    logger.debug(f"Petal {petal.name} has no _setup_mqtt_topics method")
                
                # Success - exit monitoring loop
                logger.info(f"MQTT connection monitoring completed for petal: {petal.name}")
                break
                    
            except Exception as e:
                logger.error(f"Error in MQTT connection monitoring for petal {petal.name}: {e}")
                logger.info(f"Will retry in {retry_interval}s...")
                await asyncio.sleep(retry_interval)
    
    async def _monitor_cloud_connection(petal, cloud_proxy):
        """Monitor Cloud connection and retry when organization ID becomes available."""
        logger.info(f"Starting Cloud connection monitoring for petal: {petal.name}")
        retry_interval = Config.CLOUD_RETRY_INTERVAL
        
        while True:
            try:
                await asyncio.sleep(retry_interval)
                
                # Check if organization ID is now available
                org_manager = get_organization_manager()
                organization_id = org_manager.organization_id
                if not organization_id:
                    logger.debug(f"Organization ID still not available for {petal.name}, waiting...")
                    continue
                
                # Organization ID is available - try to connect to cloud
                logger.info(f"Organization ID available: {organization_id}, attempting to connect to Cloud proxy...")
                try:
                    await asyncio.wait_for(cloud_proxy._get_access_token(), timeout=Config.CLOUD_STARTUP_TIMEOUT)
                    logger.info(f"Cloud proxy connection established for petal {petal.name}")
                except asyncio.TimeoutError:
                    logger.error(f"Timeout connecting to Cloud proxy for {petal.name}")
                    logger.info(f"Will retry in {retry_interval}s...")
                    continue
                except Exception as e:
                    logger.error(f"Failed to connect to Cloud proxy for {petal.name}: {e}")
                    logger.info(f"Will retry in {retry_interval}s...")
                    continue
                
                # Cloud is connected - setup cloud functionality
                logger.info(f"Setting up Cloud for petal {petal.name}...")
                setup_cloud_method = getattr(petal, '_setup_cloud', None)
                if setup_cloud_method and asyncio.iscoroutinefunction(setup_cloud_method):
                    await setup_cloud_method()
                    logger.info(f"Cloud setup completed for petal: {petal.name}")
                else:
                    logger.debug(f"Petal {petal.name} has no _setup_cloud method")
                
                # Success - exit monitoring loop
                logger.info(f"Cloud connection monitoring completed for petal: {petal.name}")
                break
                    
            except Exception as e:
                logger.error(f"Error in Cloud connection monitoring for petal {petal.name}: {e}")
                logger.info(f"Will retry in {retry_interval}s...")
                await asyncio.sleep(retry_interval)

    async def shutdown_petals():
        """Shutdown petals gracefully"""
        for petal in petals:
            async_shutdown_method = getattr(petal, 'async_shutdown', None)
            if async_shutdown_method and asyncio.iscoroutinefunction(async_shutdown_method):
                await async_shutdown_method()

    async def shutdown_all():
        """Shutdown petals first, then proxies, then OrganizationManager"""
        logger.info("Starting graceful shutdown...")
        
        # Step 1: Stop background petal loader task
        if background_petal_loader_task and not background_petal_loader_task.done():
            logger.info("Stopping background petal loader...")
            background_petal_loader_task.cancel()
            try:
                await background_petal_loader_task
            except asyncio.CancelledError:
                pass
            logger.info("Background petal loader stopped")
        
        # Step 2: Stop health publisher task
        if health_publisher_task and not health_publisher_task.done():
            logger.info("Stopping health status publisher...")
            health_publisher_task.cancel()
            try:
                await health_publisher_task
            except asyncio.CancelledError:
                pass
            logger.info("Health status publisher stopped")
        
        # Step 2: Shutdown petals first (async shutdown if available)
        logger.info("Shutting down petals (async)...")
        await shutdown_petals()
        
        # Step 3: Shutdown petals (sync shutdown)
        logger.info("Shutting down petals (sync)...")
        for petal in petals:
            try:
                petal.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down petal {getattr(petal, 'name', 'unknown')}: {e}")
        
        # Step 4: Shutdown proxies
        logger.info("Shutting down proxies...")
        for proxy_name, proxy in proxies.items():
            try:
                await proxy.stop()
                logger.info(f"Shutdown proxy: {proxy_name}")
            except Exception as e:
                logger.error(f"Error shutting down proxy {proxy_name}: {e}")
        
        # Step 5: Shutdown OrganizationManager last
        logger.info("Shutting down OrganizationManager...")
        try:
            org_manager = get_organization_manager()
            await org_manager.stop()
            logger.info("OrganizationManager shutdown completed")
        except Exception as e:
            logger.error(f"Error shutting down OrganizationManager: {e}")
        
        logger.info("Graceful shutdown completed")

    # Create lifespan context manager for proper startup/shutdown handling
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """FastAPI lifespan context manager to handle startup and shutdown properly"""
        # Startup
        logger.info("Starting FastAPI lifespan...")
        await startup_all()
        logger.info("FastAPI lifespan startup completed")
        
        yield
        
        # Shutdown
        logger.info("Starting FastAPI lifespan shutdown...")
        await shutdown_all()
        logger.info("=" * 80)
        logger.info("=" * 80)
        logger.info("===                                                                          ===")
        logger.info("===           🛑 FASTAPI LIFESPAN SHUTDOWN COMPLETED 🛑                      ===")
        logger.info("===                                                                          ===")
        logger.info("=" * 80)
        logger.info("=" * 80)

    # Now create the FastAPI app with the lifespan
    app = FastAPI(title="PetalAppManager", lifespan=lifespan)
    
    # Add CORS middleware to allow all origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,  # Allow origins from the JSON file
        allow_credentials=False,  # Cannot use credentials with wildcard origin
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
    )

    # Configure API proxies and routers
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
    
    # Configure MQTT API with proxy instances
    mqtt_api._set_logger(api_logger)  # Set the logger for MQTT API endpoints
    app.include_router(mqtt_api.router, prefix="/mqtt")
    
    # Register MQTT callback router if MQTT proxy is enabled and has callbacks enabled
    mqtt_proxy = proxies.get("mqtt")
    if mqtt_proxy and mqtt_proxy.callback_router:
        app.include_router(mqtt_proxy.callback_router, prefix="/mqtt-callback")
        logger.info("Registered MQTT callback router at /mqtt-callback")

    return app

app = build_app()
