"""
Configuration utilities for petal-app-manager
"""
import yaml
from pathlib import Path
import logging

def ensure_proxies_config_exists(config_path: Path) -> None:
    """
    Ensure proxies.yaml exists. If not, create it with default configuration.
    
    Args:
        config_path: Path to the proxies.yaml file
    """
    if not config_path.exists():
        logger = logging.getLogger(__name__)
        logger.warning(f"proxies.yaml not found at {config_path}. Creating with default configuration.")
        
        # Default configuration based on current working setup
        default_config = {
            'enabled_petals': [
                'flight_records',
                'mission_planner', 
                'petal_warehouse'
            ],
            'enabled_proxies': [
                'redis',
                'bucket',
                'ext_mavlink',
                'ftp_mavlink',
                'db',
                'cloud'
            ],
            'petal_dependencies': {
                'flight_records': ['redis', 'cloud'],
                'mission_planner': ['redis', 'ext_mavlink'],
                'petal_warehouse': ['redis', 'ext_mavlink']
            },
            'proxy_dependencies': {
                'bucket': ['cloud'],
                'db': ['cloud']
            }
        }
        
        # Create parent directory if it doesn't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the default configuration
        with open(config_path, 'w') as f:
            yaml.safe_dump(default_config, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Created default proxies.yaml at {config_path}")


def load_proxies_config(config_path: Path) -> dict:
    """
    Load proxies configuration, creating default if missing.
    
    Args:
        config_path: Path to the proxies.yaml file
        
    Returns:
        dict: Configuration dictionary
    """
    ensure_proxies_config_exists(config_path)
    
    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}
    
    return config
