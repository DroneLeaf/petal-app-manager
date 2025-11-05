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

**Basic Usage:**

.. code-block:: python

   from petal_app_manager.proxies.redis import RedisProxy

   class YourPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["redis"]
       
       async def cache_telemetry(self, data: dict):
           redis_proxy: RedisProxy = self.get_proxy("redis")
           
           # TODO: Add RedisProxy methods and examples
           # - Basic key-value operations
           # - Pub/sub messaging
           # - Hash operations
           # - List operations
           # - Expiration and TTL
           # - Connection pooling
           # - Error handling patterns

**Methods:**

.. code-block:: python

   # TODO: Document RedisProxy methods:
   # await redis_proxy.get(key)
   # await redis_proxy.set(key, value, ex=expiration)
   # await redis_proxy.hget(hash_key, field)
   # await redis_proxy.hset(hash_key, field, value)
   # await redis_proxy.lpush(list_key, value)
   # await redis_proxy.publish(channel, message)
   # await redis_proxy.subscribe(channel, callback)

**Example Patterns:**

.. code-block:: python

   # TODO: Add practical Redis usage examples:
   # - Caching flight data
   # - Inter-petal communication
   # - Session management
   # - Rate limiting
   # - Distributed locks

MavlinkExternalProxy
--------------------

**Purpose:** Communication with drones and autopilots using MAVLink protocol

**Common Use Cases:**

- Sending commands to drone
- Receiving telemetry data
- Mission management
- Parameter configuration
- Real-time monitoring

**Basic Usage:**

.. code-block:: python

   from petal_app_manager.proxies.external import MavLinkExternalProxy

   class YourPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["ext_mavlink"]
       
       async def send_command(self):
           mavlink_proxy: MavLinkExternalProxy = self.get_proxy("ext_mavlink")
           
           # TODO: Add MavlinkExternalProxy methods and examples
           # - Sending MAVLink messages
           # - Receiving telemetry
           # - Parameter operations
           # - Mission commands
           # - Custom message handling
           # - Connection management

**Methods:**

.. code-block:: python

   # TODO: Document MavlinkExternalProxy methods:
   # await mavlink_proxy.send_message(message)
   # await mavlink_proxy.get_telemetry()
   # await mavlink_proxy.set_parameter(name, value)
   # await mavlink_proxy.get_parameter(name)
   # await mavlink_proxy.arm_disarm(arm=True)
   # await mavlink_proxy.takeoff(altitude)
   # await mavlink_proxy.land()

**Example Patterns:**

.. code-block:: python

   # TODO: Add practical MAVLink usage examples:
   # - Flight mode changes
   # - Waypoint missions
   # - Real-time telemetry streaming
   # - Emergency procedures
   # - Custom DroneLeaf messages

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

**Basic Usage:**

.. code-block:: python

   from petal_app_manager.proxies.bucket import S3BucketProxy

   class YourPetal(Petal):
       def get_required_proxies(self) -> List[str]:
           return ["bucket"]
       
       async def upload_file(self, file_path: str):
           bucket_proxy: S3BucketProxy = self.get_proxy("bucket")
           
           # TODO: Add S3BucketProxy methods and examples
           # - File upload/download
           # - Bucket operations
           # - Metadata management
           # - Presigned URLs
           # - Multipart uploads
           # - Access control

**Methods:**

.. code-block:: python

   # TODO: Document S3BucketProxy methods:
   # await bucket_proxy.upload_file(local_path, s3_key)
   # await bucket_proxy.download_file(s3_key, local_path)
   # await bucket_proxy.list_objects(prefix)
   # await bucket_proxy.delete_object(s3_key)
   # await bucket_proxy.get_presigned_url(s3_key, expiration)
   # await bucket_proxy.upload_data(data, s3_key)

**Example Patterns:**

.. code-block:: python

   # TODO: Add practical S3 usage examples:
   # - Flight log uploads
   # - Media file management
   # - Configuration file storage
   # - Batch file operations
   # - Content serving

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
   # REDIS_HOST, REDIS_PORT, MAVLINK_ENDPOINT, etc.
   # No manual configuration needed in petal code

Next Steps
----------

- Review the :doc:`adding_petals` guide for complete petal development
- Check :doc:`contribution_guidelines` for release and versioning
- Explore existing petals for real-world proxy usage examples
- Use the Admin Dashboard to monitor proxy health and status

.. note::
   **Placeholder Documentation**: This section contains placeholders for detailed proxy usage examples and methods. Each proxy section will be populated with comprehensive examples, method documentation, and practical usage patterns in future updates.