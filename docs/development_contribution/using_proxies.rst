Using Proxies in Petals
========================

Proxies provide a standardized interface for petals to access backend services like databases, message queues, cloud services, and external protocols. This guide explains how to use each available proxy type in your petal development.

Overview
--------

Proxies abstract complex backend integrations and provide:

- **Consistent API**: Uniform interface across different services
- **Dependency Management**: Automatic service availability checking
- **Error Handling**: Standardized error responses and retry logic
- **Configuration**: Centralized service configuration
- **Health Monitoring**: Built-in health checks and status reporting

Available Proxy Types
---------------------

.. list-table:: Proxy Types and Use Cases
   :header-rows: 1
   :widths: 25 75

   * - Proxy Type
     - Use Cases
   * - RedisProxy
     - Caching, pub/sub messaging, session storage, real-time data
   * - MavlinkExternalProxy
     - Drone communication, telemetry, command/control, MAVLink protocol
   * - CloudDBProxy
     - Cloud database operations, persistent storage, data synchronization
   * - LocalDBProxy
     - Local database operations, offline storage, edge computing
   * - S3BucketProxy
     - File storage, log uploads, data archiving, content delivery
   * - MQTTProxy
     - IoT messaging, device communication, event streaming

Accessing Proxies in Your Petal
--------------------------------

**Basic Pattern:**

.. code-block:: python

   from petal_app_manager.plugins.base import Petal
   from petal_app_manager.proxies.redis import RedisProxy

   class YourPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["redis", "ext_mavlink"]  # Declare dependencies
       
       async def your_method(self):
           # Get proxy instance
           redis_proxy: RedisProxy = self.get_proxy("redis")
           
           # Use proxy methods
           await redis_proxy.set("key", "value")
           result = await redis_proxy.get("key")

RedisProxy
----------

**Purpose:** High-performance caching, pub/sub messaging, session management

**Common Use Cases:**

- Caching telemetry data
- Real-time message passing between petals
- Session and state management
- Temporary data storage
- Scanning keys by pattern for job management

**Basic Usage:**

.. code-block:: python

   from petal_app_manager.proxies.redis import RedisProxy

   class YourPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["redis"]
       
       async def cache_telemetry(self, data: dict):
           redis_proxy: RedisProxy = self.get_proxy("redis")
           
           # Store data with expiration
           await redis_proxy.set("telemetry:latest", json.dumps(data), ex=60)
           
           # Retrieve data
           cached = await redis_proxy.get("telemetry:latest")

**Methods:**

.. code-block:: python

   # Basic key-value operations
   await redis_proxy.set(key, value, ex=expiration_seconds)
   await redis_proxy.get(key)
   await redis_proxy.delete(key)
   await redis_proxy.exists(key)
   
   # Hash operations
   await redis_proxy.hset(hash_key, field, value)
   await redis_proxy.hget(hash_key, field)
   await redis_proxy.hgetall(hash_key)
   
   # List operations
   await redis_proxy.lpush(list_key, value)
   await redis_proxy.rpush(list_key, value)
   await redis_proxy.lrange(list_key, start, end)
   
   # Pub/Sub messaging
   await redis_proxy.publish(channel, message)
   await redis_proxy.subscribe(channel, callback)
   
   # Key scanning (useful for job management)
   await redis_proxy.scan_keys(pattern="job:*", count=100)

**Scan Keys Example (Job Management):**

.. code-block:: python

   from petal_app_manager.proxies.redis import RedisProxy

   class JobManagerPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["redis"]
       
       async def list_pending_jobs(self):
           """Find all pending jobs using key pattern scanning."""
           redis_proxy: RedisProxy = self.get_proxy("redis")
           
           # Scan for all job keys matching pattern
           job_keys = await redis_proxy.scan_keys(
               pattern="job:pending:*",
               count=100  # Keys per scan iteration
           )
           
           jobs = []
           for key in job_keys:
               job_data = await redis_proxy.get(key)
               if job_data:
                   jobs.append(json.loads(job_data))
           
           return jobs
       
       async def cleanup_expired_jobs(self, max_age_hours: int = 24):
           """Clean up old job entries."""
           redis_proxy: RedisProxy = self.get_proxy("redis")
           
           # Find all completed job keys
           completed_keys = await redis_proxy.scan_keys(pattern="job:completed:*")
           
           deleted = 0
           for key in completed_keys:
               job_data = await redis_proxy.get(key)
               if job_data:
                   job = json.loads(job_data)
                   # Check if job is older than max_age
                   if self._is_expired(job.get("completed_at"), max_age_hours):
                       await redis_proxy.delete(key)
                       deleted += 1
           
           self.logger.info(f"Cleaned up {deleted} expired jobs")
           return {"deleted": deleted}
       
       async def get_job_statistics(self):
           """Get counts of jobs by status."""
           redis_proxy: RedisProxy = self.get_proxy("redis")
           
           stats = {}
           for status in ["pending", "processing", "completed", "failed"]:
               keys = await redis_proxy.scan_keys(pattern=f"job:{status}:*")
               stats[status] = len(keys)
           
           return stats

