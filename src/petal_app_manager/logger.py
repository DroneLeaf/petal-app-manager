from pathlib import Path
import logging, sys

from typing import Tuple, Dict, Union

# Import streaming functionality
from .utils.log_streamer import log_streamer, StreamingLogHandler

def setup_logging(
    *,
    log_level: str = "INFO",
    base_dir: Union[Path, str] = ".",
    app_prefixes: Tuple[str, ...] = (),
    log_format: str = "%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    log_to_file: bool = False,
    level_outputs: Dict[str, str] = None
):
    """
    Configure logging so that *only* loggers whose names start with one of
    `app_prefixes` are allowed through.  Everything else is muted.

    Parameters
    ----------
    app_prefixes : tuple[str, ...]
        Accept-list of logger-name prefixes.  Add more if you need to.
    level_outputs : dict[str, list[str] | str], optional
        Dictionary mapping log levels to output destinations.
        Values can be:
        - ["terminal"]: terminal only
        - ["file"]: file only  
        - ["terminal", "file"]: both terminal and file
        - "both": terminal + file (legacy format, still supported)
        - "terminal": terminal only (legacy format, still supported)
        - "file": file only (legacy format, still supported)
        Example: {"INFO": ["terminal", "file"], "WARNING": ["terminal"], "ERROR": ["file"]}
        If None, defaults to ["terminal", "file"] for all levels when log_to_file=True,
        or ["terminal"] for all levels when log_to_file=False.
    """
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    # Set default level outputs if not provided
    if level_outputs is None:
        default_output = ["terminal", "file"] if log_to_file else ["terminal"]
        level_outputs = {
            "DEBUG": default_output,
            "INFO": default_output,
            "WARNING": default_output,
            "ERROR": default_output,
            "CRITICAL": default_output
        }
    
    # Normalize level_outputs to handle both old string format and new list format
    normalized_level_outputs = {}
    for level, output in level_outputs.items():
        if isinstance(output, str):
            # Convert legacy string format to list format
            if output == "both":
                normalized_level_outputs[level] = ["terminal", "file"]
            elif output == "terminal":
                normalized_level_outputs[level] = ["terminal"]
            elif output == "file":
                normalized_level_outputs[level] = ["file"]
            else:
                normalized_level_outputs[level] = ["terminal"]  # fallback
        elif isinstance(output, list):
            # Validate list format
            valid_outputs = ["terminal", "file"]
            filtered_output = [o for o in output if o in valid_outputs]
            normalized_level_outputs[level] = filtered_output if filtered_output else ["terminal"]
        else:
            normalized_level_outputs[level] = ["terminal"]  # fallback
    
    level_outputs = normalized_level_outputs

    # ------------------------------------------------------------------ 1️⃣
    #   Filters for controlling where each log level goes
    # ------------------------------------------------------------------
    class _PrefixFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if record.name == "root":
                return True
            name_lower = record.name.lower()
            return any(name_lower.startswith(prefix) for prefix in app_prefixes)

    class _LevelOutputFilter(logging.Filter):
        def __init__(self, target: str, level_outputs: dict):
            super().__init__()
            self.target = target  # "terminal" or "file"
            self.level_outputs = level_outputs
            
        def filter(self, record: logging.LogRecord) -> bool:
            level_name = record.levelname
            output_setting = self.level_outputs.get(level_name, ["terminal"])
            
            if self.target == "terminal":
                return "terminal" in output_setting
            elif self.target == "file":
                return "file" in output_setting
            return True

    filt = _PrefixFilter()
    terminal_filter = _LevelOutputFilter("terminal", level_outputs)
    file_filter = _LevelOutputFilter("file", level_outputs)
    fmt  = logging.Formatter(log_format)

    # ------------------------------------------------------------------ 2️⃣
    #   Root logger → console + shared app.log, both with appropriate filters
    # ------------------------------------------------------------------
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level))

    for h in root.handlers[:]:
        root.removeHandler(h)

    # Console handler with terminal filter
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.addFilter(filt)
    console.addFilter(terminal_filter)
    root.addHandler(console)

    # Streaming handler for real-time log display (always enabled)
    streaming = StreamingLogHandler(log_streamer)
    streaming.setFormatter(fmt)
    streaming.addFilter(filt)  # Apply prefix filter to streaming as well
    root.addHandler(streaming)

    # File handler with file filter (only if any level should go to file)
    if any("file" in output for output in level_outputs.values()):
        shared = logging.FileHandler(base_dir / "app.log")
        shared.setFormatter(fmt)
        shared.addFilter(filt)
        shared.addFilter(file_filter)
        root.addHandler(shared)

    # ------------------------------------------------------------------ 3️⃣
    #   Custom logger class that attaches an extra file handler *only*
    #   if the logger name begins with an approved prefix
    # ------------------------------------------------------------------
    class _PerLogger(logging.Logger):
        def __init__(self, name: str, level: int = logging.NOTSET):
            super().__init__(name, level)
            
            # Check if name starts with any of the prefixes
            name_lower = name.lower()
            matches_prefix = name == "root" or any(name_lower.startswith(prefix) for prefix in app_prefixes)
            
            if not matches_prefix:
                return                              # not one of ours → skip
            if any(getattr(h, "_per_logger", False) for h in self.handlers):
                return                              # already added
            
            if log_to_file and any("file" in output for output in level_outputs.values()):
                file_path = base_dir / f"app-{name_lower}.log"
                fh = logging.FileHandler(file_path)
                fh.setFormatter(fmt)
                fh.addFilter(filt)
                fh.addFilter(file_filter)
                fh._per_logger = True
                self.addHandler(fh)

    # Must be called *before* any new loggers are created
    logging.setLoggerClass(_PerLogger)
    
    # ------------------------------------------------------------------ 4️⃣
    #   Apply file handlers to existing loggers that match our prefixes
    # ------------------------------------------------------------------
    for name, logger in logging.Logger.manager.loggerDict.items():
        # Skip non-logger objects and loggers that don't match our prefixes
        if not isinstance(logger, logging.Logger):
            continue
            
        if not name.lower().startswith(app_prefixes) and name != "root":
            continue
            
        # Skip if this logger already has our special handler
        if any(getattr(h, "_per_logger", False) for h in logger.handlers):
            continue
            
        # Add our file handler to this logger
        if log_to_file and any("file" in output for output in level_outputs.values()):
            file_path = base_dir / f"app-{name.lower()}.log"
            fh = logging.FileHandler(file_path)
            fh.setFormatter(fmt)
            fh.addFilter(filt)
            fh.addFilter(file_filter)
            fh._per_logger = True
            logger.addHandler(fh)
    
    # Return the root logger just in case
    return root