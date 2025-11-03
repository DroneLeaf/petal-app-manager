# Petal App Manager Documentation

This directory contains the Sphinx documentation for Petal App Manager.

## Building the Documentation

### Install Dependencies

```bash
# From the project root directory
pdm install -G dev
```

This will install all development dependencies including Sphinx and related documentation tools.

### Build HTML Documentation

```bash
# On Linux/macOS
make html

# On Windows
make.bat html
```

The built documentation will be in `_build/html/`. Open `_build/html/index.html` in your browser to view it.

### Auto-rebuild Documentation (Development Mode)

For active documentation development, use `sphinx-autobuild` to automatically rebuild and refresh your browser when files change:

```bash
# From the docs directory
sphinx-autobuild . _build/html

# Or with custom port
sphinx-autobuild . _build/html --port 8181
```

This will:
- Build the documentation
- Start a local web server (default: http://127.0.0.1:8000)
- Watch for file changes and automatically rebuild
- Auto-refresh your browser when changes are detected

> [!TIP]
> Keep `sphinx-autobuild` running in a separate terminal while editing documentation for instant preview of changes.

### Other Build Formats

```bash
make epub    # Build ePub
make latexpdf # Build PDF (requires LaTeX)
make clean   # Clean build directory
```

## Documentation Structure

```
docs/
├── index.rst                      # Main documentation index
├── introduction.rst               # What is Petal App Manager?
├── getting_started/
│   ├── index.rst                  # Getting Started section index
│   ├── dependencies.rst           # Dependencies installation
│   └── quickstart.rst             # Quick start guide
├── how_to_use/
│   ├── index.rst                  # How to Use section index
│   ├── making_requests.rst        # Making API requests
│   ├── adding_petals.rst          # Adding new petals
│   ├── service_management.rst     # Service management
│   └── configuration.rst          # .env configuration
├── changelog.rst                  # Version changelog
├── api_reference/
│   ├── index.rst                  # API Reference section index
│   ├── core_api.rst               # Core API modules
│   ├── proxies.rst                # Proxy modules
│   ├── plugins.rst                # Plugin system
│   └── petals.rst                 # Available petals
└── known_issues.rst               # Known issues and troubleshooting
```

## Contributing to Documentation

When adding new features or making changes, please update the relevant documentation files.

1. Edit the appropriate `.rst` file
2. Build the documentation locally to verify (or use `sphinx-autobuild` for live preview)
3. Commit both code and documentation changes together

### Quick Development Workflow

```bash
# Terminal 1: Start auto-rebuild server
cd docs
sphinx-autobuild . _build/html --port 8001

# Terminal 2: Edit .rst files
# Your browser at http://127.0.0.1:8001 will auto-refresh on save
```
