"""
Unit tests for the CSV signal logging tool.
"""

import os
import csv
import tempfile
import pytest
from pathlib import Path

from petal_app_manager.utils.log_tool import open_channel, LogChannel


def test_scalar_channel():
    """Test logging scalar values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a scalar channel
        channel = open_channel(
            "test_value",
            base_dir=tmpdir,
            file_name="scalar_test"
        )
        
        # Push some values
        test_values = [1.0, 2.5, 3.7]
        for val in test_values:
            channel.push(val)
        
        # Close the channel to ensure data is written
        channel.close()
        
        # Find the created file
        csv_files = list(Path(tmpdir).glob("*.csv"))
        assert len(csv_files) == 1
        
        # Check file contents
        with open(csv_files[0], 'r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
            # First row should be the header with timestamp
            assert rows[0] == ["timestamp", "test_value"]
            
            # Check data rows
            data_rows = rows[1:]
            assert len(data_rows) == len(test_values)
            
            for i, val in enumerate(test_values):
                # Check that timestamp is present (index 0) and value is correct (index 1)
                assert float(data_rows[i][1]) == val


def test_multidim_channel():
    """Test logging multi-dimensional values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a multi-dimensional channel
        headers = ["x", "y", "z"]
        channel = open_channel(
            headers,
            base_dir=tmpdir,
            file_name="vector_test"
        )
        
        # Push some values
        test_values = [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0]
        ]
        for val in test_values:
            channel.push(val)
        
        # Close the channel to ensure data is written
        channel.close()
        
        # Find the created file
        csv_files = list(Path(tmpdir).glob("*.csv"))
        assert len(csv_files) == 1
        
        # Check file contents
        with open(csv_files[0], 'r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
            # First row should be the header with timestamp
            expected_headers = ["timestamp"] + headers
            assert rows[0] == expected_headers
            
            # Check data rows
            data_rows = rows[1:]
            assert len(data_rows) == len(test_values)
            
            for i, expected_vals in enumerate(test_values):
                # Skip the timestamp column (index 0)
                actual_vals = [float(v) for v in data_rows[i][1:]]
                assert actual_vals == expected_vals


def test_timestamp_precision():
    """Test that timestamp precision can be customized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test with seconds precision
        seconds_channel = open_channel(
            "test_value",
            base_dir=tmpdir,
            file_name="seconds_timestamp_test",
            use_ms=False  # Use seconds precision
        )
        
        # Push a value
        seconds_channel.push(1.0)
        seconds_channel.close()
        
        # Find the created file
        seconds_files = list(Path(tmpdir).glob("seconds_*.csv"))
        
        # Check file contents
        with open(seconds_files[0], 'r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
            # Verify timestamp is an integer with seconds precision
            timestamp = int(rows[1][0])
            # Should be a 10-digit number (seconds precision, valid for many decades)
            assert 1000000000 < timestamp < 10000000000
            
        # Test with milliseconds precision (default)
        ms_channel = open_channel(
            "test_value",
            base_dir=tmpdir,
            file_name="ms_timestamp_test",
            use_ms=True  # Use milliseconds precision (default)
        )
        
        # Push a value
        ms_channel.push(1.0)
        ms_channel.close()
        
        # Find the created file
        ms_files = list(Path(tmpdir).glob("ms_*.csv"))
        
        # Check file contents
        with open(ms_files[0], 'r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
            # Verify timestamp is an integer with milliseconds precision
            timestamp = int(rows[1][0])
            # Should be a 13-digit number (milliseconds precision)
            assert 1000000000000 < timestamp < 10000000000000


def test_buffer_flushing():
    """Test that buffer is flushed when it reaches buffer_size."""
    with tempfile.TemporaryDirectory() as tmpdir:
        buffer_size = 5
        channel = open_channel(
            "test_value",
            base_dir=tmpdir,
            file_name="buffer_test",
            buffer_size=buffer_size
        )
        
        # Push values up to buffer_size - 1
        for i in range(buffer_size - 1):
            channel.push(float(i))
            
        # Find the created file
        csv_files = list(Path(tmpdir).glob("*.csv"))
        
        # Check that only the header is written
        with open(csv_files[0], 'r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 1  # Just the header
        
        # Push one more value to trigger flush
        channel.push(float(buffer_size))
        
        # Check that all values are written
        with open(csv_files[0], 'r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == buffer_size + 1  # Header + buffer_size rows
        
        channel.close()


def test_error_handling():
    """Test error handling for invalid inputs."""
    channel = open_channel("test")
    
    # Test pushing wrong type to scalar channel
    with pytest.raises(ValueError):
        channel.push([1, 2, 3])
    
    channel.close()
    
    # Test multi-dimensional channel with wrong size
    channel = open_channel(["x", "y", "z"])
    
    with pytest.raises(ValueError):
        channel.push([1, 2])  # Only 2 values for 3 headers
    
    channel.close()


def test_cleanup():
    """Test that channels are properly cleaned up."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a channel but don't explicitly close it
        channel = open_channel(
            "test_value",
            base_dir=tmpdir,
            file_name="cleanup_test"
        )
        
        # Push a value
        channel.push(1.0)
        
        # Let the channel go out of scope, which should trigger __del__
        del channel
        
        # Find the created file
        csv_files = list(Path(tmpdir).glob("*.csv"))
        
        # Check file contents to ensure data was written
        with open(csv_files[0], 'r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 2  # Header + 1 data row
