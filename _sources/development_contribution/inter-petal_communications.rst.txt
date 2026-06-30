========================================
Inter-Petal Communication Guide
========================================

.. note::
   This is a **guided approach** (not yet a formal standard) designed to evolve based on community feedback and practical implementation experience.

Goal
====

Establish a structured, type-safe approach for petals to communicate with each other through Redis messaging, ensuring data validation and clear contracts between services.

Overview
========

Inter-petal communication follows a pattern where:

1. **Sink petals** (message receivers) define Pydantic data models for their expected requests
2. **Source petals** (message senders) import and use these models to construct type-safe messages
3. **Redis proxy** serves as the communication channel
4. **Pydantic validation** ensures data integrity on both ends

Benefits
--------

- **Type safety**: Compile-time type checking with proper IDE support
- **Data validation**: Automatic validation of message payloads
- **Clear contracts**: Explicit definition of expected data structures
- **Documentation**: Self-documenting code through Pydantic models
- **Error handling**: Structured error messages for invalid data

Implementation Guide
====================

For Sink Petal Developers (Message Receivers)
----------------------------------------------

Step 1: Define Data Models
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Create a ``data_model.py`` file in your petal's ``src/`` directory to define all request/response models:

.. code-block:: python

   # petal_sink/src/data_model.py
   
   from pydantic import BaseModel, Field, field_validator
   from typing import List, Optional, Dict, Any
   
   class GetFlightRecordsRequest(BaseModel):
       """Request model for get_flight_records command"""
       start_time: str = Field(
           ..., 
           description="Start time in ISO format (e.g., '2024-01-15T14:00:00Z')"
       )
       end_time: str = Field(
           ..., 
           description="End time in ISO format (e.g., '2024-01-15T16:00:00Z')"
       )
       tolerance_seconds: int = Field(
           default=30, 
           ge=1, 
           le=300, 
           description="Tolerance for timestamp matching in seconds (1-300)"
       )
       base: str = Field(
           ..., 
           description="Base directory for file searches"
       )
   
       model_config = {
           "json_schema_extra": {
               "example": {
                   "start_time": "2024-01-15T14:00:00Z",
                   "end_time": "2024-01-15T16:00:00Z",
                   "tolerance_seconds": 30,
                   "base": "fs/microsd/log"
               }
           }
       }
   
       @field_validator('start_time', 'end_time')
       @classmethod
       def validate_iso_format(cls, v: str) -> str:
           """Validate ISO format timestamps"""
           from datetime import datetime
           try:
               datetime.fromisoformat(v.replace('Z', '+00:00'))
               return v
           except ValueError:
               raise ValueError(f"Invalid ISO format timestamp: {v}")

.. tip::
   - Use descriptive field names and comprehensive descriptions
   - Add validators for complex field requirements
   - Provide examples in ``model_config`` for documentation
   - Use appropriate type hints (``List``, ``Dict``, ``Optional``, etc.)

Step 2: Register Message Handlers with Validation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In your petal's main logic, register Redis handlers that perform Pydantic validation:

.. code-block:: python

   from petal_sink.src.data_model import GetFlightRecordsRequest
   from petal_app_manager.proxies import RedisProxy
   
   async def handle_get_flight_records(message: Dict[str, Any]) -> None:
       """Handler for flight records requests with validation"""
       try:
           # Validate incoming message using Pydantic model
           request = GetFlightRecordsRequest(**message)
       except Exception as e:
           error_msg = f"Invalid request parameters: {e}"
           logger.error(error_msg)
           # Optionally publish error response
           await publish_error_response(error_msg)
           return
       
       # Process validated request
       logger.info(f"Processing flight records from {request.start_time} to {request.end_time}")
       
       try:
           # Your business logic here
           records = await fetch_flight_records(
               start_time=request.start_time,
               end_time=request.end_time,
               tolerance_seconds=request.tolerance_seconds,
               base=request.base
           )
           
           # Publish response
           await publish_success_response(records)
           
       except Exception as e:
           logger.error(f"Error processing flight records: {e}")
           await publish_error_response(str(e))
   
   # Register the handler
   redis_proxy.register_message_handler(
       key="/petal_sink/get_flight_records",
       callback=handle_get_flight_records
   )

.. warning::
   Always wrap Pydantic validation in try-except blocks to handle malformed messages gracefully.

Step 3: Document Your API
^^^^^^^^^^^^^^^^^^^^^^^^^^

Create clear documentation for your petal's message API:

