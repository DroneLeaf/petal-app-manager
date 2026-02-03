Petal Flight Log
================

.. note::
   This documentation is for **petal-flight-log v0.2.5**
   This documentation covers the MQTT command interface for flight log management.

The **petal-flight-log** is a petal that provides comprehensive flight record management capabilities including ULog file downloads from Pixhawk, S3 uploads, rosbag file handling, and flight record synchronization. It uses a job-based architecture for long-running operations with real-time progress streaming.

Overview
--------

This petal communicates via MQTT messages on the ``command/edge`` topic. All commands follow a standardized message format:

.. code-block:: json

   {
       "waitResponse": true,
       "messageId": "unique-message-id",
       "deviceId": "device-id",
       "command": "petal-flight-log/<command_name>",
       "timestamp": "2026-01-15T14:30:00Z",
       "payload": { ... }
   }

Required Proxies
----------------

- ``mqtt`` - For MQTT communication with web clients
- ``redis`` - For job state persistence and caching
- ``db`` - Local database proxy for flight record storage
- ``cloud`` - Cloud database proxy for flight record synchronization
- ``s3_bucket`` - S3 bucket proxy for file uploads
- ``mavftp`` - MAVFTP proxy for ULog file downloads from Pixhawk
- ``ext_mavlink`` - MAVLink proxy for flight controller communication

Command Categories
------------------

.. contents:: 
   :local:
   :depth: 2

Flight Record Fetch Commands
----------------------------

These commands handle scanning, matching, and retrieving flight records from the system.

fetch_flight_records
^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/fetch_flight_records``

Initiates a long-running job (~30 seconds) that scans for rosbag files, lists ULog files from Pixhawk via MAVFTP, matches them based on timestamps, and stores results in databases.

**Payload:**

.. code-block:: json

   {
       "tolerance_seconds": 30,
       "start_time": "2026-01-15T14:00:00Z",
       "end_time": "2026-01-15T16:00:00Z",
       "base": "fs/microsd/log"
   }

**Parameters:**

- ``tolerance_seconds`` (int): Tolerance for timestamp matching in seconds (1-300, default: 30)
- ``start_time`` (str): Start time in ISO format for filtering records
- ``end_time`` (str): End time in ISO format for filtering records
- ``base`` (str): Base directory path on Pixhawk SD card for ULog file searches

**Response:**

.. code-block:: json

   {
       "status": "success",
       "message": "Fetch flight records job started. Subscribe to progress updates using subscribe_fetch_flight_records.",
       "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
   }

**Example - Complete Fetch Workflow:**

.. code-block:: python

   import asyncio
   import json

   # Step 1: Start the fetch job
   fetch_command = {
       "waitResponse": True,
       "messageId": "fetch-001",
       "deviceId": "drone-001",
       "command": "petal-flight-log/fetch_flight_records",
       "timestamp": "2026-01-15T14:30:00Z",
       "payload": {
           "tolerance_seconds": 30,
           "start_time": "2026-01-15T00:00:00Z",
           "end_time": "2026-01-15T23:59:59Z",
           "base": "fs/microsd/log"
       }
   }
   # Publish to MQTT and receive job_id in response

   # Step 2: Subscribe to progress updates
   subscribe_command = {
       "waitResponse": True,
       "messageId": "subscribe-001",
       "deviceId": "drone-001",
       "command": "petal-flight-log/subscribe_fetch_flight_records",
       "timestamp": "2026-01-15T14:30:01Z",
       "payload": {
           "subscribed_stream_id": "fetch-progress-001",
           "data_rate_hz": 2.0
       }
   }
   # Progress updates will be published to petal-flight-log/publish_fetch_flight_records_job_value_stream

subscribe_fetch_flight_records
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/subscribe_fetch_flight_records``

Subscribes to progress updates for an active fetch flight records job via MQTT streaming.

**Payload:**

.. code-block:: json

   {
       "subscribed_stream_id": "fetch-progress-001",
       "data_rate_hz": 2.0
   }

**Parameters:**

- ``subscribed_stream_id`` (str): Unique identifier for this subscription
- ``data_rate_hz`` (float): Data publishing rate in Hz (default: 2.0)

**Progress Stream Data Format:**

.. code-block:: json

   {
       "type": "progress",
       "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
       "machine_id": "drone-001",
       "status": "in_progress",
       "progress": 45.5,
       "completed": false,
       "message": "Scanning for flight records...",
       "total_records": null
   }

unsubscribe_fetch_flight_records
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/unsubscribe_fetch_flight_records``

