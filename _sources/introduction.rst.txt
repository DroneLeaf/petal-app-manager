Introduction
============

What is Petal App Manager?
---------------------------

Overview
~~~~~~~~

Petal App Manager is a modular application framework built on FastAPI that enables the development and deployment of pluggable components called "Petals". It provides a unified proxy architecture for interacting with various backend systems commonly used in drone and robotics applications.

Think of Petal App Manager as a middleware layer that:

- **Abstracts complex system interactions** through a unified proxy system
- **Enables modular development** with independently deployable Petal components
- **Handles communication protocols** automatically (HTTP, WebSocket, MQTT)
- **Manages resource lifecycles** for connections to MAVLink devices, Redis, databases, and cloud services
- **Provides a plugin architecture** allowing teams to develop features independently

The framework is specifically designed for embedded systems and edge computing scenarios, particularly in the drone and autonomous systems domain, where multiple components need to coordinate and share data efficiently.

Key Features
~~~~~~~~~~~~

**Unified Proxy Architecture**
   Access multiple backend systems (MAVLink, Redis, DynamoDB, S3, MQTT) through a consistent interface. Proxies handle connection management, error handling, and resource cleanup automatically.

**Plugin-Based Petals**
   Develop features as independent Petal modules that can be loaded, configured, and deployed separately. Each Petal can declare its dependencies on specific proxies.

**Automatic API Generation**
   Use decorators to expose Petal methods as HTTP or WebSocket endpoints. The framework handles routing, request validation, and response serialization.

**Configuration Management**
   Centralized configuration through ``.env`` files and ``proxies.yaml``, allowing easy deployment across different environments.

**Health Monitoring**
   Built-in health check system that monitors all proxies and petals, providing real-time status information.

**Logging and Debugging**
   Comprehensive logging system with per-component log levels and optional file output for troubleshooting.

**Production-Ready**
   Designed for deployment on embedded Linux systems (Raspberry Pi, NVIDIA Orin) with systemd integration and auto-start capabilities.

Architecture
~~~~~~~~~~~~

System Architecture Diagram
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. graphviz::
   :caption: Petal App Manager System Architecture

   digraph architecture {
       rankdir=TB;
       node [shape=box, style=filled];
       
       // User layer
       subgraph cluster_clients {
           label="Clients";
           style=filled;
           color=lightgrey;
           
           web [label="Web Browser\n(Admin UI)", fillcolor=lightblue];
           postman [label="API Client\n(Postman)", fillcolor=lightblue];
           mqtt_client [label="MQTT Client", fillcolor=lightblue];
       }
       
       // Application layer
       subgraph cluster_app {
           label="Petal App Manager";
           style=filled;
           color=lightyellow;
           
           fastapi [label="FastAPI\nApplication", fillcolor=gold];
           
           subgraph cluster_petals {
               label="Petals (Plugins)";
               style=filled;
               color=lightgreen;
               
               petal1 [label="Flight Log\nPetal", fillcolor=palegreen];
               petal2 [label="Warehouse\nPetal", fillcolor=palegreen];
               petal3 [label="User Journey\nPetal", fillcolor=palegreen];
               petal4 [label="LeafSDK\nPetal", fillcolor=palegreen];
           }
           
           subgraph cluster_proxies {
               label="Proxies";
               style=filled;
               color=lightcyan;
               
               redis_proxy [label="Redis\nProxy", fillcolor=cyan];
               mavlink_proxy [label="MAVLink\nProxy", fillcolor=cyan];
               cloud_proxy [label="Cloud DB\nProxy", fillcolor=cyan];
               s3_proxy [label="S3 Bucket\nProxy", fillcolor=cyan];
               mqtt_proxy [label="MQTT\nProxy", fillcolor=cyan];
               localdb_proxy [label="Local DB\nProxy", fillcolor=cyan];
           }
       }
       
       // Backend layer
       subgraph cluster_backends {
           label="Backend Systems";
           style=filled;
           color=pink;
           
           redis [label="Redis Server\n(Cache/PubSub)", fillcolor=lightpink];
           px4 [label="PX4/ArduPilot\n(MAVLink)", fillcolor=lightpink];
           dynamodb [label="AWS DynamoDB\n(Cloud)", fillcolor=lightpink];
           s3 [label="AWS S3\n(Storage)", fillcolor=lightpink];
           mqtt_broker [label="MQTT Broker", fillcolor=lightpink];
           local_dynamo [label="Local DynamoDB", fillcolor=lightpink];
       }
       
       // Client connections
       web -> fastapi [label="HTTP/WS"];
       postman -> fastapi [label="HTTP"];
       mqtt_client -> fastapi [label="MQTT"];
       
       // Petal to Proxy connections
       petal1 -> redis_proxy [style=dashed];
       petal1 -> cloud_proxy [style=dashed];
       petal2 -> redis_proxy [style=dashed];
       petal2 -> mavlink_proxy [style=dashed];
       petal3 -> mqtt_proxy [style=dashed];
       petal3 -> mavlink_proxy [style=dashed];
       petal4 -> redis_proxy [style=dashed];
       
       // FastAPI to components
       fastapi -> petal1;
       fastapi -> petal2;
       fastapi -> petal3;
       fastapi -> petal4;
       
       // Proxy to Backend connections
       redis_proxy -> redis [style=bold];
       mavlink_proxy -> px4 [style=bold];
       cloud_proxy -> dynamodb [style=bold];
       s3_proxy -> s3 [style=bold];
       mqtt_proxy -> mqtt_broker [style=bold];
       localdb_proxy -> local_dynamo [style=bold];
   }

