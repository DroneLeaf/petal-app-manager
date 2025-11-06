Advanced Debugging and Logging
===============================

This guide covers advanced debugging techniques and logging configurations for Petal App Manager development, including per-level logging control and high-speed data logging to CSV files.

Overview
--------

Effective debugging and logging are crucial for:

- **Development**: Understanding code flow and identifying issues
- **Production**: Monitoring system health and diagnosing problems
- **Performance Analysis**: Capturing high-frequency data streams
- **Field Debugging**: Remote troubleshooting and log analysis

Available Logging Tools
-----------------------

.. list-table:: Logging Tools and Use Cases
   :header-rows: 1
   :widths: 25 75

   * - Tool
     - Use Cases
   * - Per-Level Logging
     - Control output destinations (terminal/file) for each log level
   * - CSV Signal Logging
     - High-performance logging of scalar/multi-dimensional data streams
   * - Standard Python Logging
     - General application logging with structured messages
   * - Admin Dashboard Logs
     - Real-time log streaming and filtering via web interface

Per-Level Logging Configuration
-------------------------------

**Purpose:** Fine-grained control over where each log level appears (terminal, file, or both)

**Benefits:**
- Reduce terminal noise in production
- Maintain comprehensive file logs for analysis
- Show only critical issues in terminal during deployment
- Customize logging behavior per environment

Configuration Methods
~~~~~~~~~~~~~~~~~~~~~

**Method 1: JSON Configuration File (Recommended)**

Edit ``config.json`` in the project root:

.. code-block:: javascript

   {
       "allowed_origins": ["..."],
       "logging": {
           "level_outputs": {
               "DEBUG": ["file"],
               "INFO": ["terminal", "file"],
               "WARNING": ["terminal", "file"], 
               "ERROR": ["terminal", "file"],
               "CRITICAL": ["terminal", "file"]
           }
       }
   }

**Method 2: Programmatic Configuration**

.. code-block:: python

   from petal_app_manager.logger import setup_logging

   level_outputs = {
       "DEBUG": ["file"],
       "INFO": ["terminal", "file"], 
       "WARNING": ["terminal"],
       "ERROR": ["terminal", "file"],
       "CRITICAL": ["file"]
   }

   logger = setup_logging(
       log_level="DEBUG",
       app_prefixes=("myapp_",),
       log_to_file=True,
       level_outputs=level_outputs
   )

Output Options
~~~~~~~~~~~~~~

For each log level, specify destinations:

- **``["terminal"]``**: Console output only
- **``["file"]``**: Log file output only  
- **``["terminal", "file"]``**: Both console and file output

Common Configuration Scenarios
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Development Mode:**

.. code-block:: json

   {
       "logging": {
           "level_outputs": {
               "DEBUG": ["terminal"],
               "INFO": ["terminal"],
               "WARNING": ["terminal", "file"],
               "ERROR": ["terminal", "file"],
               "CRITICAL": ["terminal", "file"]
           }
       }
   }

**Production Mode:**

.. code-block:: json

   {
       "logging": {
           "level_outputs": {
               "DEBUG": ["file"],
               "INFO": ["file"],
               "WARNING": ["terminal"],
               "ERROR": ["terminal", "file"],
               "CRITICAL": ["terminal", "file"]
           }
       }
   }

**Debug Mode (Maximum Visibility):**

.. code-block:: json

   {
       "logging": {
           "level_outputs": {
               "DEBUG": ["terminal", "file"],
               "INFO": ["terminal", "file"],
               "WARNING": ["terminal", "file"],
               "ERROR": ["terminal", "file"],
               "CRITICAL": ["terminal", "file"]
           }
       }
   }

**Silent Mode (Minimal Terminal Noise):**

.. code-block:: json

   {
       "logging": {
           "level_outputs": {
               "DEBUG": ["file"],
               "INFO": ["file"],
               "WARNING": ["file"],
               "ERROR": ["terminal"],
               "CRITICAL": ["terminal"]
           }
       }
   }

Legacy Format Support
~~~~~~~~~~~~~~~~~~~~~

The system maintains backward compatibility:

- **``"terminal"``**: Converted to ``["terminal"]``
- **``"file"``**: Converted to ``["file"]``
- **``"both"``**: Converted to ``["terminal", "file"]``

