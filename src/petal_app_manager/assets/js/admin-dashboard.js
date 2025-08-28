// Petal App Manager - Admin Dashboard JavaScript

// Log streaming functionality
let logEventSource = null;
let isLogStreamConnected = false;
let logLevelFilter = 'ALL';
let maxLogEntries = 1000;

/**
 * Update log connection status indicator
 */
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

/**
 * Add a log entry to the logs container
 */
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

/**
 * Toggle log stream connection
 */
function toggleLogStream() {
    if (isLogStreamConnected || logEventSource) {
        disconnectLogStream();
    } else {
        connectLogStream();
    }
}

/**
 * Connect to log stream
 */
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

/**
 * Disconnect from log stream
 */
function disconnectLogStream() {
    if (logEventSource) {
        logEventSource.close();
        logEventSource = null;
    }
    updateLogConnectionStatus('disconnected');
}

/**
 * Load recent logs
 */
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

/**
 * Clear all logs
 */
function clearLogs() {
    const container = document.getElementById('logs-container');
    container.innerHTML = '';
}

/**
 * Show error message in logs
 */
function showError(message) {
    const container = document.getElementById('logs-container');
    const errorEntry = document.createElement('div');
    errorEntry.className = 'log-entry';
    errorEntry.innerHTML = `<span class="log-message" style="color: #F44336;">❌ ${message}</span>`;
    container.appendChild(errorEntry);
    container.scrollTop = container.scrollHeight;
}

/**
 * Show success message in logs
 */
function showSuccess(message) {
    const container = document.getElementById('logs-container');
    const successEntry = document.createElement('div');
    successEntry.className = 'log-entry';
    successEntry.innerHTML = `<span class="log-message" style="color: #4CAF50;">✅ ${message}</span>`;
    container.appendChild(successEntry);
    container.scrollTop = container.scrollHeight;
}

/**
 * Load system status
 */
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

/**
 * Load all components
 */
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

/**
 * Load proxy controls
 */
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

/**
 * Load petal controls
 */
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

/**
 * Toggle proxy state
 */
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

/**
 * Toggle petal state
 */
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

/**
 * Show all components view
 */
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

/**
 * Hide all components view
 */
function hideAllComponentsView() {
    const section = document.getElementById('all-components-section');
    section.style.display = 'none';
}

/**
 * Handle log level filter change
 */
function onLogLevelChange() {
    logLevelFilter = document.getElementById('log-level-filter').value;
    // Re-filter logs if needed
    loadRecentLogs();
}

/**
 * Apply changes placeholder
 */
function applyChanges() {
    showSuccess('Configuration changes will be applied automatically when you make changes.');
}

/**
 * Initialize the dashboard
 */
function initializeDashboard() {
    // Set up log level filter
    document.getElementById('log-level-filter').addEventListener('change', function(e) {
        logLevelFilter = e.target.value;
    });
    
    // Initialize connection status
    updateLogConnectionStatus('disconnected');
    
    // Auto-load content
    loadRecentLogs(); // Auto-load recent logs on page load
    loadProxyControls(); // Auto-load proxy controls
    loadPetalControls(); // Auto-load petal controls
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeDashboard);