**Caching Pattern Example:**

.. code-block:: python

   class TelemetryCachePetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["redis"]
       
       async def cache_flight_data(self, flight_id: str, data: dict):
           """Cache flight telemetry with TTL."""
           redis_proxy: RedisProxy = self.get_proxy("redis")
           
           key = f"flight:{flight_id}:telemetry"
           await redis_proxy.set(key, json.dumps(data), ex=3600)  # 1 hour TTL
       
       async def get_cached_flight_data(self, flight_id: str) -> Optional[dict]:
           """Retrieve cached flight data."""
           redis_proxy: RedisProxy = self.get_proxy("redis")
           
           key = f"flight:{flight_id}:telemetry"
           cached = await redis_proxy.get(key)
           
           if cached:
               return json.loads(cached)
           return None

MavlinkExternalProxy
--------------------

**Purpose:** Communication with drones and autopilots using MAVLink protocol

**Common Use Cases:**

- Sending commands to drone
- Receiving telemetry data
- Mission management
- Parameter configuration (including bulk operations over lossy links)
- Real-time monitoring
- Autopilot reboot and system control

**Basic Usage:**

.. code-block:: python

   from petal_app_manager.proxies.external import MavLinkExternalProxy

   class YourPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["ext_mavlink"]
       
       async def send_command(self):
           mavlink_proxy: MavLinkExternalProxy = self.get_proxy("ext_mavlink")
           
           # Reboot the autopilot
           result = await mavlink_proxy.reboot_autopilot()
           if result.success:
               print("Autopilot rebooting...")

**Methods:**

.. code-block:: python

   # Reboot autopilot (PX4/ArduPilot)
   await mavlink_proxy.reboot_autopilot(
       reboot_onboard_computer=False,  # Also reboot companion computer
       timeout=3.0                      # Timeout for ACK response
   )
   # Returns: RebootAutopilotResponse with success, status_code, reason
   
   # Bulk parameter setting over lossy links
   await mavlink_proxy.set_params_bulk_lossy(
       params_to_set={
           "NAV_ACC_RAD": 2.0,
           "MPC_XY_VEL_MAX": (12.0, "REAL32"),  # With explicit type
           "COM_DISARM_LAND": {"value": 2, "type": "INT32"}
       },
       timeout_total=8.0,
       max_retries=3,
       max_in_flight=8
   )
   # Returns: Dict of confirmed parameters
   
   # Bulk parameter retrieval over lossy links
   await mavlink_proxy.get_params_bulk_lossy(
       names=["NAV_ACC_RAD", "MPC_XY_VEL_MAX", "COM_DISARM_LAND"],
       timeout_total=6.0,
       max_retries=3,
       max_in_flight=10
   )
   # Returns: Dict with name, value, raw, type, count, index for each param

**Reboot Autopilot Example:**

.. code-block:: python

   from petal_app_manager.proxies.external import MavLinkExternalProxy

   class SystemControlPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["ext_mavlink"]
       
       async def reboot_flight_controller(self, include_companion: bool = False):
           """Reboot the autopilot with proper error handling."""
           mavlink_proxy: MavLinkExternalProxy = self.get_proxy("ext_mavlink")
           
           try:
               result = await mavlink_proxy.reboot_autopilot(
                   reboot_onboard_computer=include_companion,
                   timeout=3.0
               )
               
               if result.success:
                   self.logger.info("Autopilot reboot initiated successfully")
                   return {"status": "rebooting", "reason": result.reason}
               else:
                   self.logger.warning(f"Reboot failed: {result.reason}")
                   return {"status": "failed", "reason": result.reason}
                   
           except RuntimeError as e:
               self.logger.error(f"MAVLink not connected: {e}")
               return {"status": "error", "reason": "MAVLink connection not established"}

