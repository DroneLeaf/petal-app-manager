# CSV Signal Logging Tool

A utility for Petal apps to easily log scalar or multi-dimensional signals to CSV files.

## Features

- Log scalar values or multi-dimensional data
- Automatic timestamping
- Configurable buffer size for performance optimization
- Automatic file cleanup when objects go out of scope
- Custom file naming and headers
- Thread-safe operation

## Usage

### Basic Usage

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

### Advanced Options

```python
# Custom timestamp precision and buffer size
channel = open_channel(
    "sensor_value",
    base_dir="sensor_logs",
    file_name="temperature",
    use_ms=False,  # Use seconds precision instead of milliseconds
    buffer_size=1000,  # Flush to disk every 1000 records
)

# Add to an existing file instead of creating a new one
channel = open_channel(
    "sensor_value",
    base_dir="sensor_logs",
    file_name="existing_file",
    append=True
)
```

## API Reference

### `open_channel(headers, **kwargs)`

Creates and returns a new logging channel.

#### Parameters

- `headers` (str or list of str): Column name(s) for the data. For multi-dimensional data, provide a list of headers.
- `base_dir` (str or Path, optional): Directory where log files will be stored. Default: "logs"
- `file_name` (str, optional): Name of the CSV file. If not provided, it will be generated from the headers.
- `use_ms` (bool, optional): Whether to use milliseconds precision for timestamps (True) or seconds (False). Default: True
- `buffer_size` (int, optional): Number of records to buffer before writing to disk. Default: 100
- `append` (bool, optional): If True, append to an existing file rather than creating a new one. Default: False

#### Returns

A `LogChannel` object that can be used to log data.

### `LogChannel` Methods

- `push(value)`: Record a value to this channel. For multi-dimensional channels, this should be a list with the same length as the headers list.
- `flush()`: Write all buffered values to the file immediately.
- `close()`: Close the channel and its associated file.

## Example Petal

Check out the `LoggingExamplePetal` in the examples directory for a complete working example of how to use this tool in a Petal app.

## Testing

Run the unit tests to verify the functionality:

```bash
pytest tests/test_log_tool.py
```
