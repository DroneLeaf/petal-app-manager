from pathlib import Path
import logging, sys

def setup_logging(
    *,
    log_level: str = "INFO",
    base_dir: Path | str = ".",
    app_prefixes: tuple[str, ...] = (),
    log_format: str = "%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    log_to_file: bool = False
):
    """
    Configure logging so that *only* loggers whose names start with one of
    `app_prefixes` are allowed through.  Everything else is muted.

    Parameters
    ----------
    app_prefixes : tuple[str, ...]
        Accept-list of logger-name prefixes.  Add more if you need to.
    """
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ 1️⃣
    #   A tiny filter that keeps only records from the approved prefixes
    # ------------------------------------------------------------------
    class _PrefixFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if record.name == "root":
                return True
            name_lower = record.name.lower()
            return any(name_lower.startswith(prefix) for prefix in app_prefixes)

    filt = _PrefixFilter()
    fmt  = logging.Formatter(log_format)

    # ------------------------------------------------------------------ 2️⃣
    #   Root logger → console + shared app.log, both with the filter
    # ------------------------------------------------------------------
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level))

    for h in root.handlers[:]:
        root.removeHandler(h)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.addFilter(filt)
    root.addHandler(console)

    shared = logging.FileHandler(base_dir / "app.log")
    shared.setFormatter(fmt)
    shared.addFilter(filt)
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
            
            if log_to_file:
                file_path = base_dir / f"app-{name_lower}.log"
                fh = logging.FileHandler(file_path)
                fh.setFormatter(fmt)
                fh.addFilter(filt)                     # keep same filter
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
        if log_to_file:
            file_path = base_dir / f"app-{name.lower()}.log"
            fh = logging.FileHandler(file_path)
            fh.setFormatter(fmt)
            fh.addFilter(filt)
            fh._per_logger = True
            logger.addHandler(fh)
    
    # Return the root logger just in case
    return root