**Bulk Parameter Operations Example (Lossy Links):**

.. code-block:: python

   class ParameterConfigPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["ext_mavlink"]
       
       async def configure_flight_parameters(self):
           """Set multiple parameters efficiently over unreliable links."""
           mavlink_proxy: MavLinkExternalProxy = self.get_proxy("ext_mavlink")
           
           # Define parameters to set with optional type hints
           params = {
               # Simple value (type auto-detected)
               "NAV_ACC_RAD": 2.0,
               
               # Tuple format: (value, type_string)
               "MPC_XY_VEL_MAX": (12.0, "REAL32"),
               "MPC_Z_VEL_MAX_UP": (3.0, "REAL32"),
               
               # Dict format with explicit type
               "COM_DISARM_LAND": {"value": 2, "type": "INT32"},
               "COM_ARM_WO_GPS": {"value": 1, "type": "INT32"}
           }
           
           try:
               confirmed = await mavlink_proxy.set_params_bulk_lossy(
                   params_to_set=params,
                   timeout_total=8.0,    # Total operation timeout
                   max_retries=3,        # Retry count per parameter
                   max_in_flight=8,      # Concurrent requests
                   resend_interval=0.8,  # Time before resending unconfirmed
                   verify_ack_value=True # Verify echoed value matches
               )
               
               self.logger.info(f"Confirmed {len(confirmed)}/{len(params)} parameters")
               
               # Check which parameters were NOT confirmed
               failed = set(params.keys()) - set(confirmed.keys())
               if failed:
                   self.logger.warning(f"Failed to confirm: {failed}")
                   
               return {"confirmed": list(confirmed.keys()), "failed": list(failed)}
               
           except RuntimeError as e:
               return {"error": str(e)}
       
       async def read_flight_parameters(self, param_names: List[str]):
           """Read multiple parameters efficiently over unreliable links."""
           mavlink_proxy: MavLinkExternalProxy = self.get_proxy("ext_mavlink")
           
           try:
               results = await mavlink_proxy.get_params_bulk_lossy(
                   names=param_names,
                   timeout_total=6.0,
                   max_retries=3,
                   max_in_flight=10,
                   resend_interval=0.7
               )
               
               # Results contain detailed info for each parameter
               for name, info in results.items():
                   self.logger.debug(
                       f"{name}: value={info['value']}, "
                       f"type={info['type']}, index={info['index']}"
                   )
               
               return results
               
           except RuntimeError as e:
               return {"error": str(e)}

CloudDBProxy
------------

**Purpose:** Cloud database operations for persistent, scalable data storage

**Common Use Cases:**

- Storing flight logs in cloud
- Synchronizing configuration data
- Multi-device data sharing
- Analytics and reporting
- Long-term data retention

**Basic Usage:**

.. code-block:: python

   from petal_app_manager.proxies.cloud import CloudDBProxy

   class YourPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["cloud"]
       
       async def store_flight_data(self, data: dict):
           cloud_proxy: CloudDBProxy = self.get_proxy("cloud")
           
           # TODO: Add CloudDBProxy methods and examples
           # - Database operations
           # - Table management
           # - Query operations
           # - Batch operations
           # - Synchronization patterns
           # - Authentication handling

**Methods:**

.. code-block:: python

   # TODO: Document CloudDBProxy methods:
   # await cloud_proxy.scan_table(table_name, filters)
   # await cloud_proxy.get_item(table_name, key)
   # await cloud_proxy.put_item(table_name, item)
   # await cloud_proxy.update_item(table_name, key, updates)
   # await cloud_proxy.delete_item(table_name, key)
   # await cloud_proxy.batch_write(table_name, items)

**Example Patterns:**

.. code-block:: python

   # TODO: Add practical cloud database usage examples:
   # - Flight log storage
   # - Configuration synchronization
   # - User data management
   # - Analytics data collection
   # - Backup and recovery

LocalDBProxy
------------

**Purpose:** Local database operations for offline-capable, edge computing scenarios

**Common Use Cases:**

- Offline data storage
- Edge computing applications
- Local caching with persistence
- Backup when cloud unavailable
- Real-time local queries

**Basic Usage:**

