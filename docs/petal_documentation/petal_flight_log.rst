Petal Flight Log
================

.. note::
   This documentation is for **petal-flight-log v0.2.6**
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
       "payload": {}
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

Bulk Delete Flight Records Commands
------------------------------------

These commands handle bulk deletion of multiple flight records using the job-based architecture with
real-time progress streaming.

bulk_delete_flight_records
^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/bulk_delete_flight_records``

Initiates a long-running job to delete multiple flight records simultaneously. Each record's ULog,
Rosbag, S3 files, and database entries are removed. Any existing bulk delete job is automatically
cancelled before starting a new one.

**Payload:**

.. code-block:: json

   {
       "flight_record_ids": [
           "f47ac10b-58cc-4372-a567-0e02b2c3d479",
           "a1b2c3d4-e5f6-7890-abcd-1234567890ab"
       ]
   }

**Parameters:**

- ``flight_record_ids`` (list[str]): List of flight record IDs to delete (1-100, must be unique)

**Response:**

.. code-block:: json

   {
       "status": "success",
       "message": "Bulk delete job started for 2 flight records. Subscribe to progress updates using subscribe_bulk_delete_flight_records.",
       "total_requested": 2,
       "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
   }

**Example - Complete Bulk Delete Workflow:**

.. code-block:: python

   # Step 1: Start the bulk delete job
   bulk_delete_command = {
       "waitResponse": True,
       "messageId": "bulk-del-001",
       "deviceId": "drone-001",
       "command": "petal-flight-log/bulk_delete_flight_records",
       "timestamp": "2026-02-18T14:30:00Z",
       "payload": {
           "flight_record_ids": [
               "record-001",
               "record-002",
               "record-003"
           ]
       }
   }
   # Publish to MQTT and receive job_id in response

   # Step 2: Subscribe to progress updates
   subscribe_command = {
       "waitResponse": True,
       "messageId": "subscribe-bulk-del-001",
       "deviceId": "drone-001",
       "command": "petal-flight-log/subscribe_bulk_delete_flight_records",
       "timestamp": "2026-02-18T14:30:01Z",
       "payload": {
           "subscribed_stream_id": "bulk-delete-progress-001",
           "data_rate_hz": 2.0
       }
   }
   # Progress updates published to petal-flight-log/publish_bulk_delete_job_value_stream

subscribe_bulk_delete_flight_records
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/subscribe_bulk_delete_flight_records``

Subscribes to progress updates for an active bulk delete flight records job via MQTT streaming.
The ``subscribed_stream_id`` is provided by the front-end for future use but is not used to find
the job — this handler subscribes to the single active ``BulkDeleteFlightRecordsJob``.

**Payload:**

.. code-block:: json

   {
       "subscribed_stream_id": "bulk-delete-progress-001",
       "data_rate_hz": 2.0
   }

**Parameters:**

- ``subscribed_stream_id`` (str): Unique identifier for this subscription
- ``data_rate_hz`` (float): Data publishing rate in Hz (0.1-10.0, default: 2.0)

**Progress Stream Data Format:**

.. code-block:: json

   {
       "type": "progress",
       "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
       "machine_id": "drone-001",
       "status": "in_progress",
       "progress": 50.0,
       "completed": false,
       "message": "Deleted 1 of 2 flight records...",
       "total_requested": 2,
       "total_deleted": 1,
       "total_failed": 0
   }

**Response:**

.. code-block:: json

   {
       "status": "success",
       "message": "Subscribed to bulk delete job progress updates",
       "subscribed_stream_id": "bulk-delete-progress-001",
       "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
       "data_rate_hz": 2.0,
       "mqtt_topic": "petal-flight-log/publish_bulk_delete_job_value_stream"
   }

unsubscribe_bulk_delete_flight_records
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/unsubscribe_bulk_delete_flight_records``

Unsubscribes from bulk delete flight records progress updates.

**Payload:**

.. code-block:: json

   {
       "unsubscribed_stream_id": "bulk-delete-progress-001"
   }

**Response:**

.. code-block:: json

   {
       "status": "success",
       "message": "Unsubscribed from bulk delete job progress updates",
       "unsubscribed_stream_id": "bulk-delete-progress-001",
       "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
   }

