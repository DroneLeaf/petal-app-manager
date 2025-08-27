# conftest.py
import pytest

def pytest_addoption(parser):
    parser.addoption(
        "--hardware",
        action="store_true",
        default=False,
        help="run tests that require real hardware",
    )

def pytest_configure(config):
    config.addinivalue_line("markers", "hardware: mark test as requiring hardware")

def pytest_collection_modifyitems(config, items):
    """Skip hardware tests unless --hardware is given."""
    if config.getoption("--hardware"):
        return
    skip_hw = pytest.mark.skip(reason="need --hardware to run hardware tests")
    for item in items:
        if "hardware" in item.keywords:
            item.add_marker(skip_hw)