.. code-block:: python

   from petal_app_manager.proxies.localdb import LocalDBProxy

   class YourPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["db"]
       
       async def store_local_data(self, data: dict):
           db_proxy: LocalDBProxy = self.get_proxy("db")
           
           # TODO: Add LocalDBProxy methods and examples
           # - Local database operations
           # - SQLite/embedded database usage
           # - Offline synchronization
           # - Local query patterns
           # - Data migration
           # - Backup strategies

**Methods:**

.. code-block:: python

   # TODO: Document LocalDBProxy methods:
   # await db_proxy.execute_query(sql, params)
   # await db_proxy.fetch_one(sql, params)
   # await db_proxy.fetch_all(sql, params)
   # await db_proxy.insert(table, data)
   # await db_proxy.update(table, data, where)
   # await db_proxy.delete(table, where)

**Example Patterns:**

.. code-block:: python

   # TODO: Add practical local database usage examples:
   # - Offline flight data storage
   # - Local configuration management
   # - Edge analytics
   # - Sync queue management
   # - Local user sessions

S3BucketProxy
-------------

**Purpose:** File storage, uploads, downloads, and content management using AWS S3

**Common Use Cases:**

- Upload flight logs and media
- Store configuration files
- Archive historical data
- Content delivery
- Backup storage
- Moving/renaming files within buckets

**Basic Usage:**

.. code-block:: python

   from petal_app_manager.proxies.bucket import S3BucketProxy

   class YourPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["bucket"]
       
       async def upload_file(self, file_path: str):
           bucket_proxy: S3BucketProxy = self.get_proxy("bucket")
           
           # Upload with auto-generated S3 key
           result = await bucket_proxy.upload_file(Path(file_path))
           
           # Upload with custom S3 key
           result = await bucket_proxy.upload_file(
               Path(file_path),
               custom_s3_key="custom/path/myfile.ulg"
           )

**Methods:**

.. code-block:: python

   # Upload file with auto-generated key
   await bucket_proxy.upload_file(
       file_path=Path("/path/to/file.ulg"),
       custom_filename="renamed.ulg"  # Optional: rename file
   )
   
   # Upload file with custom S3 key (full control over path)
   await bucket_proxy.upload_file(
       file_path=Path("/path/to/file.ulg"),
       custom_s3_key="flights/2026/01/07/flight_001.ulg"
   )
   
   # Move/rename a file within the bucket
   await bucket_proxy.move_file(
       source_key="uploads/temp/file.ulg",
       dest_key="archive/2026/file.ulg"
   )
   
   # Delete a file
   await bucket_proxy.delete_file(s3_key="path/to/file.ulg")
   
   # List objects in bucket
   await bucket_proxy.list_objects(prefix="flights/")

**Upload with Custom S3 Key Example:**

.. code-block:: python

   from pathlib import Path
   from petal_app_manager.proxies.bucket import S3BucketProxy

   class FlightLogPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["bucket"]
       
       async def upload_flight_log(self, file_path: Path, flight_date: str, flight_id: str):
           """Upload flight log with organized S3 path structure."""
           bucket_proxy: S3BucketProxy = self.get_proxy("bucket")
           
           # Create organized S3 key: flights/YYYY/MM/DD/flight_id.ulg
           custom_key = f"flights/{flight_date.replace('-', '/')}/{flight_id}.ulg"
           
           result = await bucket_proxy.upload_file(
               file_path=file_path,
               custom_s3_key=custom_key
           )
           
           if result.get("success"):
               self.logger.info(f"Uploaded to: {result['s3_key']}")
               return {"status": "success", "url": result.get("url")}
           else:
               self.logger.error(f"Upload failed: {result.get('error')}")
               return {"status": "error", "reason": result.get("error")}

**Move/Rename Files Example:**

