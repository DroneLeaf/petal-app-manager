# Petal and Proxy Configuration API

The petal-app-manager now supports dynamic control of proxies and petals through REST API endpoints. This allows you to enable/disable components without restarting the application.

## API Endpoints

### 1. Get Configuration Status
```bash
GET /api/petal-proxies-control/status
```

Returns the current configuration including enabled proxies, petals, and their dependencies.

**Response:**
```json
{
  "enabled_proxies": ["redis", "ext_mavlink", "db", "cloud"],
  "enabled_petals": ["petal_warehouse", "mission_planner"],
  "petal_dependencies": {
    "petal_warehouse": ["redis", "ext_mavlink"],
    "flight_records": ["redis", "cloud"],
    "mission_planner": ["redis", "ext_mavlink"]
  },
  "proxy_dependencies": {
    "db": ["cloud"],
    "bucket": ["cloud"]
  },
  "restart_required": true
}
```

### 2. List All Components
```bash
GET /api/petal-proxies-control/components/list
```

Returns a comprehensive list of all available petals and proxies, regardless of their enabled/disabled state. This includes their dependencies, dependents, and current status.

**Response:**
```json
{
  "petals": [
    {
      "name": "flight_records",
      "enabled": false,
      "dependencies": ["redis", "cloud"]
    },
    {
      "name": "petal_warehouse", 
      "enabled": true,
      "dependencies": ["redis", "ext_mavlink"]
    },
    {
      "name": "mission_planner",
      "enabled": true,
      "dependencies": ["redis", "ext_mavlink"]
    }
  ],
  "proxies": [
    {
      "name": "bucket",
      "enabled": false,
      "dependencies": ["cloud"],
      "dependents": []
    },
    {
      "name": "cloud",
      "enabled": true,
      "dependencies": [],
      "dependents": ["petal:flight_records", "proxy:bucket", "proxy:db"]
    },
    {
      "name": "redis",
      "enabled": true,
      "dependencies": [],
      "dependents": ["petal:flight_records", "petal:petal_warehouse", "petal:mission_planner"]
    }
  ],
  "total_petals": 3,
  "total_proxies": 6
}
```

**Use this endpoint to:**
- See all available components in the system
- Check dependency relationships
- Understand what would be affected by enabling/disabling a component
- Get a complete overview before making configuration changes

### 3. Control Petals (Enable/Disable)
```bash
POST /api/petal-proxies-control/petals/control
```

**Request Body:**
```json
{
  "petals": ["petal_name1", "petal_name2"],
  "action": "ON" | "OFF"
}
```

**Examples:**

Enable a single petal:
```bash
curl -X POST "http://localhost:8000/api/petal-proxies-control/petals/control" \
     -H "Content-Type: application/json" \
     -d '{
       "petals": ["flight_records"],
       "action": "ON"
     }'
```

Disable multiple petals:
```bash
curl -X POST "http://localhost:8000/api/petal-proxies-control/petals/control" \
     -H "Content-Type: application/json" \
     -d '{
       "petals": ["petal_warehouse", "mission_planner"],
       "action": "OFF"
     }'
```

### 4. Control Proxies (Enable/Disable)
```bash
POST /api/petal-proxies-control/proxies/control
```

**Request Body:**
```json
{
  "petals": ["proxy_name1", "proxy_name2"],
  "action": "ON" | "OFF"
}
```

**Examples:**

Enable multiple proxies:
```bash
curl -X POST "http://localhost:8000/api/petal-proxies-control/proxies/control" \
     -H "Content-Type: application/json" \
     -d '{
       "petals": ["redis", "cloud", "ext_mavlink"],
       "action": "ON"
     }'
```

Disable a proxy:
```bash
curl -X POST "http://localhost:8000/api/petal-proxies-control/proxies/control" \
     -H "Content-Type: application/json" \
     -d '{
       "petals": ["cloud"],
       "action": "OFF"
     }'
```

### 5. Server Restart Control
```bash
POST /api/petal-proxies-control/restart
GET /api/petal-proxies-control/restart-status
```

**Check if restart is needed:**
```bash
curl -X GET "http://localhost:8000/api/petal-proxies-control/restart-status"
```

**Response:**
```json
{
  "restart_required": true,
  "reason": "Configuration changes require server restart to take effect",
  "file_config": {
    "enabled_proxies": ["redis", "ext_mavlink", "db"],
    "enabled_petals": ["petal_warehouse"]
  },
  "note": "Use POST /api/petal-proxies-control/restart to restart the server"
}
```

**Restart the server:**
```bash
curl -X POST "http://localhost:8000/api/petal-proxies-control/restart"
```

**Response:**
```json
{
  "success": true,
  "message": "Server restart triggered. Please wait a moment for the server to reload.",
  "note": "If running with --reload, the server will automatically restart."
}
```

## Response Format

All control endpoints return responses in this format:

```json
{
  "success": true,
  "action": "ON",
  "processed_petals": ["petal_warehouse", "mission_planner"],
  "results": [
    "Enabled petal: petal_warehouse",
    "Enabled petal: mission_planner"
  ],
  "restart_required": true,
  "message": "Configuration updated. 2 petals oned successfully.",
  "errors": [],  // Present only if there were errors
  "partial_success": false  // Present only if some operations failed
}
```