CSV Signal Logging Tool
-----------------------

**Purpose:** High-performance logging of scalar or multi-dimensional data streams to CSV files

**Use Cases:**
- Real-time telemetry data capture
- Sensor readings and flight parameters
- Performance metrics and timing data
- Multi-dimensional position/orientation tracking
- High-frequency signal analysis

Basic Usage
~~~~~~~~~~~

**Scalar Data Logging:**

.. code-block:: python

   from petal_app_manager.utils.log_tool import open_channel

   class TelemetryPetal(Petal):
       def __init__(self):
           super().__init__()
           # Create a channel for altitude logging
           self.altitude_channel = open_channel("altitude", base_dir="flight_logs")
           
       async def log_telemetry(self, altitude_value: float):
           # Log altitude reading
           self.altitude_channel.push(altitude_value)

**Multi-Dimensional Data Logging:**

.. code-block:: python

   from petal_app_manager.utils.log_tool import open_channel

   class PositionPetal(Petal):
       def __init__(self):
           super().__init__()
           # Create a channel for 3D position data
           self.position_channel = open_channel(
               ["pos_x", "pos_y", "pos_z"], 
               base_dir="flight_logs",
               file_name="position_data"
           )
           
       async def log_position(self, x: float, y: float, z: float):
           # Log position coordinates
           self.position_channel.push([x, y, z])

Advanced Configuration
~~~~~~~~~~~~~~~~~~~~~~

**Custom Settings:**

.. code-block:: python

   # High-performance logging with custom settings
   channel = open_channel(
       "sensor_value",
       base_dir="sensor_logs",
       file_name="temperature",
       use_ms=False,         # Use seconds instead of milliseconds
       buffer_size=1000,     # Flush every 1000 records for performance
   )

**Append to Existing Files:**

.. code-block:: python

   # Continue logging to existing file
   channel = open_channel(
       "sensor_value",
       base_dir="sensor_logs", 
       file_name="existing_file",
       append=True
   )

**Manual Buffer Control:**

.. code-block:: python

   # Explicit flushing for critical data
   channel.push(critical_value)
   channel.flush()  # Ensure data is written immediately

Complete Petal Example
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from petal_app_manager.plugins.base import Petal
   from petal_app_manager.utils.log_tool import open_channel
   import asyncio
   import time

   class FlightDataLogger(Petal):
       def __init__(self):
           super().__init__()
           # Create multiple logging channels
           self.altitude_log = open_channel("altitude", base_dir="flight_data")
           self.velocity_log = open_channel(
               ["vel_x", "vel_y", "vel_z"], 
               base_dir="flight_data",
               file_name="velocity"
           )
           self.attitude_log = open_channel(
               ["roll", "pitch", "yaw"],
               base_dir="flight_data", 
               file_name="attitude",
               buffer_size=500  # High-frequency attitude data
           )
           
       async def start(self):
           """Start logging telemetry data"""
           self.logger.info("Starting flight data logging")
           
           # Start telemetry collection loop
           asyncio.create_task(self.telemetry_loop())
           
       async def telemetry_loop(self):
           """Main telemetry collection loop"""
           while True:
               try:
                   # Get telemetry from MAVLink proxy
                   mavlink_proxy = self.get_proxy("ext_mavlink")
                   if mavlink_proxy:
                       telemetry = await mavlink_proxy.get_telemetry()
                       
                       # Log altitude
                       if 'altitude' in telemetry:
                           self.altitude_log.push(telemetry['altitude'])
                           
                       # Log velocity vector
                       if all(k in telemetry for k in ['vx', 'vy', 'vz']):
                           self.velocity_log.push([
                               telemetry['vx'], 
                               telemetry['vy'], 
                               telemetry['vz']
                           ])
                           
                       # Log attitude
                       if all(k in telemetry for k in ['roll', 'pitch', 'yaw']):
                           self.attitude_log.push([
                               telemetry['roll'],
                               telemetry['pitch'], 
                               telemetry['yaw']
                           ])
                           
               except Exception as e:
                   self.logger.error(f"Telemetry logging error: {e}")
                   
               await asyncio.sleep(0.1)  # 10Hz logging rate
               
       async def stop(self):
           """Clean shutdown of logging channels"""
           self.logger.info("Stopping flight data logging")
           
           # Close all logging channels
           self.altitude_log.close()
           self.velocity_log.close() 
           self.attitude_log.close()