cancel_bulk_delete_flight_records
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/cancel_bulk_delete_flight_records``

Cancels all active bulk delete flight records jobs.

**Payload:** None required

**Response:**

.. code-block:: json

   {
       "status": "success",
       "message": "Cancelled 1 bulk delete jobs",
       "cancelled_jobs": ["f47ac10b-58cc-4372-a567-0e02b2c3d479"]
   }

Clear All ULogs Commands
------------------------

These commands handle clearing all ULog files from the Pixhawk SD card using the job-based
architecture with real-time progress streaming.

clear_all_ulogs
^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/clear_all_ulogs``

Initiates a long-running job to delete all ULog files from the Pixhawk SD card via MAVFTP.
Any existing clear all ULogs job is automatically cancelled before starting a new one.

**Payload:**

.. code-block:: json

   {
       "base": "fs/microsd/log"
   }

**Parameters:**

- ``base`` (str): Base directory on Pixhawk SD card to clear ULogs from (default: ``"fs/microsd/log"``)

**Response:**

.. code-block:: json

   {
       "status": "success",
       "message": "Clear all ULogs job started for fs/microsd/log. Subscribe to progress updates using subscribe_clear_all_ulogs.",
       "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
   }

**Example - Complete Clear All ULogs Workflow:**

.. code-block:: python

   # Step 1: Start the clear all ULogs job
   clear_command = {
       "waitResponse": True,
       "messageId": "clear-ulogs-001",
       "deviceId": "drone-001",
       "command": "petal-flight-log/clear_all_ulogs",
       "timestamp": "2026-02-18T14:30:00Z",
       "payload": {
           "base": "fs/microsd/log"
       }
   }
   # Publish to MQTT and receive job_id in response

   # Step 2: Subscribe to progress updates
   subscribe_command = {
       "waitResponse": True,
       "messageId": "subscribe-clear-001",
       "deviceId": "drone-001",
       "command": "petal-flight-log/subscribe_clear_all_ulogs",
       "timestamp": "2026-02-18T14:30:01Z",
       "payload": {
           "subscribed_stream_id": "clear-ulogs-progress-001",
           "data_rate_hz": 2.0
       }
   }
   # Progress updates published to petal-flight-log/publish_clear_all_ulogs_job_value_stream

subscribe_clear_all_ulogs
^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/subscribe_clear_all_ulogs``

Subscribes to progress updates for an active clear all ULogs job via MQTT streaming.
The ``subscribed_stream_id`` is provided by the front-end for future use but is not used to find
the job — this handler subscribes to the single active ``ClearAllUlogsJob``.

**Payload:**

.. code-block:: json

   {
       "subscribed_stream_id": "clear-ulogs-progress-001",
       "data_rate_hz": 2.0
   }

**Parameters:**

- ``subscribed_stream_id`` (str): Unique identifier for this subscription
- ``data_rate_hz`` (float): Data publishing rate in Hz (0.1-10.0, default: 2.0)

**Progress Stream Data Format:**

.. code-block:: json

   {
       "type": "progress",
       "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
       "machine_id": "drone-001",
       "status": "in_progress",
       "progress": 50.0,
       "completed": false,
       "message": "Deleting ULog files...",
       "base": "fs/microsd/log",
       "total_files": 10,
       "deleted": 5,
       "failed": 0
   }

**Response:**

.. code-block:: json

   {
       "status": "success",
       "message": "Subscribed to clear all ULogs job progress updates",
       "subscribed_stream_id": "clear-ulogs-progress-001",
       "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
       "data_rate_hz": 2.0,
       "mqtt_topic": "petal-flight-log/publish_clear_all_ulogs_job_value_stream"
   }

unsubscribe_clear_all_ulogs
^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/unsubscribe_clear_all_ulogs``

Unsubscribes from clear all ULogs progress updates.

**Payload:**

.. code-block:: json

   {
       "unsubscribed_stream_id": "clear-ulogs-progress-001"
   }

**Response:**

.. code-block:: json

   {
       "status": "success",
       "message": "Unsubscribed from clear all ULogs job progress updates",
       "unsubscribed_stream_id": "clear-ulogs-progress-001",
       "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
   }

cancel_clear_all_ulogs
^^^^^^^^^^^^^^^^^^^^^^