Architecture Components
^^^^^^^^^^^^^^^^^^^^^^^

The architecture consists of three main layers:

**1. Client Layer**
   External clients interact with Petal App Manager through:
   
   - **HTTP REST API**: Standard RESTful endpoints for data operations
   - **WebSocket API**: Real-time bidirectional communication
   - **MQTT Interface**: Message-based publish/subscribe patterns
   - **Admin UI**: Web-based dashboard for monitoring and configuration

**2. Application Layer**
   
   **FastAPI Core**
      The application server that handles routing, request validation, and response serialization.
   
   **Petals (Plugins)**
      Independent feature modules that implement specific functionality:
      
      - Loaded dynamically at startup based on ``proxies.yaml`` configuration
      - Each Petal inherits from ``BasePetal`` class
      - Declare dependencies on specific proxies
      - Expose endpoints using ``@http_endpoint`` or ``@websocket_endpoint`` decorators
   
   **Proxies**
      Abstraction layer for backend system communication:
      
      - **RedisProxy**: In-memory cache, pub/sub messaging, and inter-process communication
      - **MavLinkExternalProxy**: Communication with flight controllers (PX4/ArduPilot)
      - **CloudProxy**: Cloud database operations (DynamoDB)
      - **S3BucketProxy**: Object storage and file management
      - **MQTTProxy**: Message broker integration
      - **LocalDBProxy**: Local database operations

**3. Backend Layer**
   The actual systems and services that Petals interact with:
   
   - **Redis Server**: High-performance in-memory data store
   - **Flight Controller**: Drone autopilot systems via MAVLink protocol
   - **Cloud Services**: AWS DynamoDB and S3 for persistent storage
   - **MQTT Broker**: Message-oriented middleware
   - **Local Database**: On-device DynamoDB instance

Data Flow
^^^^^^^^^

A typical request flows through the system as follows:

1. **Client Request**: External client sends HTTP/WebSocket/MQTT request
2. **FastAPI Routing**: Request is routed to the appropriate Petal endpoint
3. **Petal Processing**: Petal method executes business logic
4. **Proxy Interaction**: Petal uses proxies to interact with backend systems
5. **Backend Operations**: Proxies communicate with actual backend services
6. **Response**: Data flows back through the same path to the client

Use Cases
~~~~~~~~~

**Drone Data Management**
   Collect, process, and store flight logs, telemetry data, and mission information from drones. The Flight Log Petal handles automatic upload of ULog files to cloud storage.

**Real-time Telemetry Streaming**
   Stream live drone telemetry data to ground control stations or monitoring dashboards using WebSocket endpoints.

**Mission Planning and Execution**
   Coordinate complex missions through the User Journey Coordinator Petal, which manages mission states and drone commands.

**Fleet Management**
   Monitor and control multiple drones simultaneously using the Warehouse Petal for data aggregation and analytics.

**Custom Drone Applications**
   Develop domain-specific applications as Petals (e.g., precision agriculture, inspection, delivery) that leverage the existing proxy infrastructure.

**Edge Computing**
   Run AI/ML models on edge devices (Raspberry Pi, NVIDIA Orin) with direct access to drone data through MAVLink.

**Integration Projects**
   Connect drone systems with enterprise software, IoT platforms, or custom backends using the flexible proxy architecture.

Why Petal App Manager?
~~~~~~~~~~~~~~~~~~~~~~

**For Developers**
   - Focus on business logic, not infrastructure
   - Modular development with clear separation of concerns
   - Type-safe Python with FastAPI's validation
   - Hot-reload during development
   - Comprehensive API documentation automatically generated

**For Operations**
   - Single service manages multiple drone-related functions
   - Centralized configuration and monitoring
   - Designed for embedded Linux environments
   - Systemd integration for production deployments
   - Minimal resource footprint

**For System Integrators**
   - Standard REST/WebSocket/MQTT interfaces
   - Easy integration with existing systems
   - Extensible through custom Petals
   - Well-documented proxy interfaces
   - Active development and support
