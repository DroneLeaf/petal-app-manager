# Admin UI Guide

## Accessi3. **Control Proxies**
   - Enable/disable individual proxies
   - View proxy dependencies
   - See proxy status

4. **Control Petals**
   - Enable/disable individual petals
   - View petal dependencies
   - See petal status

5. **List All Components**
   - View all available proxies and petals (enabled and disabled)
   - See comprehensive dependency information
   - View component status

6. **Quick Actions**
The admin UI is available at the dedicated endpoint `/admin/` and does not interfere with the FastAPI documentation at `/docs`.

### URLs:
- **Admin UI Dashboard**: http://localhost:9000/admin/
- **FastAPI Docs**: http://localhost:9000/docs (unchanged)
- **OpenAPI JSON**: http://localhost:9000/openapi.json (unchanged)

## Admin UI Features

The admin UI provides a web-based interface to:

1. **View System Status**
   - Current enabled/disabled proxies and petals
   - Configuration overview
   - Quick status refresh and component listing

2. **Real-time Log Streaming** 🆕
   - Live log streaming using Server-Sent Events (SSE)
   - Log level filtering (DEBUG, INFO, WARNING, ERROR, CRITICAL)
   - Auto-scroll and connection status indicators
   - Recent logs loading functionality
   - Clear logs functionality
   - 1000+ log entry capacity with automatic rotation

3. **Control Proxies**
   - Enable/disable individual proxies
   - View proxy dependencies
   - See proxy status

3. **Control Petals**
   - Enable/disable individual petals
   - View petal dependencies
   - See petal status

4. **List All Components**
   - View all available proxies and petals (enabled and disabled)
   - See comprehensive dependency information
   - View component status

5. **Quick Actions**
   - Preset configurations for common setups
   - Minimal, Full, and MAVLink setup options

## API Endpoints Used by Admin UI

The admin UI uses the following API endpoints (all under `/api/petal-proxies-control/`):

- `GET /status` - Get system status
- `POST /proxies/control` - Enable/disable proxies
- `POST /petals/control` - Enable/disable petals
- `GET /components/list` - List all components
- `GET /logs/recent` - Get recent log entries 🆕
- `GET /logs/stream` - Real-time log streaming (SSE) 🆕

## Technical Implementation

- **Served at**: `/admin/` (dedicated endpoint)
- **Non-intrusive**: Does not interfere with FastAPI docs or other endpoints
- **Technology**: HTML/CSS/JavaScript dashboard
- **API Integration**: Uses fetch() to communicate with backend APIs
- **Real-time**: Provides real-time status updates and control

## Usage Example

1. Start the server: `python -m src.petal_app_manager.main`
2. Open browser to: http://localhost:8000/admin/
3. Use the dashboard to manage proxies and petals
4. FastAPI docs remain available at: http://localhost:8000/docs

The admin UI provides a user-friendly alternative to using the raw API endpoints directly.

**Note**: Configuration changes take effect immediately without requiring a server restart. The petal app manager dynamically loads and manages proxies and petals based on the current configuration.

## Real-time Log Streaming 🆕

The admin UI now includes a powerful real-time log streaming feature that provides live visibility into the petal app manager's operations.

### Features:
- **Live Streaming**: Uses Server-Sent Events (SSE) for real-time log delivery
- **Log Level Filtering**: Filter logs by DEBUG, INFO, WARNING, ERROR, or CRITICAL levels
- **Auto-scroll**: Automatically scrolls to show newest log entries
- **Connection Status**: Visual indicator showing stream connection status
- **Recent Logs**: Load recent historical logs without needing to connect to the stream
- **Clear Functionality**: Clear the log display for better readability
- **High Capacity**: Stores up to 1000 log entries with automatic rotation

### How to Use:
1. Open the admin dashboard at `/admin/`
2. Scroll down to the "Real-time Application Logs" section
3. Click "Load Recent" to see recent logs immediately
4. Click "Connect" to start live log streaming
5. Use the level filter dropdown to focus on specific log types
6. Click "Clear" to clean the log display
7. Click "Disconnect" to stop the stream

### What You'll See:
- **Proxy connections and disconnections**
- **Petal loading and unloading events**
- **API requests and responses**
- **Configuration changes**
- **Error conditions and warnings**
- **System startup and shutdown events**

This feature is perfect for monitoring the system in real-time, debugging issues, and understanding the application's behavior during operation.