**Command:** ``petal-flight-log/cancel_clear_all_ulogs``

Cancels all active clear all ULogs jobs.

**Payload:** None required

**Response:**

.. code-block:: json

   {
       "status": "success",
       "message": "Cancelled 1 clear all ULogs jobs",
       "cancelled_jobs": ["f47ac10b-58cc-4372-a567-0e02b2c3d479"]
   }

.. warning::
   The ``clear_all_ulogs`` command permanently deletes **all** ULog files from the Pixhawk SD card.
   This operation cannot be undone. Ensure important logs have been synced to S3 before clearing.

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
- ``petal-flight-log/publish_bulk_delete_job_value_stream`` - Bulk delete job progress
- ``petal-flight-log/publish_clear_all_ulogs_job_value_stream`` - Clear all ULogs job progress
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

MQTT Topics Reference
---------------------

This section provides a comprehensive reference of all MQTT topics used by the petal.

Commands (Received on ``command/edge``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Commands are received on the ``command/edge`` topic with the following format:
``petal-flight-log/<command_name>``

**Flight Record Fetch:**

- ``petal-flight-log/fetch_flight_records`` - Scan and match flight records from multiple sources
- ``petal-flight-log/fetch_existing_flight_records`` - Fetch previously fetched records from cache

**Flight Record Management:**

- ``petal-flight-log/delete_flight_record`` - Delete a flight record and associated files
- ``petal-flight-log/bulk_delete_flight_records`` - Bulk delete multiple flight records
- ``petal-flight-log/subscribe_bulk_delete_flight_records`` - Subscribe to bulk delete progress
- ``petal-flight-log/unsubscribe_bulk_delete_flight_records`` - Unsubscribe from bulk delete progress
- ``petal-flight-log/cancel_bulk_delete_flight_records`` - Cancel active bulk delete job

**ULog Management:**

- ``petal-flight-log/clear_all_ulogs`` - Clear all ULog files from Pixhawk SD card
- ``petal-flight-log/subscribe_clear_all_ulogs`` - Subscribe to clear all ULogs progress
- ``petal-flight-log/unsubscribe_clear_all_ulogs`` - Unsubscribe from clear all ULogs progress
- ``petal-flight-log/cancel_clear_all_ulogs`` - Cancel active clear all ULogs job

**Sync Job Management:**

- ``petal-flight-log/start_sync_flight_record`` - Start a sync job for ULog download and S3 upload
- ``petal-flight-log/cancel_sync_job`` - Cancel an active sync job

**Stream Subscriptions:**

- ``petal-flight-log/subscribe_sync_job_value_stream`` - Subscribe to sync job progress updates
- ``petal-flight-log/unsubscribe_sync_job_value_stream`` - Unsubscribe from sync job progress
- ``petal-flight-log/subscribe_fetch_flight_records`` - Subscribe to fetch job progress updates
- ``petal-flight-log/unsubscribe_fetch_flight_records`` - Unsubscribe from fetch job progress
- ``petal-flight-log/cancel_fetch_flight_records`` - Cancel an active fetch job

Published Topics (Sent to ``command/web``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The petal publishes status updates and progress to ``command/web`` with the following topics:

**Progress Streams:**

- ``/petal-flight-log/log_download/progress`` - ULog download progress updates
- ``/petal-flight-log/s3_upload/progress`` - S3 upload progress updates

**Job Status Streams:**

- ``/petal-flight-log/publish_sync_job_value_stream`` - Sync job status and progress
- ``/petal-flight-log/publish_fetch_flight_records_job_value_stream`` - Fetch job status and progress
- ``/petal-flight-log/publish_bulk_delete_job_value_stream`` - Bulk delete job status and progress
- ``/petal-flight-log/publish_clear_all_ulogs_job_value_stream`` - Clear all ULogs job status and progress

**Job Results:**

- ``/petal-flight-log/delete_flight_record`` - Delete operation result
- ``/petal-flight-log/cancel_sync_job`` - Cancel operation result
- ``/petal-flight-log/check_sync_job`` - Sync job check result

See Also
--------

- :doc:`../development_contribution/using_proxies` - Proxy usage documentation
- :doc:`../changelog` - Version history and changes