.. code-block:: python

   class FileOrganizerPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["bucket"]
       
       async def archive_processed_file(self, source_key: str):
           """Move processed file from uploads to archive."""
           bucket_proxy: S3BucketProxy = self.get_proxy("bucket")
           
           # Move from uploads/ to archive/
           # e.g., "uploads/pending/file.ulg" -> "archive/2026/01/file.ulg"
           from datetime import datetime
           date_path = datetime.now().strftime("%Y/%m")
           filename = source_key.split("/")[-1]
           dest_key = f"archive/{date_path}/{filename}"
           
           result = await bucket_proxy.move_file(
               source_key=source_key,
               dest_key=dest_key
           )
           
           if result.get("success"):
               self.logger.info(f"Moved {source_key} -> {dest_key}")
               return {"status": "archived", "new_path": dest_key}
           else:
               self.logger.error(f"Move failed: {result.get('error')}")
               return {"status": "error", "reason": result.get("error")}
       
       async def batch_organize_files(self, source_prefix: str, dest_prefix: str):
           """Move all files from one prefix to another."""
           bucket_proxy: S3BucketProxy = self.get_proxy("bucket")
           
           # List all files in source prefix
           objects = await bucket_proxy.list_objects(prefix=source_prefix)
           
           results = {"moved": [], "failed": []}
           for obj in objects.get("objects", []):
               source_key = obj["key"]
               filename = source_key.split("/")[-1]
               dest_key = f"{dest_prefix}/{filename}"
               
               result = await bucket_proxy.move_file(source_key, dest_key)
               if result.get("success"):
                   results["moved"].append(dest_key)
               else:
                   results["failed"].append(source_key)
           
           return results

MQTTProxy
---------

**Purpose:** IoT messaging, device communication, and event streaming using MQTT protocol

**Common Use Cases:**

- Device-to-device communication
- Real-time event streaming
- IoT sensor data collection
- Command distribution
- Status broadcasting

**Basic Usage:**

.. code-block:: python

   from petal_app_manager.proxies.mqtt import MQTTProxy

   class YourPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["mqtt"]
       
       async def publish_status(self, status: dict):
           mqtt_proxy: MQTTProxy = self.get_proxy("mqtt")
           
           # TODO: Add MQTTProxy methods and examples
           # - Publishing messages
           # - Subscribing to topics
           # - Topic management
           # - QoS handling
           # - Retained messages
           # - Connection management

**Methods:**

.. code-block:: python

   # TODO: Document MQTTProxy methods:
   # await mqtt_proxy.publish(topic, message, qos=0, retain=False)
   # await mqtt_proxy.subscribe(topic, callback, qos=0)
   # await mqtt_proxy.unsubscribe(topic)
   # await mqtt_proxy.get_subscriptions()
   # await mqtt_proxy.is_connected()
   # await mqtt_proxy.disconnect()

**Example Patterns:**

.. code-block:: python

   # TODO: Add practical MQTT usage examples:
   # - Status broadcasting
   # - Command distribution
   # - Sensor data collection
   # - Event notifications
   # - Device coordination

Error Handling and Best Practices
----------------------------------

**Proxy Availability:**

.. code-block:: python

   class YourPetal(Petal):
       async def safe_proxy_usage(self):
           try:
               redis_proxy = self.get_proxy("redis")
               if redis_proxy is None:
                   logger.warning("Redis proxy not available")
                   return
               
               result = await redis_proxy.get("key")
           except Exception as e:
               logger.error(f"Proxy operation failed: {e}")

**Dependency Declaration:**

.. code-block:: python

   def get_required_proxies(self) -> List[str]:
       # Always declare required proxies
       return ["redis", "ext_mavlink"]
   
   def get_optional_proxies(self) -> List[str]:
       # Declare optional proxies for graceful degradation
       return ["cloud", "bucket"]

**Health Checks:**

.. code-block:: python

   async def check_proxy_health(self):
       for proxy_name in self.get_required_proxies():
           proxy = self.get_proxy(proxy_name)
           if proxy and hasattr(proxy, 'health_check'):
               health = await proxy.health_check()
               logger.info(f"{proxy_name} health: {health}")

**Configuration Management:**

.. code-block:: python

   # Proxies automatically use configuration from .env file
   # PETAL_REDIS_HOST, PETAL_REDIS_PORT, PETAL_MAVLINK_ENDPOINT, etc.
   # No manual configuration needed in petal code

Next Steps
----------

- Review the :doc:`adding_petals` guide for complete petal development
- Check :doc:`contribution_guidelines` for release and versioning
- Explore existing petals for real-world proxy usage examples
- Use the Admin Dashboard to monitor proxy health and status

.. note::
   **Documentation Status**: The MavlinkExternalProxy, S3BucketProxy, and RedisProxy sections 
   include comprehensive examples for bulk parameter operations, file management, and key scanning.
   CloudDBProxy, LocalDBProxy, and MQTTProxy sections contain placeholders that will be 
   populated with detailed examples in future updates.