.. code-block:: python

   """
   Petal Sink Message API
   ======================
   
   Channel: /petal_sink/get_flight_records
   Request Model: GetFlightRecordsRequest
   
   Description:
       Retrieves flight records within a specified time range.
   
   Example Usage:
       See petal_sink.src.data_model.GetFlightRecordsRequest for full model definition.
   
   Response Format:
       Success: {"status": "success", "records": [...]}
       Error: {"status": "error", "message": "..."}
   """

For Source Petal Developers (Message Senders)
----------------------------------------------

Step 1: Add Dependency
^^^^^^^^^^^^^^^^^^^^^^

Add the sink petal as a dependency in your ``pyproject.toml`` for proper type hinting:

.. code-block:: toml

   [tool.pdm.dev-dependencies]
   dev = [
       "petal-sink @ file:///${PROJECT_ROOT}/../petal-sink",
       # other dependencies...
   ]

Or for production dependencies:

.. code-block:: toml

   [project]
   dependencies = [
       "petal-sink @ file:///${PROJECT_ROOT}/../petal-sink",
       # other dependencies...
   ]

.. tip::
   Use relative paths for local development or Git URLs for remote dependencies.

Step 2: Import and Use Data Models
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Import the data model from the sink petal and use it to construct type-safe messages:

.. code-block:: python

   # petal_source/src/some_module.py
   
   from petal_sink.src.data_model import GetFlightRecordsRequest
   from petal_app_manager.proxies import RedisProxy
   
   async def request_flight_records(
       redis_proxy: RedisProxy,
       start_time: str,
       end_time: str
   ) -> None:
       """Request flight records from petal_sink"""
       
       # Create validated request using Pydantic model
       request = GetFlightRecordsRequest(
           start_time=start_time,
           end_time=end_time,
           tolerance_seconds=30,
           base="fs/microsd/log"
       )
       
       # Convert to dictionary for Redis publishing
       request_json = request.model_dump()
       
       # Publish to Redis channel
       await redis_proxy.publish(
           channel="/petal_sink/get_flight_records",
           message=request_json,
       )
       
       logger.info(f"Published flight records request to petal_sink")

.. note::
   The Pydantic model will validate your data at creation time, catching errors before they're sent over the network.