## Dependency Management

The API automatically validates dependencies:

### For Petals:
- **Enabling**: Won't enable a petal if its required proxies are disabled
- **Error Example**: `"Cannot enable flight_records: missing dependencies ['cloud']. Enable those proxies first."`

### For Proxies:
- **Disabling**: Won't disable a proxy if enabled petals depend on it  
- **Error Example**: `"Cannot disable ext_mavlink: required by petals ['mission_planner', 'petal_warehouse']. Disable those petals first."`

## Configuration File

Changes are automatically saved to `proxies.yaml`:

```yaml
enabled_petals:
  - mission_planner
  - petal_warehouse
  - flight_records
enabled_proxies:
  - redis
  - ext_mavlink
  - db
  - cloud
petal_dependencies:
  flight_records:
    - redis
    - cloud
  mission_planner:
    - redis
    - ext_mavlink
  petal_warehouse:
    - redis
    - ext_mavlink
```

## Use Cases

### 1. Minimal Setup (Redis Only)
```bash
# Disable all unnecessary proxies for lightweight operation
curl -X POST "http://localhost:8000/api/petal-proxies-control/proxies/control" \
     -H "Content-Type: application/json" \
     -d '{"petals": ["cloud", "ext_mavlink"], "action": "OFF"}'

# Disable petals that require disabled proxies
curl -X POST "http://localhost:8000/api/petal-proxies-control/petals/control" \
     -H "Content-Type: application/json" \
     -d '{"petals": ["flight_records", "petal_warehouse", "mission_planner"], "action": "OFF"}'
```

### 2. Full MAVLink Setup
```bash
# Enable MAVLink functionality
curl -X POST "http://localhost:8000/api/petal-proxies-control/proxies/control" \
     -H "Content-Type: application/json" \
     -d '{"petals": ["ext_mavlink"], "action": "ON"}'

# Enable MAVLink-dependent petals
curl -X POST "http://localhost:8000/api/petal-proxies-control/petals/control" \
     -H "Content-Type: application/json" \
     -d '{"petals": ["petal_warehouse", "mission_planner"], "action": "ON"}'
```

### 3. Cloud Integration
```bash
# Enable cloud functionality
curl -X POST "http://localhost:8000/api/petal-proxies-control/proxies/control" \
     -H "Content-Type: application/json" \
     -d '{"petals": ["cloud"], "action": "ON"}'

# Enable cloud-dependent petals
curl -X POST "http://localhost:8000/api/petal-proxies-control/petals/control" \
     -H "Content-Type: application/json" \
     -d '{"petals": ["flight_records"], "action": "ON"}'
```

## Proxy Dependencies

The system now supports proxy dependencies, where some proxies depend on others to function properly. This prevents configuration errors and ensures system stability.

### Current Proxy Dependencies
- **`db`** depends on **`cloud`**
- **`bucket`** depends on **`cloud`**

### Dependency Rules
1. **Cannot disable a proxy** if other proxies depend on it
2. **Cannot enable a proxy** without first enabling its dependencies
3. **Dependency validation** happens for both petals and proxies

### Example: Trying to disable cloud proxy
```bash
curl -X POST "http://localhost:8000/api/petal-proxies-control/proxies/control" \
     -H "Content-Type: application/json" \
     -d '{"petals": ["cloud"], "action": "OFF"}'
```

**Response (Error):**
```json
{
  "success": false,
  "action": "OFF",
  "processed_proxies": ["cloud"],
  "results": [],
  "errors": [
    "Cannot disable cloud: required by proxies ['db', 'bucket']. Disable those first."
  ],
  "restart_required": true,
  "message": "Configuration updated. 0 proxies offed successfully."
}
```

### Correct Order: Disable dependent proxies first
```bash
# 1. First disable dependent proxies
curl -X POST "http://localhost:8000/api/petal-proxies-control/proxies/control" \
     -H "Content-Type: application/json" \
     -d '{"petals": ["db", "bucket"], "action": "OFF"}'

# 2. Then disable cloud proxy
curl -X POST "http://localhost:8000/api/petal-proxies-control/proxies/control" \
     -H "Content-Type: application/json" \
     -d '{"petals": ["cloud"], "action": "OFF"}'
```

## Notes

- **Restart Required**: Changes to the configuration require an application restart to take effect on the actual proxy/petal loading
- **Dependency Validation**: The API prevents invalid configurations that would break functionality
  - **Petal Dependencies**: Petals cannot be enabled without their required proxies
  - **Proxy Dependencies**: Proxies cannot be enabled without their required proxies, and cannot be disabled if other proxies depend on them
- **Batch Operations**: You can enable/disable multiple petals or proxies in a single request
- **Error Handling**: Partial failures are supported - some operations may succeed while others fail with clear error messages

## Interactive Testing

Visit `http://localhost:8000/docs` to access the interactive API documentation and test the endpoints directly in your browser.