API Reference
~~~~~~~~~~~~~

**``open_channel(headers, **kwargs)``**

Creates a new logging channel.

**Parameters:**
- ``headers`` (str or list): Column name(s) for data
- ``base_dir`` (str, optional): Directory for log files (default: "logs")
- ``file_name`` (str, optional): CSV file name (auto-generated if not provided)
- ``use_ms`` (bool, optional): Millisecond timestamp precision (default: True)
- ``buffer_size`` (int, optional): Records to buffer before writing (default: 100)
- ``append`` (bool, optional): Append to existing file (default: False)

**``LogChannel`` Methods:**
- ``push(value)``: Record a value (scalar or list for multi-dimensional)
- ``flush()``: Write buffered data immediately
- ``close()``: Close channel and file

Debugging Best Practices
------------------------

Environment-Specific Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Development Environment:**

.. code-block:: python

   # In your petal's __init__ method
   import os
   
   if os.getenv("PETAL_ENV") == "development":
       self.logger.setLevel("DEBUG")
       # Enable verbose CSV logging
       self.debug_channel = open_channel(
           ["timestamp", "debug_value", "state"],
           base_dir="debug_logs",
           buffer_size=10  # Frequent flushing for debugging
       )

**Production Environment:**

.. code-block:: python

   # Production logging configuration
   if os.getenv("PETAL_ENV") == "production":
       # Use file-only logging for most levels
       self.logger.setLevel("INFO")
       # Efficient CSV logging
       self.metrics_channel = open_channel(
           ["metric_name", "value"],
           base_dir="metrics",
           buffer_size=1000  # Less frequent flushing
       )

Performance Considerations
~~~~~~~~~~~~~~~~~~~~~~~~~~

**High-Frequency Logging:**

.. code-block:: python

   # For data rates > 100Hz
   high_freq_channel = open_channel(
       ["timestamp", "sensor_value"],
       buffer_size=5000,     # Large buffer for performance
       use_ms=True          # Millisecond precision
   )

**Memory Management:**

.. code-block:: python

   # Periodic flushing for long-running processes
   async def periodic_flush(self):
       while True:
           await asyncio.sleep(30)  # Flush every 30 seconds
           self.data_channel.flush()

Error Handling and Recovery
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class RobustLoggingPetal(Petal):
       def __init__(self):
           super().__init__()
           self.setup_logging_with_fallback()
           
       def setup_logging_with_fallback(self):
           try:
               self.primary_channel = open_channel(
                   "primary_data",
                   base_dir="primary_logs"
               )
           except Exception as e:
               self.logger.error(f"Primary logging failed: {e}")
               # Fallback to basic logging
               self.primary_channel = None
               
       async def log_data_safely(self, data):
           try:
               if self.primary_channel:
                   self.primary_channel.push(data)
               else:
                   # Fallback to standard logging
                   self.logger.info(f"Data: {data}")
           except Exception as e:
               self.logger.error(f"Logging failed: {e}")

Integration with Admin Dashboard
---------------------------------

**Real-Time Log Monitoring:**

The Admin Dashboard at ``http://localhost:9000/admin-dashboard`` provides:

- **Live Log Streaming**: WebSocket-based real-time log display
- **Log Level Filtering**: Filter by DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Component Filtering**: View logs from specific petals or proxies
- **Search Functionality**: Find specific log messages
- **Export Options**: Download log segments for analysis

**CSV File Monitoring:**

.. code-block:: python

   # Add CSV logging status to health checks
   class MonitoredPetal(Petal):
       async def health_check(self):
           health = await super().health_check()
           
           # Add CSV logging status
           health["csv_logging"] = {
               "active_channels": len(self.active_channels),
               "last_flush": self.last_flush_time,
               "buffer_usage": self.get_buffer_usage()
           }
           
           return health

Testing and Validation
----------------------

**Testing Log Configuration:**