Step 3: Handle Responses (Optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you need to receive responses, register a handler:

.. code-block:: python

   async def handle_flight_records_response(message: Dict[str, Any]) -> None:
       """Handle response from petal_sink"""
       if message.get("status") == "success":
           records = message.get("records", [])
           logger.info(f"Received {len(records)} flight records")
           # Process records...
       else:
           error = message.get("message", "Unknown error")
           logger.error(f"Flight records request failed: {error}")
   
   redis_proxy.register_message_handler(
       key="/petal_source/flight_records_response",
       callback=handle_flight_records_response
   )

Best Practices
==============

Data Model Design
-----------------

1. **Use clear, descriptive field names**
   
   .. code-block:: python
   
      # Good
      start_time: str = Field(..., description="Start time in ISO format")
      
      # Avoid
      st: str  # Unclear abbreviation

2. **Add field validators for complex requirements**
   
   .. code-block:: python
   
      @field_validator('email')
      @classmethod
      def validate_email(cls, v: str) -> str:
          if '@' not in v:
              raise ValueError("Invalid email format")
          return v

3. **Provide default values where appropriate**
   
   .. code-block:: python
   
      timeout_seconds: int = Field(default=30, ge=1, le=300)

4. **Include examples in model_config**
   
   This helps with documentation and testing.

5. **Use type hints consistently**
   
   .. code-block:: python
   
      from typing import List, Optional, Dict, Any
      
      tags: List[str] = Field(default_factory=list)
      metadata: Optional[Dict[str, Any]] = None

Channel Naming Convention
--------------------------

Use a consistent naming pattern for Redis channels:

.. code-block:: text

   /<petal_name>/<action>
   
   Examples:
   /petal_leafsdk/get_flight_records
   /petal_qgc_mission/upload_mission
   /petal_warehouse/store_telemetry

Error Handling
--------------

1. **Always validate incoming messages**
   
   .. code-block:: python
   
      try:
          request = RequestModel(**message)
      except ValidationError as e:
          logger.error(f"Validation failed: {e}")
          return

2. **Provide meaningful error messages**
   
   .. code-block:: python
   
      await redis_proxy.publish(
          channel="/petal_source/error",
          message={
              "status": "error",
              "message": "Invalid timestamp format",
              "details": str(e)
          }
      )

3. **Log validation failures**
   
   This helps with debugging and monitoring.

Versioning
----------

Consider adding version fields to your models for future compatibility:

.. code-block:: python

   class GetFlightRecordsRequest(BaseModel):
       """Request model for get_flight_records command"""
       version: str = Field(default="1.0.0", description="API version")
       # ... other fields

Testing
-------

Write tests for your data models and handlers:

.. code-block:: python

   import pytest
   from petal_sink.src.data_model import GetFlightRecordsRequest
   
   def test_valid_request():
       """Test creating a valid request"""
       request = GetFlightRecordsRequest(
           start_time="2024-01-15T14:00:00Z",
           end_time="2024-01-15T16:00:00Z",
           tolerance_seconds=30,
           base="fs/microsd/log"
       )
       assert request.tolerance_seconds == 30
   
   def test_invalid_tolerance():
       """Test validation of tolerance_seconds"""
       with pytest.raises(ValidationError):
           GetFlightRecordsRequest(
               start_time="2024-01-15T14:00:00Z",
               end_time="2024-01-15T16:00:00Z",
               tolerance_seconds=500,  # Exceeds maximum
               base="fs/microsd/log"
           )

Example: Complete Implementation
=================================

Sink Petal (petal-leafsdk)
---------------------------

**data_model.py:**

.. code-block:: python

   # petal_leafsdk/src/data_model.py
   
   from pydantic import BaseModel, Field, field_validator
   from typing import Optional
   from datetime import datetime
   
   class GetFlightRecordsRequest(BaseModel):
       """Request model for retrieving flight records"""
       start_time: str = Field(
           ..., 
           description="Start time in ISO format (e.g., '2024-01-15T14:00:00Z')"
       )
       end_time: str = Field(
           ..., 
           description="End time in ISO format (e.g., '2024-01-15T16:00:00Z')"
       )
       tolerance_seconds: int = Field(
           default=30, 
           ge=1, 
           le=300, 
           description="Tolerance for timestamp matching in seconds (1-300)"
       )
       base: str = Field(
           default="fs/microsd/log", 
           description="Base directory for file searches"
       )
       
       model_config = {
           "json_schema_extra": {
               "example": {
                   "start_time": "2024-01-15T14:00:00Z",
                   "end_time": "2024-01-15T16:00:00Z",
                   "tolerance_seconds": 30,
                   "base": "fs/microsd/log"
               }
           }
       }
       
       @field_validator('start_time', 'end_time')
       @classmethod
       def validate_iso_format(cls, v: str) -> str:
           """Validate ISO format timestamps"""
           try:
               datetime.fromisoformat(v.replace('Z', '+00:00'))
               return v
           except ValueError:
               raise ValueError(f"Invalid ISO format timestamp: {v}")
   
   class GetFlightRecordsResponse(BaseModel):
       """Response model for flight records"""
       status: str = Field(..., description="Response status: 'success' or 'error'")
       message: str = Field(..., description="Status message")
       records: Optional[list] = Field(default=None, description="Flight records if successful")

**Handler implementation:**

.. code-block:: python

   # petal_leafsdk/src/main.py
   
   from petal_leafsdk.src.data_model import (
       GetFlightRecordsRequest, 
       GetFlightRecordsResponse
   )
   from petal_app_manager.proxies import RedisProxy
   import logging
   
   logger = logging.getLogger(__name__)
   
   async def handle_get_flight_records(message: dict) -> None:
       """Handler for flight records requests"""
       try:
           # Validate request
           request = GetFlightRecordsRequest(**message)
       except Exception as e:
           error_msg = f"Invalid request parameters: {e}"
           logger.error(error_msg)
           
           # Send error response
           response = GetFlightRecordsResponse(
               status="error",
               message=error_msg
           )
           await redis_proxy.publish(
               channel="/petal_qgc_mission/flight_records_response",
               message=response.model_dump()
           )
           return
       
       logger.info(f"Processing flight records request: {request.start_time} to {request.end_time}")
       
       try:
           # Fetch flight records
           records = await fetch_flight_records(
               start_time=request.start_time,
               end_time=request.end_time,
               tolerance_seconds=request.tolerance_seconds,
               base=request.base
           )
           
           # Send success response
           response = GetFlightRecordsResponse(
               status="success",
               message=f"Found {len(records)} flight records",
               records=records
           )
           await redis_proxy.publish(
               channel="/petal_qgc_mission/flight_records_response",
               message=response.model_dump()
           )
           
       except Exception as e:
           logger.error(f"Error fetching flight records: {e}")
           response = GetFlightRecordsResponse(
               status="error",
               message=str(e)
           )
           await redis_proxy.publish(
               channel="/petal_qgc_mission/flight_records_response",
               message=response.model_dump()
           )
   
   # Register handler
   redis_proxy.register_message_handler(
       key="/petal_leafsdk/get_flight_records",
       callback=handle_get_flight_records
   )

Source Petal (petal-qgc-mission-adapter)
-----------------------------------------

**pyproject.toml:**

.. code-block:: toml

   [tool.pdm.dev-dependencies]
   dev = [
       "petal-leafsdk @ file:///${PROJECT_ROOT}/../petal-leafsdk",
   ]

**Source code:**

.. code-block:: python

   # petal_qgc_mission_adapter/src/main.py
   
   from petal_leafsdk.src.data_model import (
       GetFlightRecordsRequest,
       GetFlightRecordsResponse
   )
   from petal_app_manager.proxies import RedisProxy
   import logging
   
   logger = logging.getLogger(__name__)
   
   async def request_flight_records(
       redis_proxy: RedisProxy,
       start_time: str,
       end_time: str
   ) -> None:
       """Request flight records from petal-leafsdk"""
       
       # Create type-safe request
       request = GetFlightRecordsRequest(
           start_time=start_time,
           end_time=end_time,
           tolerance_seconds=30,
           base="fs/microsd/log"
       )
       
       # Publish request
       await redis_proxy.publish(
           channel="/petal_leafsdk/get_flight_records",
           message=request.model_dump(),
       )
       
       logger.info("Published flight records request to petal-leafsdk")
   
   async def handle_flight_records_response(message: dict) -> None:
       """Handle response from petal-leafsdk"""
       try:
           response = GetFlightRecordsResponse(**message)
       except Exception as e:
           logger.error(f"Invalid response format: {e}")
           return
       
       if response.status == "success":
           logger.info(f"Received {len(response.records or [])} flight records")
           # Process records...
       else:
           logger.error(f"Flight records request failed: {response.message}")
   
   # Register response handler
   redis_proxy.register_message_handler(
       key="/petal_qgc_mission/flight_records_response",
       callback=handle_flight_records_response
   )

Acceptance Criteria
===================

The following criteria must be met for compliance with this guide:

1. ✅ **Data models defined** in sink petal under ``src/data_model.py``
2. ✅ **Pydantic validation** used in all message handlers
3. ✅ **Type-safe message construction** in source petal
4. ✅ **Dependency added** to source petal's ``pyproject.toml``
5. ✅ **Error handling** implemented for validation failures
6. ✅ **Documentation** provided for message API
7. ✅ **Example implementation** will be updated soon once merged

Reference Implementation
========================

The first compliant interaction is in progress. This section will be updated with links to the actual code once merged.

This implementation serves as the reference for future inter-petal communications.

Migration Path
==============

For Existing Petals
-------------------

If you have existing inter-petal communication that doesn't follow this guide:

1. **Identify all message types** exchanged between petals
2. **Create Pydantic models** for each message type
3. **Update handlers** to validate incoming messages
4. **Update senders** to use Pydantic models
5. **Add dependencies** to ``pyproject.toml``
6. **Test thoroughly** with both valid and invalid messages
7. **Update documentation** to reflect new models

Deprecation Strategy
--------------------

When migrating:

1. Keep old handlers working during transition period
2. Add new Pydantic-based handlers alongside old ones
3. Update senders to use new models
4. Monitor logs for validation errors
5. Remove old handlers once migration is complete

Additional Resources
====================

- `Pydantic Documentation <https://docs.pydantic.dev/>`_
- :doc:`using_proxies` - Guide to using Redis and other proxies
- :doc:`adding_petals` - Guide to creating new petals
- `Redis Pub/Sub Documentation <https://redis.io/docs/manual/pubsub/>`_

Troubleshooting
===============

Common Issues
-------------

**Type hints not working**
   Make sure the sink petal is added to ``pyproject.toml`` and run ``pdm install``

**Validation errors**
   Check that field names and types match exactly between sender and receiver

**Import errors**
   Verify the import path matches your petal's structure (``petal_name.src.data_model``)

**Messages not received**
   Verify channel names match exactly between publisher and subscriber

Getting Help
------------

For questions or issues:

1. Check the example implementation in this document
2. Review Pydantic documentation for model-related questions
3. Open an issue in the petal-app-manager repository
4. Reach out to the development team

.. note::
   This guide will be updated as we gain more experience with inter-petal communication patterns.