Unsubscribes from fetch flight records progress updates.

**Payload:**

.. code-block:: json

   {
       "unsubscribed_stream_id": "fetch-progress-001"
   }

cancel_fetch_flight_records
^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/cancel_fetch_flight_records``

Cancels all active fetch flight records jobs.

**Payload:** None required

**Response:**

.. code-block:: json

   {
       "status": "success",
       "message": "Cancelled 1 fetch flight records jobs",
       "cancelled_jobs": ["f47ac10b-58cc-4372-a567-0e02b2c3d479"]
   }

fetch_existing_flight_records
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/fetch_existing_flight_records``

Retrieves existing flight records from the cloud database without performing a new scan. This is a fast operation that returns cached/stored records.

**Payload:** None required

**Response:**

.. code-block:: json

   {
       "status": "success",
       "data": {
           "flight_records": [
               {
                   "id": "record-001",
                   "ulog": {
                       "id": "ulog-001",
                       "file_name": "log_44_2026-01-15-14-30-22.ulg",
                       "storage_type": "local",
                       "size_bytes": 1048576
                   },
                   "rosbag": {
                       "id": "rosbag-001",
                       "file_name": "LeafFC_2026-01-15-14-30-22.bag",
                       "storage_type": "local",
                       "size_bytes": 2097152
                   },
                   "sync_job_status": "completed"
               }
           ],
           "total_matches": 1
       }
   }

Flight Record Sync Commands
---------------------------

These commands handle synchronizing flight records to cloud storage (S3).

start_sync_flight_record
^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/start_sync_flight_record``

Starts a synchronization job for a specific flight record. This orchestrates multiple sub-jobs:

1. Download ULog from Pixhawk (if needed, via MAVFTP)
2. Upload ULog to S3
3. Upload Rosbag to S3

**Progress Weight Distribution:**

- If ULog download is needed: 90% for ULog download, 5% each for S3 uploads
- If no ULog download needed: S3 jobs split 100% evenly (50% each, or 100% if single job)

**Payload:**

.. code-block:: json

   {
       "flight_record_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
   }

**Parameters:**

- ``flight_record_id`` (str): Unique identifier for the flight record to sync

**Response:**

.. code-block:: json

   {
       "status": "success",
       "message": "Started flight record sync job abc12345",
       "sync_job_id": "abc12345-6789-0def-ghij-klmnopqrstuv"
   }

**Example - Complete Sync Workflow:**

.. code-block:: python

   # Step 1: Start sync job
   sync_command = {
       "waitResponse": True,
       "messageId": "sync-001",
       "deviceId": "drone-001",
       "command": "petal-flight-log/start_sync_flight_record",
       "timestamp": "2026-01-15T14:30:00Z",
       "payload": {
           "flight_record_id": "record-001"
       }
   }

   # Step 2: Subscribe to sync job progress
   subscribe_command = {
       "waitResponse": True,
       "messageId": "subscribe-002",
       "deviceId": "drone-001",
       "command": "petal-flight-log/subscribe_sync_job_value_stream",
       "timestamp": "2026-01-15T14:30:01Z",
       "payload": {
           "subscribed_stream_id": "abc12345-6789-0def-ghij-klmnopqrstuv",
           "data_rate_hz": 2.0
       }
   }
   # Progress updates published to petal-flight-log/publish_sync_job_value_stream

subscribe_sync_job_value_stream
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/subscribe_sync_job_value_stream``

Subscribes to progress updates for a flight record sync job.

**Payload:**

.. code-block:: json

   {
       "subscribed_stream_id": "abc12345-6789-0def-ghij-klmnopqrstuv",
       "data_rate_hz": 2.0
   }

**Parameters:**

- ``subscribed_stream_id`` (str): The sync job ID to subscribe to
- ``data_rate_hz`` (float): Data publishing rate in Hz (default: 2.0)

**Progress Stream Data Format:**

.. code-block:: json

   {
       "type": "progress",
       "sync_job_id": "abc12345-6789-0def-ghij-klmnopqrstuv",
       "flight_record_id": "record-001",
       "machine_id": "drone-001",
       "progress": 45.0,
       "completed": false,
       "message": "Downloading ULog from Pixhawk... (125.5 KB/s)",
       "sub_jobs": {
           "ulog_download": "download-job-001",
           "ulog_upload": "upload-job-001",
           "rosbag_upload": "upload-job-002"
       }
   }

unsubscribe_sync_job_value_stream
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/unsubscribe_sync_job_value_stream``

