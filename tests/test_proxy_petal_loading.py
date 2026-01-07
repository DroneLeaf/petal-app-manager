import pytest
from fastapi import FastAPI
from unittest.mock import MagicMock
import yaml

from petal_app_manager.plugins.loader import load_petals

@pytest.fixture
def mock_logger():
    class DummyLogger:
        def __init__(self):
            self.errors = []
            self.infos = []
            self.warnings = []
            self.debugs = []
        def error(self, msg, *args, **kwargs): self.errors.append(msg % args if args else msg)
        def info(self, msg, *args, **kwargs): self.infos.append(msg % args if args else msg)
        def warning(self, msg, *args, **kwargs): self.warnings.append(msg % args if args else msg)
        def debug(self, msg, *args, **kwargs): self.debugs.append(msg % args if args else msg)
    return DummyLogger()

@pytest.fixture
def dummy_app():
    return FastAPI()

@pytest.fixture
def dummy_proxies():
    # Simulate proxies dict with dummy objects
    return {"redis": MagicMock(), "cloud": MagicMock(), "ext_mavlink": MagicMock()}

@pytest.fixture
def dummy_entry_points(monkeypatch):
    class DummyEP:
        def __init__(self, name):
            self.name = name
        def load(self):
            class DummyPetal:
                name = self.name
                version = "1.0"
                def inject_proxies(self, proxies): self._proxies = proxies
                def startup(self): pass
            return DummyPetal
    eps = [
        DummyEP("petal_warehouse"),
        DummyEP("flight_records"),
        DummyEP("mission_planner"),
    ]
    monkeypatch.setattr("importlib.metadata.entry_points", lambda group=None: eps if group == "petal.plugins" else [])
    yield

def test_petals_loaded_when_dependencies_met(tmp_path, monkeypatch, dummy_app, dummy_proxies, mock_logger, dummy_entry_points):
    config = {
        "enabled_proxies": ["redis", "cloud", "ext_mavlink"],
        "enabled_petals": ["petal_warehouse", "flight_records", "mission_planner"],
        "petal_dependencies": {
            "petal_warehouse": ["redis", "ext_mavlink"],
            "flight_records": ["redis", "cloud"],
            "mission_planner": ["redis", "ext_mavlink"]
        }
    }
    
    # Mock load_proxies_config directly - simpler and more reliable
    def mock_load_config(config_path):
        return config
    
    monkeypatch.setattr("petal_app_manager.config.load_proxies_config", mock_load_config)

    petal_name_list = ["petal_warehouse", "flight_records", "mission_planner"]
    petals = load_petals(dummy_app, petal_name_list, dummy_proxies, mock_logger)
    loaded_names = [p.name for p in petals]
    assert set(loaded_names) == {"petal_warehouse", "flight_records", "mission_planner"}
    assert not mock_logger.errors

def test_petals_skipped_when_proxy_missing(tmp_path, monkeypatch, dummy_app, dummy_proxies, mock_logger, dummy_entry_points):
    config = {
        "enabled_proxies": ["redis"],
        "enabled_petals": ["petal_warehouse", "flight_records", "mission_planner"],
        "petal_dependencies": {
            "petal_warehouse": ["redis", "ext_mavlink"],
            "flight_records": ["redis", "cloud"],
            "mission_planner": ["redis", "ext_mavlink"]
        }
    }
    
    # Mock load_proxies_config directly - simpler and more reliable
    def mock_load_config(config_path):
        return config
    
    monkeypatch.setattr("petal_app_manager.config.load_proxies_config", mock_load_config)

    petal_name_list = ["petal_warehouse", "flight_records", "mission_planner"]
    petals = load_petals(dummy_app, petal_name_list, {"redis": MagicMock()}, mock_logger)
    loaded_names = [p.name for p in petals]
    assert loaded_names == []
    assert any("Cannot load petal_warehouse" in e for e in mock_logger.errors)
    assert any("Cannot load flight_records" in e for e in mock_logger.errors)
    assert any("Cannot load mission_planner" in e for e in mock_logger.errors)

def test_partial_petals_loaded(tmp_path, monkeypatch, dummy_app, dummy_proxies, mock_logger, dummy_entry_points):
    config = {
        "enabled_proxies": ["redis", "ext_mavlink"],
        "enabled_petals": ["petal_warehouse", "flight_records", "mission_planner"],
        "petal_dependencies": {
            "petal_warehouse": ["redis", "ext_mavlink"],
            "flight_records": ["redis", "cloud"],
            "mission_planner": ["redis", "ext_mavlink"]
        }
    }
    
    # Mock load_proxies_config directly - simpler and more reliable
    def mock_load_config(config_path):
        return config
    
    monkeypatch.setattr("petal_app_manager.config.load_proxies_config", mock_load_config)

    petal_name_list = ["petal_warehouse", "flight_records", "mission_planner"]
    petals = load_petals(dummy_app, petal_name_list, {"redis": MagicMock(), "ext_mavlink": MagicMock()}, mock_logger)
    loaded_names = [p.name for p in petals]
    print("Loaded petals:", loaded_names)
    print("Logger errors:", mock_logger.errors)
    assert set(loaded_names) == {"petal_warehouse", "mission_planner"}
    assert any("Cannot load flight_records" in e for e in mock_logger.errors)