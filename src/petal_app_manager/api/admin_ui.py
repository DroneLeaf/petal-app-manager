from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from typing import Optional
import logging

router = APIRouter(prefix="/admin", tags=["Admin UI"])

_logger: Optional[logging.Logger] = None

def _set_logger(logger: logging.Logger):
    """Set the logger for admin UI endpoints."""
    global _logger
    _logger = logger

def get_logger() -> logging.Logger:
    """Get the logger instance."""
    global _logger
    if not _logger:
        _logger = logging.getLogger("AdminUI")
    return _logger

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard():
    """Simple admin dashboard for controlling petals and proxies"""
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Petal App Manager - Admin Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { 
                font-family: Arial, sans-serif; 
                margin: 40px; 
                background-color: #f5f5f5;
            }
            .container { 
                max-width: 1200px; 
                margin: 0 auto; 
                background: white; 
                padding: 30px; 
                border-radius: 8px; 
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .section { 
                margin: 30px 0; 
                padding: 20px; 
                border: 1px solid #ddd; 
                border-radius: 5px;
                background-color: #fafafa;
            }
            button { 
                padding: 10px 20px; 
                margin: 5px; 
                border: none; 
                border-radius: 4px; 
                cursor: pointer; 
                font-size: 14px;
            }
            .btn-primary { background-color: #007bff; color: white; }
            .btn-success { background-color: #28a745; color: white; }
            .btn-danger { background-color: #dc3545; color: white; }
            .btn-warning { background-color: #ffc107; color: black; }
            .btn-secondary { background-color: #6c757d; color: white; }
            button:hover { opacity: 0.8; }
            .status { 
                padding: 15px; 
                margin: 10px 0; 
                border-radius: 4px; 
                font-family: monospace;
                white-space: pre-wrap;
            }
            .success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .info { background-color: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
            h2 { color: #666; margin-top: 0; }
            .checkbox-group { margin: 10px 0; }
            .checkbox-group label { margin-right: 15px; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌸 Petal App Manager - Admin Dashboard</h1>
            
            <div class="section">
                <h2>📊 Current Status</h2>
                <button class="btn-primary" onclick="loadStatus()">🔄 Refresh Status</button>
                <div id="status" class="status info">Click "Refresh Status" to load current configuration...</div>
            </div>

            <div class="grid">
                <div class="section">
                    <h2>🌸 Petal Control</h2>
                    <div class="checkbox-group">
                        <label><input type="checkbox" id="petal_warehouse"> petal_warehouse</label><br>
                        <label><input type="checkbox" id="flight_records"> flight_records</label><br>
                        <label><input type="checkbox" id="mission_planner"> mission_planner</label><br>
                    </div>
                    <button class="btn-success" onclick="updatePetals('ON')">✅ Enable Selected</button>
                    <button class="btn-danger" onclick="updatePetals('OFF')">❌ Disable Selected</button>
                </div>

                <div class="section">
                    <h2>🔌 Proxy Control</h2>
                    <div class="checkbox-group">
                        <label><input type="checkbox" id="redis"> redis</label><br>
                        <label><input type="checkbox" id="ext_mavlink"> ext_mavlink</label><br>
                        <label><input type="checkbox" id="ftp_mavlink"> ftp_mavlink</label><br>
                        <label><input type="checkbox" id="db"> db</label><br>
                        <label><input type="checkbox" id="cloud"> cloud</label><br>
                        <label><input type="checkbox" id="bucket"> bucket</label><br>
                    </div>
                    <button class="btn-success" onclick="updateProxies('ON')">✅ Enable Selected</button>
                    <button class="btn-danger" onclick="updateProxies('OFF')">❌ Disable Selected</button>
                </div>
            </div>

            <div class="section">
                <h2>🔄 Server Control</h2>
                <button class="btn-warning" onclick="checkRestartStatus()">🔍 Check Restart Status</button>
                <button class="btn-secondary" onclick="restartServer()">🔄 Restart Server</button>
                <div id="restart-status" class="status info">Use "Check Restart Status" to see if restart is needed...</div>
            </div>

            <div class="section">
                <h2>📚 Quick Actions</h2>
                <button class="btn-primary" onclick="presetMinimal()">🔧 Minimal Setup (Redis only)</button>
                <button class="btn-primary" onclick="presetFull()">🚀 Full Setup (All features)</button>
                <button class="btn-primary" onclick="presetMavlink()">✈️ MAVLink Setup</button>
            </div>
        </div>

        <script>
            async function apiCall(method, endpoint, data = null) {
                try {
                    const options = {
                        method: method,
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    };
                    
                    if (data) {
                        options.body = JSON.stringify(data);
                    }
                    
                    const response = await fetch(endpoint, options);
                    const result = await response.json();
                    
                    return { success: response.ok, data: result };
                } catch (error) {
                    return { success: false, data: { detail: error.message } };
                }
            }

            async function loadStatus() {
                const statusDiv = document.getElementById('status');
                statusDiv.className = 'status info';
                statusDiv.textContent = 'Loading...';
                
                const result = await apiCall('GET', '/api/config/status');
                
                if (result.success) {
                    statusDiv.className = 'status success';
                    statusDiv.textContent = JSON.stringify(result.data, null, 2);
                    
                    // Update checkboxes based on current status
                    result.data.enabled_petals.forEach(petal => {
                        const checkbox = document.getElementById(petal);
                        if (checkbox) checkbox.checked = true;
                    });
                    
                    result.data.enabled_proxies.forEach(proxy => {
                        const checkbox = document.getElementById(proxy);
                        if (checkbox) checkbox.checked = true;
                    });
                } else {
                    statusDiv.className = 'status error';
                    statusDiv.textContent = 'Error: ' + JSON.stringify(result.data, null, 2);
                }
            }

            async function updatePetals(action) {
                const checkboxes = ['petal_warehouse', 'flight_records', 'mission_planner'];
                const selected = checkboxes.filter(id => document.getElementById(id).checked);
                
                if (selected.length === 0) {
                    alert('Please select at least one petal');
                    return;
                }
                
                const result = await apiCall('POST', '/api/config/petals/control', {
                    petals: selected,
                    action: action
                });
                
                showResult(result, 'status');
                if (result.success) loadStatus();
            }

            async function updateProxies(action) {
                const checkboxes = ['redis', 'ext_mavlink', 'ftp_mavlink', 'db', 'cloud', 'bucket'];
                const selected = checkboxes.filter(id => document.getElementById(id).checked);
                
                if (selected.length === 0) {
                    alert('Please select at least one proxy');
                    return;
                }
                
                const result = await apiCall('POST', '/api/config/proxies/control', {
                    petals: selected,  // API uses 'petals' field for proxy names too
                    action: action
                });
                
                showResult(result, 'status');
                if (result.success) loadStatus();
            }

            async function checkRestartStatus() {
                const result = await apiCall('GET', '/api/config/restart-status');
                showResult(result, 'restart-status');
            }

            async function restartServer() {
                if (!confirm('Are you sure you want to restart the server? This will briefly interrupt service.')) {
                    return;
                }
                
                const result = await apiCall('POST', '/api/config/restart');
                showResult(result, 'restart-status');
                
                if (result.success) {
                    setTimeout(() => {
                        document.getElementById('restart-status').textContent = 
                            'Server restarted. Refreshing page...';
                        setTimeout(() => location.reload(), 2000);
                    }, 1000);
                }
            }

            function showResult(result, divId) {
                const div = document.getElementById(divId);
                if (result.success) {
                    div.className = 'status success';
                    div.textContent = JSON.stringify(result.data, null, 2);
                } else {
                    div.className = 'status error';
                    div.textContent = 'Error: ' + JSON.stringify(result.data, null, 2);
                }
            }

            // Preset configurations
            async function presetMinimal() {
                // Disable all proxies except redis and db
                const disableProxies = ['ext_mavlink', 'ftp_mavlink', 'cloud', 'bucket'];
                await apiCall('POST', '/api/config/proxies/control', {
                    petals: disableProxies,
                    action: 'OFF'
                });
                
                // Disable all petals
                const disablePetals = ['petal_warehouse', 'flight_records', 'mission_planner'];
                await apiCall('POST', '/api/config/petals/control', {
                    petals: disablePetals,
                    action: 'OFF'
                });
                
                loadStatus();
            }

            async function presetFull() {
                // Enable all proxies
                const allProxies = ['redis', 'ext_mavlink', 'ftp_mavlink', 'db', 'cloud', 'bucket'];
                await apiCall('POST', '/api/config/proxies/control', {
                    petals: allProxies,
                    action: 'ON'
                });
                
                // Enable all petals
                const allPetals = ['petal_warehouse', 'flight_records', 'mission_planner'];
                await apiCall('POST', '/api/config/petals/control', {
                    petals: allPetals,
                    action: 'ON'
                });
                
                loadStatus();
            }

            async function presetMavlink() {
                // Enable MAVLink related proxies
                const mavlinkProxies = ['redis', 'db', 'ext_mavlink', 'ftp_mavlink'];
                await apiCall('POST', '/api/config/proxies/control', {
                    petals: mavlinkProxies,
                    action: 'ON'
                });
                
                // Enable MAVLink related petals
                const mavlinkPetals = ['petal_warehouse', 'mission_planner'];
                await apiCall('POST', '/api/config/petals/control', {
                    petals: mavlinkPetals,
                    action: 'ON'
                });
                
                loadStatus();
            }

            // Load status on page load
            loadStatus();
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)
