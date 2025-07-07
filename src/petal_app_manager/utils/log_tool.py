"""
CSV Signal Logging Tool
======================

A utility for Petal apps to easily log scalar or multi-dimensional signals to CSV files.

Usage:
------
```python
from petal_app_manager.utils.log_tool import open_channel

# Create a channel for a scalar value
ch1 = open_channel("altitude", base_dir="flight_logs")

# Log some values
ch1.push(10.5)
ch1.push(11.2)

# Create a channel for multi-dimensional values
ch2 = open_channel(["pos_x", "pos_y", "pos_z"], 
                   base_dir="flight_logs",
                   file_name="position_data")

# Log position values
ch2.push([1.0, 2.0, 3.0])
ch2.push([1.1, 2.2, 3.3])

# Channels are automatically closed when they go out of scope,
# but can be explicitly closed if needed
ch1.close()
ch2.close()
```
"""

import os
import csv
import time
import weakref
import logging
import datetime
import atexit
from pathlib import Path
from typing import List, Union, Optional, Any, Dict

# Get a logger for this module
logger = logging.getLogger("loggingtool")

# Registry of open channels to ensure proper cleanup
_open_channels = weakref.WeakSet()

class LogChannel:
    """
    A channel for logging scalar or multi-dimensional signals to a CSV file.
    
    Each channel manages a single CSV file with either one column for
    scalar values or multiple columns for multi-dimensional values.
    """
    
    def __init__(
        self, 
        headers: Union[str, List[str]], 
        base_dir: Union[str, Path] = "logs",
        file_name: Optional[str] = None,
        use_ms: bool = True,
        buffer_size: int = 100,
        append: bool = False
    ):
        """
        Initialize a logging channel.
        
        Parameters
        ----------
        headers : Union[str, List[str]]
            Column name(s) for the data. For multi-dimensional data, provide a list of headers.
        base_dir : Union[str, Path], optional
            Directory where log files will be stored, by default "logs"
        file_name : Optional[str], optional
            Name of the CSV file. If not provided, it will be generated from the headers.
        use_ms : bool, optional
            Whether to use milliseconds precision for timestamps (True) or seconds (False), by default True
        buffer_size : int, optional
            Number of records to buffer before writing to disk, by default 100
        append : bool, optional
            If True, append to an existing file rather than creating a new one, by default False
        
        Raises
        ------
        ValueError
            If headers are not provided or are invalid
        """
        # Validate headers
        if not headers:
            raise ValueError("Headers must be provided")
            
        # Convert single header to list for consistent handling
        self.headers = [headers] if isinstance(headers, str) else headers
        self.is_scalar = isinstance(headers, str)
        self.use_ms = use_ms
        self.buffer_size = buffer_size
        
        # Create directory
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename if not provided
        if not file_name:
            if self.is_scalar:
                file_name = f"{headers}"
            else:
                file_name = f"{self.headers[0]}_etc"
        
        # Add timestamp to filename to ensure uniqueness
        # We still use a readable date format for filenames
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file_path = self.base_dir / f"{file_name}_{timestamp}.csv"
        
        # Set up headers for CSV - always include timestamp as first column
        csv_headers = ["timestamp"]
        csv_headers.extend(self.headers)
        
        # Initialize buffer and file
        self.buffer = []
        self.file_mode = 'a' if append else 'w'
        self.file = None
        self.writer = None
        self._open_file()
        
        # Write headers if in write mode
        if self.file_mode == 'w':
            self.writer.writerow(csv_headers)
            self.file.flush()
            
        # Register this channel for cleanup
        _open_channels.add(self)
        logger.debug(f"Created log channel for {self.headers} at {self.file_path}")
    
    def _open_file(self):
        """Open the CSV file and create writer."""
        try:
            self.file = open(self.file_path, self.file_mode, newline='')
            self.writer = csv.writer(self.file)
        except Exception as e:
            logger.error(f"Failed to open log file {self.file_path}: {e}")
            raise
    
    def push(self, value: Union[float, int, List[float], List[int]]) -> None:
        """
        Record a value to this channel.
        
        Parameters
        ----------
        value : Union[float, int, List[float], List[int]]
            The value to record. For multi-dimensional channels, this should be a list
            with the same length as the headers list.
            
        Raises
        ------
        ValueError
            If the value doesn't match the expected dimensions
        """
        if self.file is None:
            logger.error("Attempting to push to a closed channel")
            return
            
        if self.is_scalar:
            if isinstance(value, (list, tuple)):
                raise ValueError(f"Expected scalar value but got {value}")
            data = [value]
        else:
            if not isinstance(value, (list, tuple)):
                raise ValueError(f"Expected list but got {value}")
            if len(value) != len(self.headers):
                raise ValueError(f"Expected {len(self.headers)} values but got {len(value)}")
            data = value
            
        # Always add timestamp as the first column (Unix epoch time)
        if self.use_ms:
            # Millisecond precision (int)
            timestamp = int(time.time() * 1000)
        else:
            # Second precision (int)
            timestamp = int(time.time())
            
        row = [timestamp]
        row.extend(data)
        
        # Add to buffer
        self.buffer.append(row)
        
        # Flush if buffer is full
        if len(self.buffer) >= self.buffer_size:
            self.flush()
    
    def flush(self) -> None:
        """Write all buffered values to the file."""
        if self.file is None or not self.buffer:
            return
            
        try:
            self.writer.writerows(self.buffer)
            self.file.flush()
            self.buffer = []
        except Exception as e:
            logger.error(f"Failed to write to log file {self.file_path}: {e}")
    
    def close(self) -> None:
        """Close the channel and its associated file."""
        if self.file is None:
            return
            
        try:
            self.flush()
            self.file.close()
            self.file = None
            self.writer = None
            logger.debug(f"Closed log channel at {self.file_path}")
        except Exception as e:
            logger.error(f"Error closing log file {self.file_path}: {e}")
    
    def __del__(self):
        """Ensure the file is closed when the object is garbage collected."""
        self.close()


def open_channel(
    headers: Union[str, List[str]], 
    **kwargs
) -> LogChannel:
    """
    Create and return a new logging channel.
    
    This is the main entry point for the logging tool.
    
    Parameters
    ----------
    headers : Union[str, List[str]]
        Column name(s) for the data. For multi-dimensional data, provide a list of headers.
    **kwargs
        Additional arguments to pass to LogChannel constructor.
        
    Returns
    -------
    LogChannel
        A new logging channel object
    """
    return LogChannel(headers, **kwargs)


def _cleanup():
    """Close all open channels when the program exits."""
    for channel in list(_open_channels):
        channel.close()


# Register cleanup function to run at program exit
atexit.register(_cleanup)