Unsubscribes from sync job progress updates.

**Payload:**

.. code-block:: json

   {
       "unsubscribed_stream_id": "abc12345-6789-0def-ghij-klmnopqrstuv"
   }

cancel_sync_job
^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/cancel_sync_job``

Cancels a flight record sync job and all its sub-jobs (ULog download, S3 uploads).

**Payload:**

.. code-block:: json

   {
       "flight_record_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
   }

**Parameters:**

- ``flight_record_id`` (str): Unique identifier for the flight record whose sync job should be cancelled

**Response:**

.. code-block:: json

   {
       "status": "success",
       "message": "Cancelled flight record sync job"
   }

Flight Record Management Commands
---------------------------------

delete_flight_record
^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/delete_flight_record``

Deletes a flight record and its associated files from local storage and S3.

**Payload:**

.. code-block:: json

   {
       "flight_record_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
   }

**Parameters:**

- ``flight_record_id`` (str): Unique identifier for the flight record to delete

**Response:**

.. code-block:: json

   {
       "status": "success",
       "message": "Flight record f47ac10b-58cc-4372-a567-0e02b2c3d479 deleted successfully"
   }

.. warning::
   This operation permanently deletes the flight record from both local and cloud databases, 
   and moves associated S3 files to a ``deleted/`` folder. Local files are permanently removed.

Job Status Values
-----------------

All jobs in petal-flight-log use the following status values:

- ``pending`` - Job created but not yet started
- ``in_progress`` - Job is currently executing
- ``completed`` - Job finished successfully
- ``cancelled`` - Job was cancelled by user request
- ``error`` - Job failed with an error

MQTT Topics Reference
---------------------

**Command Topic (incoming):**

- ``command/edge`` - All commands are received on this topic

**Progress Stream Topics (outgoing):**

- ``petal-flight-log/publish_fetch_flight_records_job_value_stream`` - Fetch job progress
- ``petal-flight-log/publish_sync_job_value_stream`` - Sync job progress
- ``petal-flight-log/log_download/progress`` - ULog download progress
- ``petal-flight-log/s3_upload/progress`` - S3 upload progress

**Event Topics (outgoing):**

- ``petal-flight-log/fetch_flight_records`` - Fetch results broadcast
- ``petal-flight-log/cancel_sync_job`` - Sync cancellation notifications
- ``petal-flight-log/delete_flight_record`` - Delete notifications

Data Models
-----------

FlightRecordMatch
^^^^^^^^^^^^^^^^^

Represents a matched pair of ULog and Rosbag files from the same flight session.

.. code-block:: json

   {
       "id": "record-001",
       "ulog": {
           "id": "ulog-001",
           "file_name": "log_44_2026-01-15-14-30-22.ulg",
           "file_path": "/opt/ulog_downloads/log_44_2026-01-15-14-30-22.ulg",
           "file_type": "ulg",
           "sd_card_path": "/log/2026-01-15/14_30_22.ulg",
           "storage_type": "local",
           "size_bytes": 1048576,
           "size_kb": 1024.0,
           "modified_timestamp_unix_s": 1705323022,
           "date_str": "2026-01-15-14-30-22",
           "s3_key": "flight-logs/drone-001/2026-01-15/log_44.ulg"
       },
       "rosbag": {
           "id": "rosbag-001",
           "file_name": "LeafFC_2026-01-15-14-30-22.bag",
           "file_path": "/home/leaf/rosbag_records/LeafFC_2026-01-15-14-30-22.bag",
           "file_type": "bag",
           "storage_type": "local",
           "size_bytes": 2097152,
           "size_kb": 2048.0,
           "modified_timestamp_unix_s": 1705323022,
           "date_str": "2026-01-15-14-30-22",
           "s3_key": "flight-logs/drone-001/2026-01-15/LeafFC.bag"
       },
       "sync_job_id": "abc12345",
       "sync_job_status": "completed"
   }

Error Handling
--------------

All commands return standardized error responses:

.. code-block:: json

   {
       "status": "error",
       "message": "Detailed error description",
       "error_code": "ERROR_CODE"
   }

**Common Error Codes:**

- ``INVALID_PARAMETERS`` - Request payload validation failed
- ``JOB_NOT_FOUND`` - Requested job does not exist
- ``JOB_MONITOR_NOT_INITIALIZED`` - Job monitoring system not ready
- ``INTERNAL_ERROR`` - Unexpected server error
- ``PROCESSING_ERROR`` - Error during command processing
