# conftest.py
import os
import pytest
import tempfile

def pytest_addoption(parser):
    parser.addoption(
        "--hardware",
        action="store_true",
        default=False,
        help="run tests that require real hardware",
    )

def pytest_configure(config):
    config.addinivalue_line("markers", "hardware: mark test as requiring hardware")
    
    # Set up test environment variables before any tests run
    # Use a temporary directory for logs during tests
    test_log_dir = tempfile.mkdtemp(prefix="petal_test_logs_")
    os.environ["PETAL_LOG_DIR"] = test_log_dir
    os.environ["PETAL_LOG_TO_FILE"] = "false"  # Disable file logging in tests

def pytest_collection_modifyitems(config, items):
    """Skip hardware tests unless --hardware is given."""
    if config.getoption("--hardware"):
        return
    skip_hw = pytest.mark.skip(reason="need --hardware to run hardware tests")
    for item in items:
        if "hardware" in item.keywords:
            item.add_marker(skip_hw)
