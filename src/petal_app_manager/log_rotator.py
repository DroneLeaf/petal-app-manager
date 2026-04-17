#!/usr/bin/env python3
"""
Log rotation utility for Petal App Manager.

Rotates log files when app.log exceeds 1KB.
Moves all *.log files from base directory to base_dir/logs/log_{date}_{time}/
"""

import shutil
from pathlib import Path
from datetime import datetime
import logging


def rotate_logs_if_needed(base_dir: Path = None, logger: logging.Logger = None) -> None:
    """
    Rotate log files if app.log exceeds 1KB.
    
    Moves all *.log files from base_dir to base_dir/logs/log_{date}_{time}/
    
    Args:
        base_dir: Base directory containing log files (default: ~/petal-app-manager-dev)
        logger: Logger instance to use for logging (optional)
    """
    # check if base_dir is ending with "petal-app-manager"
    if base_dir is None:
        base_dir = Path.home() / "petal-app-manager-dev" / "petal-app-manager"
    elif base_dir.name != "petal-app-manager":
        base_dir = base_dir / "petal-app-manager"
    base_dir = base_dir / "logs"
    app_log_path = base_dir / "app.log"
    
    # Check if app.log exists and is larger than 1KB (1024 bytes)
    if not app_log_path.exists():
        if logger:
            logger.debug(f"No app.log found at {app_log_path}, skipping rotation")
        return
    
    file_size = app_log_path.stat().st_size
    if file_size <= 1024:  # 1KB threshold
        if logger:
            logger.debug(f"app.log size ({file_size} bytes) is under 1KB threshold, no rotation needed")
        return
    
    # Create timestamp for archive directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = base_dir / "logs" / f"log_{timestamp}"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all .log files in base directory (not recursive)
    log_files = list(base_dir.glob("*.log"))
    
    if not log_files:
        if logger:
            logger.debug("No log files found to rotate")
        return
    
    if logger:
        logger.info(f"Rotating {len(log_files)} log files to {archive_dir} (app.log size: {file_size} bytes)")
    
    # Move each log file to the archive directory
    moved_count = 0
    for log_file in log_files:
        try:
            destination = archive_dir / log_file.name
            shutil.move(str(log_file), str(destination))
            if logger:
                logger.debug(f"Moved {log_file.name} to {destination}")
            moved_count += 1
        except Exception as e:
            if logger:
                logger.error(f"Failed to move {log_file}: {e}")
    
    if logger:
        logger.info(f"Log rotation completed: {moved_count}/{len(log_files)} files moved to {archive_dir}")


if __name__ == "__main__":
    """
    Standalone execution mode for manual log rotation.
    
    Usage:
        python log_rotator.py
        python log_rotator.py /path/to/custom/directory
    """
    import sys
    
    # Set up basic logging for standalone mode
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("log_rotator")
    
    base_dir = Path.home() / "petal-app-manager-dev"
    
    # Allow custom directory as command line argument
    if len(sys.argv) > 1:
        base_dir = Path(sys.argv[1])
    
    logger.info(f"Checking logs in: {base_dir}")
    rotate_logs_if_needed(base_dir, logger)