.. code-block:: bash

   # Validate config.json parsing
   python3 -c "
   import json
   with open('config.json') as f:
       config = json.load(f)
       print('Config valid:', config.get('logging', {}))
   "

**Testing CSV Logging:**

.. code-block:: python

   # Unit test for CSV logging
   def test_csv_logging():
       from petal_app_manager.utils.log_tool import open_channel
       
       # Test scalar logging
       channel = open_channel("test_value", base_dir="test_logs")
       channel.push(42.0)
       channel.push(43.5)
       channel.close()
       
       # Verify file exists and contains data
       assert os.path.exists("test_logs/test_value_*.csv")

**Performance Testing:**

.. code-block:: python

   # Benchmark high-frequency logging
   import time
   from petal_app_manager.utils.log_tool import open_channel
   
   def benchmark_logging():
       channel = open_channel("benchmark", buffer_size=10000)
       
       start_time = time.time()
       for i in range(100000):
           channel.push(i * 0.1)
       
       channel.close()
       duration = time.time() - start_time
       print(f"Logged 100k records in {duration:.2f}s ({100000/duration:.0f} Hz)")

File Management
---------------

**Automatic File Naming:**

CSV files are automatically named with timestamps:
- ``{base_dir}/{file_name}_{timestamp}.csv``
- Example: ``flight_logs/altitude_20251105_143022.csv``

**Log Rotation:**

.. code-block:: python

   # Implement log rotation for long-running processes
   class RotatingLogger:
       def __init__(self, base_name, max_records=100000):
           self.base_name = base_name
           self.max_records = max_records
           self.current_records = 0
           self.file_index = 0
           self.create_new_channel()
           
       def create_new_channel(self):
           file_name = f"{self.base_name}_{self.file_index:04d}"
           self.channel = open_channel("data", file_name=file_name)
           self.current_records = 0
           self.file_index += 1
           
       def log(self, data):
           self.channel.push(data)
           self.current_records += 1
           
           if self.current_records >= self.max_records:
               self.channel.close()
               self.create_new_channel()

**Cleanup and Archival:**

.. code-block:: python

   # Cleanup old log files
   import os
   import time
   from pathlib import Path

   def cleanup_old_logs(log_dir="logs", max_age_days=7):
       """Remove log files older than max_age_days"""
       cutoff_time = time.time() - (max_age_days * 24 * 3600)
       
       for log_file in Path(log_dir).glob("*.csv"):
           if log_file.stat().st_mtime < cutoff_time:
               log_file.unlink()
               print(f"Removed old log file: {log_file}")

Troubleshooting
---------------

**Common Issues:**

1. **Permission Errors**: Ensure log directories are writable
2. **Disk Space**: Monitor available space for log files
3. **Buffer Overflow**: Increase buffer size for high-frequency logging
4. **File Locking**: Close channels properly to avoid file locks

**Debug Checklist:**

.. code-block:: python

   # Diagnostic function for logging issues
   def diagnose_logging():
       import os
       import json
       
       print("=== Logging Diagnostics ===")
       
       # Check config.json
       try:
           with open("config.json") as f:
               config = json.load(f)
               print("✓ config.json loaded successfully")
               print(f"  Logging config: {config.get('logging', 'Not configured')}")
       except Exception as e:
           print(f"✗ config.json error: {e}")
           
       # Check log directory permissions
       log_dir = "logs"
       if os.path.exists(log_dir):
           if os.access(log_dir, os.W_OK):
               print(f"✓ {log_dir} directory is writable")
           else:
               print(f"✗ {log_dir} directory is not writable")
       else:
           print(f"✗ {log_dir} directory does not exist")
           
       # Check disk space
       stat = os.statvfs(".")
       available_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
       print(f"  Available disk space: {available_gb:.1f} GB")

Next Steps
----------

- Review the :doc:`adding_petals` guide for petal development basics
- Check :doc:`using_proxies` for proxy integration patterns  
- Explore existing petals for real-world logging examples
- Use the Admin Dashboard for real-time log monitoring
- Implement appropriate logging strategies for your use case

.. note::
   **Performance Tip**: For high-frequency data logging (>1kHz), consider using larger buffer sizes (1000-10000) and ensure adequate disk I/O performance. Monitor system resources during intensive logging operations.