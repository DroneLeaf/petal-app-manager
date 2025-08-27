from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from typing import Optional
import logging

router = APIRouter(prefix="/admin", tags=["Admin UI"])

_logger: Optional[logging.Logger] = None

def _set_logger(logger: logging.Logger):
    global _logger
    _logger = logger

def get_logger() -> logging.Logger:
    global _logger
    if not _logger:
        _logger = logging.getLogger("AdminUI")
    return _logger

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard():
    """Admin dashboard with real-time log streaming"""
    
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>Petal App Manager - Admin Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {
            --ion-color-primary: #3880ff;
            --ion-color-primary-rgb: 56, 128, 255;
            --ion-color-primary-contrast: #ffffff;
            --ion-color-primary-contrast-rgb: 255, 255, 255;
            --ion-color-primary-shade: #3171e0;
            --ion-color-primary-tint: #4c8dff;

            --ion-color-secondary: #3dc2ff;
            --ion-color-secondary-rgb: 61, 194, 255;
            --ion-color-secondary-contrast: #ffffff;
            --ion-color-secondary-contrast-rgb: 255, 255, 255;
            --ion-color-secondary-shade: #36abe0;
            --ion-color-secondary-tint: #50c8ff;

            --ion-color-success: #2dd36f;
            --ion-color-success-rgb: 45, 211, 111;
            --ion-color-success-contrast: #ffffff;
            --ion-color-success-contrast-rgb: 255, 255, 255;
            --ion-color-success-shade: #28ba62;
            --ion-color-success-tint: #42d77d;

            --ion-color-warning: #ffc409;
            --ion-color-warning-rgb: 255, 196, 9;
            --ion-color-warning-contrast: #000000;
            --ion-color-warning-contrast-rgb: 0, 0, 0;
            --ion-color-warning-shade: #e0ac08;
            --ion-color-warning-tint: #ffca22;

            --ion-color-danger: #eb445a;
            --ion-color-danger-rgb: 235, 68, 90;
            --ion-color-danger-contrast: #ffffff;
            --ion-color-danger-contrast-rgb: 255, 255, 255;
            --ion-color-danger-shade: #cf3c4f;
            --ion-color-danger-tint: #ed576b;

            --ion-color-medium: #92949c;
            --ion-color-medium-rgb: 146, 148, 156;
            --ion-color-medium-contrast: #ffffff;
            --ion-color-medium-contrast-rgb: 255, 255, 255;
            --ion-color-medium-shade: #808289;
            --ion-color-medium-tint: #9d9fa6;

            --ion-color-light: #f4f5f8;
            --ion-color-light-rgb: 244, 245, 248;
            --ion-color-light-contrast: #000000;
            --ion-color-light-contrast-rgb: 0, 0, 0;
            --ion-color-light-shade: #d7d8da;
            --ion-color-light-tint: #f5f6f9;

            --ion-color-dark: #222428;
            --ion-color-dark-rgb: 34, 36, 40;
            --ion-color-dark-contrast: #ffffff;
            --ion-color-dark-contrast-rgb: 255, 255, 255;
            --ion-color-dark-shade: #1e2023;
            --ion-color-dark-tint: #383a3e;
        }

        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Open Sans', 'Helvetica Neue', sans-serif;
            margin: 0; 
            padding: 0;
            background-color: #f8f9fa;
            color: var(--ion-color-dark);
            line-height: 1.6;
        }

        .petals-proxies-page {
            padding: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        /* Header Section */
        .header-section {
            margin-bottom: 30px;
            text-align: center;
        }

        .header-section h1 {
            color: var(--ion-color-primary);
            margin-bottom: 10px;
            font-size: 28px;
            font-weight: 600;
        }

        .header-section p {
            color: var(--ion-color-medium);
            font-size: 16px;
            line-height: 1.6;
            margin: 0;
        }

        /* Section Headers */
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }

        .section-header h2 {
            color: var(--ion-color-primary);
            margin: 0;
            font-size: 20px;
            font-weight: 600;
        }

        .action-buttons {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        /* Buttons */
        button {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .btn-primary { 
            background-color: var(--ion-color-primary); 
            color: white; 
        }
        .btn-primary:hover { 
            background-color: var(--ion-color-primary-shade); 
            transform: translateY(-1px);
        }

        .btn-success { 
            background-color: var(--ion-color-success); 
            color: white; 
        }
        .btn-success:hover { 
            background-color: var(--ion-color-success-shade); 
            transform: translateY(-1px);
        }

        .btn-danger { 
            background-color: var(--ion-color-danger); 
            color: white; 
        }
        .btn-danger:hover { 
            background-color: var(--ion-color-danger-shade); 
            transform: translateY(-1px);
        }

        .btn-warning { 
            background-color: var(--ion-color-warning); 
            color: var(--ion-color-dark); 
        }
        .btn-warning:hover { 
            background-color: var(--ion-color-warning-shade); 
            transform: translateY(-1px);
        }

        .btn-secondary { 
            background-color: var(--ion-color-medium); 
            color: white; 
        }
        .btn-secondary:hover { 
            background-color: var(--ion-color-medium-shade); 
            transform: translateY(-1px);
        }

        /* Status Section */
        .status-section {
            margin-bottom: 30px;
        }

        .status {
            margin-top: 15px;
            padding: 15px;
            border-radius: 8px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 12px;
            white-space: pre-wrap;
            overflow-x: auto;
        }

        .success { 
            background-color: rgba(45, 211, 111, 0.1); 
            color: var(--ion-color-success-shade); 
            border: 1px solid var(--ion-color-success); 
        }
        .error { 
            background-color: rgba(235, 68, 90, 0.1); 
            color: var(--ion-color-danger-shade); 
            border: 1px solid var(--ion-color-danger); 
        }
        .info { 
            background-color: var(--ion-color-light); 
            color: var(--ion-color-dark); 
            border: 1px solid var(--ion-color-medium); 
        }

        /* Control Sections */
        .control-section {
            margin-bottom: 30px;
        }

        .controls-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }

        .control-card {
            background: white;
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            border: 1px solid #e0e0e0;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .control-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }

        .card-header h3 {
            color: var(--ion-color-primary);
            margin: 0;
            font-size: 16px;
            font-weight: 500;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 4px;
            font-size: 12px;
            font-weight: 500;
            padding: 4px 8px;
            border-radius: 16px;
        }

        .status-indicator.enabled {
            color: var(--ion-color-success);
            background: rgba(45, 211, 111, 0.1);
        }

        .status-indicator.disabled {
            color: var(--ion-color-danger);
            background: rgba(235, 68, 90, 0.1);
        }

        .card-content {
            margin-bottom: 12px;
        }

        .dependencies, .dependents {
            font-size: 12px;
            color: var(--ion-color-medium);
            margin-bottom: 4px;
        }

        .dependencies strong, .dependents strong {
            color: var(--ion-color-dark);
        }

        .card-actions {
            display: flex;
            justify-content: flex-end;
        }

        /* All Components Section */
        .all-components-section {
            margin-bottom: 30px;
            display: none;
        }

        .all-components-display {
            margin-top: 15px;
        }

        .components-overview {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        .component-column h3 {
            color: var(--ion-color-primary);
            font-size: 18px;
            margin-bottom: 10px;
        }

        .component-item {
            border: 1px solid #ddd;
            margin: 5px 0;
            padding: 8px;
            border-radius: 4px;
            background: white;
        }

        .component-item.enabled {
            background: rgba(45, 211, 111, 0.05);
            border-color: var(--ion-color-success);
        }

        .component-item.disabled {
            background: rgba(235, 68, 90, 0.05);
            border-color: var(--ion-color-danger);
        }

        .component-name {
            font-weight: bold;
            margin-bottom: 4px;
        }

        .component-details {
            font-size: 11px;
            color: var(--ion-color-medium);
        }

        /* Logs Section */
        .logs-section {
            margin-bottom: 30px;
        }

        .logs-controls {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }

        .connection-status {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        .status-dot.connected {
            background: var(--ion-color-success);
        }

        .status-dot.disconnected {
            background: var(--ion-color-danger);
        }

        .status-dot.connecting {
            background: var(--ion-color-warning);
            animation: pulse 1s infinite;
        }

        .status-text {
            font-size: 12px;
            color: var(--ion-color-medium);
        }

        .log-level-filter {
            padding: 6px 12px;
            border: 1px solid var(--ion-color-medium);
            border-radius: 6px;
            background: white;
            font-size: 12px;
            min-width: 120px;
        }

        .logs-container {
            height: 400px;
            overflow-y: auto;
            border: 1px solid var(--ion-color-medium);
            border-radius: 8px;
            background: #1a1a1a;
            color: #ffffff;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 11px;
            padding: 10px;
            margin-top: 15px;
        }

        .log-entry {
            margin-bottom: 2px;
            padding: 2px 0;
            word-wrap: break-word;
            border-bottom: 1px solid #333;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .log-timestamp {
            color: #888;
            min-width: 80px;
            font-size: 10px;
        }

        .log-level {
            font-weight: bold;
            padding: 1px 6px;
            border-radius: 3px;
            font-size: 9px;
            min-width: 50px;
            text-align: center;
        }

        .log-level.DEBUG { background: #666; color: white; }
        .log-level.INFO { background: var(--ion-color-primary); color: white; }
        .log-level.WARNING { background: var(--ion-color-warning); color: white; }
        .log-level.ERROR { background: var(--ion-color-danger); color: white; }
        .log-level.CRITICAL { background: #9C27B0; color: white; }

        .log-logger {
            color: var(--ion-color-success);
            font-weight: bold;
            min-width: 80px;
        }

        .log-message {
            color: #fff;
            flex: 1;
        }

        .log-message.welcome {
            color: #888;
            font-style: italic;
        }

        /* Resources Section */
        .resources-section {
            margin-bottom: 30px;
        }

        .resources-section h2 {
            color: var(--ion-color-primary);
            margin-bottom: 15px;
            font-size: 18px;
            font-weight: 600;
        }

        .resource-links {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .resource-links a {
            text-decoration: none;
            padding: 8px 16px;
            border: 1px solid var(--ion-color-primary);
            color: var(--ion-color-primary);
            border-radius: 6px;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .resource-links a:hover {
            background: var(--ion-color-primary);
            color: white;
            transform: translateY(-1px);
        }

        /* Icons */
        .icon {
            width: 16px;
            height: 16px;
            display: inline-block;
        }

        /* Animations */
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        /* Responsive Design */
        @media (max-width: 768px) {
            .petals-proxies-page {
                padding: 15px;
            }

            .section-header {
                flex-direction: column;
                align-items: flex-start;
            }

            .logs-controls {
                width: 100%;
                justify-content: space-between;
            }

            .controls-grid {
                grid-template-columns: 1fr !important;
            }

            .components-overview {
                grid-template-columns: 1fr;
            }

            .resource-links {
                flex-direction: column;
            }

            .resource-links a {
                width: 100%;
            }

            .logs-container {
                height: 300px;
                font-size: 10px;
            }

            .log-entry {
                flex-direction: column;
                gap: 2px;
            }

            .log-timestamp,
            .log-level,
            .log-logger {
                min-width: auto;
            }
        }

        @media (max-width: 480px) {
            .petals-proxies-page {
                padding: 10px;
            }

            .header-section h1 {
                font-size: 24px;
            }

            .section-header h2 {
                font-size: 18px;
            }

            .control-card {
                padding: 12px;
            }

            .card-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 8px;
            }
        }
    </style>
</head>
<body>
    <div class="petals-proxies-page">
        <!-- Header Section -->
        <section class="header-section">
            <h1>🌸 Petal App Manager - Admin Dashboard</h1>
            <p>Control and monitor your distributed inference systems and proxy configurations</p>
        </section>

        <!-- Quick Status Section -->
        <section class="status-section">
            <div class="section-header">
                <h2>📊 System Status</h2>
                <div class="action-buttons">
                    <button class="btn-primary" onclick="loadStatus()">
                        <span class="icon">🔄</span>
                        Refresh Status
                    </button>
                    <button class="btn-warning" onclick="showAllComponentsView()">
                        <span class="icon">📋</span>
                        All Components
                    </button>
                </div>
            </div>
            <div id="status" class="status info">Click "Refresh Status" to load current configuration...</div>
        </section>

        <!-- All Components Section -->
        <section class="all-components-section" id="all-components-section">
            <div class="section-header">
                <h2>📋 All Components Overview</h2>
                <div class="action-buttons">
                    <button class="btn-secondary" onclick="hideAllComponentsView()">
                        <span class="icon">❌</span>
                        Hide
                    </button>
                </div>
            </div>
            <div class="all-components-display">
                <p>Complete list of all proxies and petals in the system:</p>
                <div id="all-components-display"></div>
            </div>
        </section>
        <!-- Proxy Controls Section -->
        <section class="control-section">
            <div class="section-header">
                <h2>🔧 Proxy Controls</h2>
                <div class="action-buttons">
                    <button class="btn-primary" onclick="loadProxyControls()">
                        <span class="icon">🔄</span>
                        Refresh Proxies
                    </button>
                    <button class="btn-success" onclick="applyChanges()">
                        <span class="icon">✅</span>
                        Apply Changes
                    </button>
                </div>
            </div>
            <p>Enable or disable proxies dynamically:</p>
            <div id="proxy-controls" class="controls-grid">
                <div class="control-card">
                    <div class="card-content">
                        <p>Click "Refresh Proxies" to load available proxy configurations.</p>
                    </div>
                </div>
            </div>
        </section>

        <!-- Petal Controls Section -->
        <section class="control-section">
            <div class="section-header">
                <h2>🌸 Petal Controls</h2>
                <div class="action-buttons">
                    <button class="btn-primary" onclick="loadPetalControls()">
                        <span class="icon">🔄</span>
                        Refresh Petals
                    </button>
                    <button class="btn-success" onclick="applyChanges()">
                        <span class="icon">✅</span>
                        Apply Changes
                    </button>
                </div>
            </div>
            <p>Enable or disable petals dynamically:</p>
            <div id="petal-controls" class="controls-grid">
                <div class="control-card">
                    <div class="card-content">
                        <p>Click "Refresh Petals" to load available petal configurations.</p>
                    </div>
                </div>
            </div>
        </section>

        <!-- Real-time Logs Section -->
        <section class="logs-section">
            <div class="section-header">
                <h2>📋 Real-time Application Logs</h2>
                <div class="logs-controls">
                    <div class="connection-status">
                        <div class="status-dot disconnected" id="log-connection-status"></div>
                        <span class="status-text" id="log-status-text">Disconnected</span>
                    </div>
                    <select class="log-level-filter" id="log-level-filter" onchange="onLogLevelChange()">
                        <option value="ALL">All Levels</option>
                        <option value="DEBUG">Debug</option>
                        <option value="INFO">Info</option>
                        <option value="WARNING">Warning</option>
                        <option value="ERROR">Error</option>
                        <option value="CRITICAL">Critical</option>
                    </select>
                    <button class="btn-primary" onclick="toggleLogStream()" id="log-stream-btn">Connect</button>
                    <button class="btn-warning" onclick="clearLogs()">Clear</button>
                    <button class="btn-secondary" onclick="loadRecentLogs()">Load Recent</button>
                </div>
            </div>
            <div class="logs-container" id="logs-container">
                <div class="log-entry">
                    <span class="log-message welcome">
                        📡 Real-time log streaming ready. Click "Connect" to start or "Load Recent" to see historical logs.
                    </span>
                </div>
            </div>
        </section>
        <!-- Additional Resources -->
        <section class="resources-section">
            <h2>🔗 Additional Resources</h2>
            <div class="resource-links">
                <a href="/docs" target="_blank">
                    <span class="icon">📖</span>
                    API Documentation
                </a>
                <a href="/api/petal-proxies-control/status" target="_blank">
                    <span class="icon">🔍</span>
                    Raw Status API
                </a>
                <a href="/health/detailed" target="_blank">
                    <span class="icon">❤️</span>
                    Health Check
                </a>
            </div>
        </section>
    </div>

    <script>
        // Log streaming functionality
        let logEventSource = null;
        let isLogStreamConnected = false;
        let logLevelFilter = 'ALL';
        let maxLogEntries = 1000;
        
        function updateLogConnectionStatus(status) {
            const statusEl = document.getElementById('log-connection-status');
            const textEl = document.getElementById('log-status-text');
            const btnEl = document.getElementById('log-stream-btn');
            
            statusEl.className = `status-dot ${status}`;
            
            switch(status) {
                case 'connected':
                    textEl.textContent = 'Connected';
                    btnEl.textContent = 'Disconnect';
                    btnEl.className = 'btn-danger';
                    isLogStreamConnected = true;
                    break;
                case 'connecting':
                    textEl.textContent = 'Connecting...';
                    btnEl.textContent = 'Cancel';
                    btnEl.className = 'btn-warning';
                    break;
                case 'disconnected':
                    textEl.textContent = 'Disconnected';
                    btnEl.textContent = 'Connect';
                    btnEl.className = 'btn-primary';
                    isLogStreamConnected = false;
                    break;
            }
        }
        
        function addLogEntry(logData) {
            const container = document.getElementById('logs-container');
            
            // Check if we should filter this log level
            if (logLevelFilter !== 'ALL' && logData.level !== logLevelFilter) {
                return;
            }
            
            const logEntry = document.createElement('div');
            logEntry.className = 'log-entry';
            
            const timestamp = new Date(logData.timestamp).toLocaleTimeString();
            
            logEntry.innerHTML = `
                <span class="log-timestamp">${timestamp}</span>
                <span class="log-level ${logData.level}">${logData.level}</span>
                <span class="log-logger">${logData.logger}</span>
                <span class="log-message">${logData.message}</span>
            `;
            
            container.appendChild(logEntry);
            
            // Remove old entries if we have too many
            while (container.children.length > maxLogEntries) {
                container.removeChild(container.firstChild);
            }
            
            // Auto-scroll to bottom
            container.scrollTop = container.scrollHeight;
        }
        
        function toggleLogStream() {
            if (isLogStreamConnected || logEventSource) {
                disconnectLogStream();
            } else {
                connectLogStream();
            }
        }
        
        function connectLogStream() {
            updateLogConnectionStatus('connecting');
            
            logEventSource = new EventSource('/api/petal-proxies-control/logs/stream');
            
            logEventSource.onopen = function(event) {
                updateLogConnectionStatus('connected');
            };
            
            logEventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'log') {
                        addLogEntry(data);
                    } else if (data.type === 'connection') {
                        const container = document.getElementById('logs-container');
                        const welcomeEntry = document.createElement('div');
                        welcomeEntry.className = 'log-entry';
                        welcomeEntry.innerHTML = `<span class="log-message" style="color: #4CAF50;">🟢 ${data.message}</span>`;
                        container.appendChild(welcomeEntry);
                        container.scrollTop = container.scrollHeight;
                    }
                } catch (e) {
                    console.error('Error parsing log data:', e);
                }
            };
            
            logEventSource.onerror = function(event) {
                console.error('Log stream error:', event);
                updateLogConnectionStatus('disconnected');
                logEventSource = null;
            };
        }
        
        function disconnectLogStream() {
            if (logEventSource) {
                logEventSource.close();
                logEventSource = null;
            }
            updateLogConnectionStatus('disconnected');
        }
        
        async function loadRecentLogs() {
            try {
                const response = await fetch('/api/petal-proxies-control/logs/recent?count=50');
                const result = await response.json();
                
                if (response.ok && result.logs) {
                    clearLogs();
                    const welcomeEntry = document.createElement('div');
                    welcomeEntry.className = 'log-entry';
                    welcomeEntry.innerHTML = `<span class="log-message" style="color: #4CAF50;">📋 Loaded ${result.logs.length} recent log entries</span>`;
                    document.getElementById('logs-container').appendChild(welcomeEntry);
                    
                    result.logs.forEach(log => addLogEntry(log));
                } else {
                    showError('Failed to load recent logs: ' + (result.detail || 'Unknown error'));
                }
            } catch (error) {
                showError('Failed to load recent logs: ' + error.message);
            }
        }
        
        function clearLogs() {
            const container = document.getElementById('logs-container');
            container.innerHTML = '';
        }
        
        function showError(message) {
            const container = document.getElementById('logs-container');
            const errorEntry = document.createElement('div');
            errorEntry.className = 'log-entry';
            errorEntry.innerHTML = `<span class="log-message" style="color: #F44336;">❌ ${message}</span>`;
            container.appendChild(errorEntry);
            container.scrollTop = container.scrollHeight;
        }

        async function loadStatus() {
            try {
                const response = await fetch('/api/petal-proxies-control/status');
                const result = await response.json();
                
                const div = document.getElementById('status');
                if (response.ok) {
                    div.className = 'status success';
                    div.textContent = JSON.stringify(result, null, 2);
                } else {
                    div.className = 'status error';
                    div.textContent = 'Error: ' + JSON.stringify(result, null, 2);
                }
            } catch (error) {
                const div = document.getElementById('status');
                div.className = 'status error';
                div.textContent = 'Error: ' + error.message;
            }
        }

        async function loadComponents() {
            try {
                const response = await fetch('/api/petal-proxies-control/components/list');
                const result = await response.json();
                
                const div = document.getElementById('status');
                if (response.ok) {
                    div.className = 'status success';
                    div.textContent = JSON.stringify(result, null, 2);
                } else {
                    div.className = 'status error';
                    div.textContent = 'Error: ' + JSON.stringify(result, null, 2);
                }
            } catch (error) {
                const div = document.getElementById('status');
                div.className = 'status error';
                div.textContent = 'Error: ' + error.message;
            }
        }

        async function loadProxyControls() {
            try {
                const response = await fetch('/api/petal-proxies-control/components/list');
                const result = await response.json();
                
                const container = document.getElementById('proxy-controls');
                if (response.ok && result.proxies) {
                    let html = '';
                    
                    result.proxies.forEach(proxy => {
                        const isEnabled = proxy.enabled;
                        const statusClass = isEnabled ? 'enabled' : 'disabled';
                        const statusIcon = isEnabled ? '✅' : '❌';
                        const statusText = isEnabled ? 'Enabled' : 'Disabled';
                        const btnClass = isEnabled ? 'btn-danger' : 'btn-success';
                        const btnText = isEnabled ? 'Disable' : 'Enable';
                        
                        // Format dependencies and dependents
                        const deps = proxy.dependencies && proxy.dependencies.length > 0 ? 
                            proxy.dependencies.join(', ') : 'None';
                        const dependents = proxy.dependents && proxy.dependents.length > 0 ? 
                            proxy.dependents.join(', ') : 'None';
                        
                        html += `
                            <div class="control-card">
                                <div class="card-header">
                                    <h3>${proxy.name}</h3>
                                    <div class="status-indicator ${statusClass}">
                                        <span class="icon">${statusIcon}</span>
                                        ${statusText}
                                    </div>
                                </div>
                                <div class="card-content">
                                    <div class="dependencies">
                                        <strong>Dependencies:</strong> ${deps}
                                    </div>
                                    <div class="dependents">
                                        <strong>Used by:</strong> ${dependents}
                                    </div>
                                </div>
                                <div class="card-actions">
                                    <button class="${btnClass}" onclick="toggleProxy('${proxy.name}', ${!isEnabled})">${btnText}</button>
                                </div>
                            </div>
                        `;
                    });
                    
                    container.innerHTML = html;
                } else {
                    container.innerHTML = '<div class="status error">Failed to load proxies: ' + (result.detail || 'Unknown error') + '</div>';
                }
            } catch (error) {
                const container = document.getElementById('proxy-controls');
                container.innerHTML = '<div class="status error">Error loading proxies: ' + error.message + '</div>';
            }
        }

        async function loadPetalControls() {
            try {
                const response = await fetch('/api/petal-proxies-control/components/list');
                const result = await response.json();
                
                const container = document.getElementById('petal-controls');
                if (response.ok && result.petals) {
                    let html = '';
                    
                    // Remove duplicates from petals array
                    const uniquePetals = result.petals.reduce((acc, petal) => {
                        if (!acc.find(p => p.name === petal.name)) {
                            acc.push(petal);
                        }
                        return acc;
                    }, []);
                    
                    uniquePetals.forEach(petal => {
                        const isEnabled = petal.enabled;
                        const statusClass = isEnabled ? 'enabled' : 'disabled';
                        const statusIcon = isEnabled ? '✅' : '❌';
                        const statusText = isEnabled ? 'Enabled' : 'Disabled';
                        const btnClass = isEnabled ? 'btn-danger' : 'btn-success';
                        const btnText = isEnabled ? 'Disable' : 'Enable';
                        
                        // Format dependencies
                        const deps = petal.dependencies && petal.dependencies.length > 0 ? 
                            petal.dependencies.join(', ') : 'None';
                        
                        html += `
                            <div class="control-card">
                                <div class="card-header">
                                    <h3>${petal.name}</h3>
                                    <div class="status-indicator ${statusClass}">
                                        <span class="icon">${statusIcon}</span>
                                        ${statusText}
                                    </div>
                                </div>
                                <div class="card-content">
                                    <div class="dependencies">
                                        <strong>Dependencies:</strong> ${deps}
                                    </div>
                                </div>
                                <div class="card-actions">
                                    <button class="${btnClass}" onclick="togglePetal('${petal.name}', ${!isEnabled})">${btnText}</button>
                                </div>
                            </div>
                        `;
                    });
                    
                    container.innerHTML = html;
                } else {
                    container.innerHTML = '<div class="status error">Failed to load petals: ' + (result.detail || 'Unknown error') + '</div>';
                }
            } catch (error) {
                const container = document.getElementById('petal-controls');
                container.innerHTML = '<div class="status error">Error loading petals: ' + error.message + '</div>';
            }
        }

        async function toggleProxy(proxyName, enable) {
            try {
                const response = await fetch('/api/petal-proxies-control/proxies/control', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        petals: [proxyName],  // API reuses petals field for proxy names
                        action: enable ? 'ON' : 'OFF'
                    })
                });
                
                const result = await response.json();
                if (response.ok) {
                    showSuccess(`Proxy "${proxyName}" ${enable ? 'enabled' : 'disabled'} successfully`);
                    loadProxyControls(); // Reload to show updated state
                } else {
                    showError(`Failed to toggle proxy: ${result.detail || 'Unknown error'}`);
                }
            } catch (error) {
                showError(`Error toggling proxy: ${error.message}`);
            }
        }

        async function togglePetal(petalName, enable) {
            try {
                const response = await fetch('/api/petal-proxies-control/petals/control', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        petals: [petalName],
                        action: enable ? 'ON' : 'OFF'
                    })
                });
                
                const result = await response.json();
                if (response.ok) {
                    showSuccess(`Petal "${petalName}" ${enable ? 'enabled' : 'disabled'} successfully`);
                    loadPetalControls(); // Reload to show updated state
                } else {
                    showError(`Failed to toggle petal: ${result.detail || 'Unknown error'}`);
                }
            } catch (error) {
                showError(`Error toggling petal: ${error.message}`);
            }
        }

        function showSuccess(message) {
            const container = document.getElementById('logs-container');
            const successEntry = document.createElement('div');
            successEntry.className = 'log-entry';
            successEntry.innerHTML = `<span class="log-message" style="color: #4CAF50;">✅ ${message}</span>`;
            container.appendChild(successEntry);
            container.scrollTop = container.scrollHeight;
        }

        function showAllComponentsView() {
            const section = document.getElementById('all-components-section');
            const display = document.getElementById('all-components-display');
            
            // Show the section
            section.style.display = 'block';
            display.innerHTML = '<div style="text-align: center; padding: 20px;">Loading all components...</div>';
            
            // Load and display all components
            fetch('/api/petal-proxies-control/components/list')
                .then(response => response.json())
                .then(data => {
                    let html = '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">';
                    
                    // Proxies column
                    html += '<div><h3>🔧 All Proxies (' + data.total_proxies + ')</h3>';
                    html += '<div style="font-size: 12px; margin-bottom: 10px;">🟢 = Enabled | 🔴 = Disabled</div>';
                    
                    data.proxies.forEach(proxy => {
                        const status = proxy.enabled ? '🟢' : '🔴';
                        const deps = proxy.dependencies.length > 0 ? proxy.dependencies.join(', ') : 'None';
                        const dependents = proxy.dependents.length;
                        
                        html += `
                            <div style="border: 1px solid #ddd; margin: 5px 0; padding: 8px; border-radius: 4px; background: ${proxy.enabled ? '#f0f8f0' : '#f8f0f0'};">
                                <div style="font-weight: bold;">${status} ${proxy.name}</div>
                                <div style="font-size: 11px; color: #666;">
                                    Dependencies: ${deps}<br>
                                    Used by: ${dependents} components
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                    
                    // Petals column  
                    html += '<div><h3>🌸 All Petals (' + data.total_petals + ')</h3>';
                    html += '<div style="font-size: 12px; margin-bottom: 10px;">🟢 = Enabled | 🔴 = Disabled</div>';
                    
                    // Remove duplicates from petals
                    const uniquePetals = data.petals.reduce((acc, petal) => {
                        if (!acc.find(p => p.name === petal.name)) {
                            acc.push(petal);
                        }
                        return acc;
                    }, []);
                    
                    uniquePetals.forEach(petal => {
                        const status = petal.enabled ? '🟢' : '🔴';
                        const deps = petal.dependencies.length > 0 ? petal.dependencies.join(', ') : 'None';
                        
                        html += `
                            <div style="border: 1px solid #ddd; margin: 5px 0; padding: 8px; border-radius: 4px; background: ${petal.enabled ? '#f0f8f0' : '#f8f0f0'};">
                                <div style="font-weight: bold;">${status} ${petal.name}</div>
                                <div style="font-size: 11px; color: #666;">
                                    Dependencies: ${deps}
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                    
                    html += '</div>';
                    
                    // Add summary
                    html += `
                        <div style="margin-top: 15px; padding: 10px; background: #e8f4fd; border-radius: 4px; border-left: 4px solid #2196F3;">
                            <strong>📊 Summary:</strong> Found ${data.total_proxies} proxies and ${data.total_petals} petals in the system.<br>
                            <strong>🎯 This view shows ALL components regardless of enabled/disabled state.</strong>
                        </div>
                    `;
                    
                    display.innerHTML = html;
                })
                .catch(error => {
                    display.innerHTML = `<div class="status error">Error loading components: ${error.message}</div>`;
                });
        }

        // Set up log level filter
        document.getElementById('log-level-filter').addEventListener('change', function(e) {
            logLevelFilter = e.target.value;
        });
        
        // Additional utility functions
        function applyChanges() {
            showSuccess('Configuration changes will be applied automatically when you make changes.');
        }
        
        function hideAllComponentsView() {
            const section = document.getElementById('all-components-section');
            section.style.display = 'none';
        }
        
        function onLogLevelChange() {
            logLevelFilter = document.getElementById('log-level-filter').value;
            // Re-filter logs if needed
            loadRecentLogs();
        }
        
        // Initialize
        updateLogConnectionStatus('disconnected');
        loadRecentLogs(); // Auto-load recent logs on page load
        loadProxyControls(); // Auto-load proxy controls
        loadPetalControls(); // Auto-load petal controls
    </script>
</body>
</html>
""")
