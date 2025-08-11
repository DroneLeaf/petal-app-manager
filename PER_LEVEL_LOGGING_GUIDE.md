# Per-Level Logging Output Control

This feature allows you to configure where each log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) should be output: terminal only, file only, or both.

## Configuration Method

### JSON Configuration File

Configure per-level logging by editing the `config.json` file in the project root:

```json
{
    "allowed_origins": [...],
    "logging": {
        "level_outputs": {
            "DEBUG": ["file"],
            "INFO": ["terminal", "file"],
            "WARNING": ["terminal", "file"], 
            "ERROR": ["terminal", "file"],
            "CRITICAL": ["terminal", "file"]
        }
    }
}
```

### Programmatic Configuration

You can also pass the configuration directly to `setup_logging()`:

```python
from petal_app_manager.logger import setup_logging

level_outputs = {
    "DEBUG": ["file"],
    "INFO": ["terminal", "file"], 
    "WARNING": ["terminal"],
    "ERROR": ["terminal", "file"],
    "CRITICAL": ["file"]
}

logger = setup_logging(
    log_level="DEBUG",
    app_prefixes=("myapp_",),
    log_to_file=True,
    level_outputs=level_outputs
)
```

## Output Options

For each log level, you can specify a list containing:

- **`["terminal"]`**: Log messages appear only in the terminal/console
- **`["file"]`**: Log messages appear only in log files  
- **`["terminal", "file"]`**: Log messages appear in both terminal and files

## Legacy Format Support

The system maintains backward compatibility with the old string format in the JSON configuration:

- **`"terminal"`**: Converted to `["terminal"]`
- **`"file"`**: Converted to `["file"]`
- **`"both"`**: Converted to `["terminal", "file"]`

## Common Configuration Scenarios

### Development Mode
- DEBUG, INFO: terminal only (avoid cluttering log files)
- WARNING, ERROR, CRITICAL: both (important messages everywhere)

```json
{
    "logging": {
        "level_outputs": {
            "DEBUG": ["terminal"],
            "INFO": ["terminal"],
            "WARNING": ["terminal", "file"],
            "ERROR": ["terminal", "file"],
            "CRITICAL": ["terminal", "file"]
        }
    }
}
```

### Production Mode
- DEBUG, INFO: file only (detailed logs for later analysis)
- WARNING: terminal only (immediate alerts)
- ERROR, CRITICAL: both (urgent issues need immediate attention and logging)

```json
{
    "logging": {
        "level_outputs": {
            "DEBUG": ["file"],
            "INFO": ["file"],
            "WARNING": ["terminal"],
            "ERROR": ["terminal", "file"],
            "CRITICAL": ["terminal", "file"]
        }
    }
}
```

### Debug Mode
- All levels: both (maximum visibility during debugging)

```json
{
    "logging": {
        "level_outputs": {
            "DEBUG": ["terminal", "file"],
            "INFO": ["terminal", "file"],
            "WARNING": ["terminal", "file"],
            "ERROR": ["terminal", "file"],
            "CRITICAL": ["terminal", "file"]
        }
    }
}
```

### Silent Mode
- DEBUG, INFO, WARNING: file only (minimal terminal noise)
- ERROR, CRITICAL: terminal only (only show urgent issues)

```json
{
    "logging": {
        "level_outputs": {
            "DEBUG": ["file"],
            "INFO": ["file"],
            "WARNING": ["file"],
            "ERROR": ["terminal"],
            "CRITICAL": ["terminal"]
        }
    }
}
```

## Default Behavior

If no `level_outputs` configuration is provided:

- When `log_to_file=True`: All levels default to `["terminal", "file"]`
- When `log_to_file=False`: All levels default to `["terminal"]`

## Integration with Existing Configuration

This feature works seamlessly with existing logging configuration:

- `PETAL_LOG_LEVEL`: Controls the minimum log level (from environment variables)
- `PETAL_LOG_TO_FILE`: Enables file logging (from environment variables)
- Per-level output destinations: Configured in `config.json`

## File Output

When file output is enabled for any level:

- **Shared log file**: `app.log` - contains logs from all application components
- **Per-component log files**: `app-{component}.log` - contains logs from specific components

Both file types respect the per-level output configuration.

## Testing Your Configuration

Use the test script provided to verify your configuration:

```bash
# Test config.json parsing
python3 test_config_json.py

# View example configurations
python3 logging_examples.py
```

## Benefits

- **Reduced terminal noise**: Hide verbose logs in production
- **Comprehensive file logging**: Keep detailed logs for debugging
- **Immediate alerts**: Show critical issues in terminal
- **Flexible configuration**: Adapt to different environments
- **JSON-based**: Easy to edit and version control
- **Environment-driven**: Configure via environment variables or code
