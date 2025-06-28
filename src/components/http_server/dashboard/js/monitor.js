// Monitor functions
async function loadMonitorInfo() {
    const monitorName = document.getElementById('monitor-select').value;

    // Clear validation errors when switching monitors
    hideValidationErrors();

    // Handle empty selection (placeholder)
    if (!monitorName) {
        toggleVisibility('monitor-controls', false);
        toggleVisibility('monitor-form', false);
        toggleVisibility('new-monitor-section', false);
        return;
    }

    // Handle "Create new monitor" selection
    if (monitorName === '___CREATE_NEW___') {
        toggleVisibility('monitor-controls', false);
        toggleVisibility('monitor-form', false);
        toggleVisibility('new-monitor-section', true);
        document.getElementById('new-monitor-name-input').focus();
        return;
    }

    // Hide new monitor section
    toggleVisibility('new-monitor-section', false);

    // Always switch to code tab when loading a monitor
    switchTab('code-tab');

    const existsOnServer = state.monitors.some(m => m.id !== undefined && m.name === monitorName);

    if (existsOnServer) {
        await loadExistingMonitor(monitorName);
    } else {
        loadNewMonitor();
    }
}

async function loadExistingMonitor(monitorName) {
    try {
        const response = await fetch(`${state.apiUrl}/monitor/${monitorName}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const monitorInfo = await response.json();
        state.currentMonitor = monitorInfo;

        showMonitorUI();
        populateMonitorData(monitorInfo);

    } catch (error) {
        console.error('Error loading monitor:', error);
        showToast('Error loading monitor: ' + error.message, 'error');
    }
}

function loadNewMonitor() {
    state.currentMonitor = { enabled: true, code: '', additional_files: {} };
    state.additionalFiles = [];
    
    showMonitorUI();
    
    document.getElementById('monitor-enabled').checked = true;
    
    if (state.codeEditors.main) {
        state.codeEditors.main.setValue('');
        refreshEditor(state.codeEditors.main);
    }
    
    updateAdditionalFileTabs();
}

function showMonitorUI() {
    toggleVisibility('monitor-controls', true);
    toggleVisibility('monitor-form', true);
    toggleVisibility('new-monitor-section', false);
}

function populateMonitorData(monitorInfo) {
    document.getElementById('monitor-enabled').checked = monitorInfo.enabled;
    
    // Handle additional files
    state.additionalFiles = Object.entries(monitorInfo.additional_files || {})
        .map(([fileName, content]) => ({ fileName, content }));

    updateAdditionalFileTabs();

    // Update main code editor
    if (state.codeEditors.main) {
        state.codeEditors.main.setValue(monitorInfo.code);
        refreshEditor(state.codeEditors.main);
    }
}

function createNewMonitor() {
    const monitorName = document.getElementById('new-monitor-name-input').value.trim();
    if (!monitorName) {
        showToast('Monitor name is required', 'error');
        return;
    }

    if (state.monitors.some(m => m.name === monitorName)) {
        showToast('Monitor name already exists', 'error');
        return;
    }

    // Add to monitors list
    state.monitors.push({ name: monitorName, enabled: true });
    updateMonitorSelect();

    // Select the new monitor and load it
    document.getElementById('monitor-select').value = monitorName;
    
    // Clear the input
    document.getElementById('new-monitor-name-input').value = '';
    
    // Load the new monitor
    loadNewMonitor();
}

function cancelNewMonitor() {
    // Reset to placeholder
    document.getElementById('monitor-select').value = '';
    document.getElementById('new-monitor-name-input').value = '';
    toggleVisibility('new-monitor-section', false);
    loadMonitorInfo();
}

async function validateMonitor() {
    const code = state.codeEditors.main?.getValue() || document.getElementById('monitor-code').value;

    if (!code.trim()) {
        showValidationErrors('Monitor code is required');
        return;
    }

    // Hide previous errors
    hideValidationErrors();

    try {
        const response = await fetch(`${state.apiUrl}/monitor/validate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ monitor_code: code })
        });

        const result = await response.json();

        if (response.ok) {
            showToast('Monitor validated successfully!');
        } else {
            // Show detailed validation errors
            if (result.error) {
                showValidationErrors(result.error);
            } else if (result.message) {
                showValidationErrors(result.message);
            } else {
                showValidationErrors('Validation failed');
            }
        }
    } catch (error) {
        console.error('Validation error:', error);
        showValidationErrors(`Network error: ${error.message}`);
    }
}

async function saveMonitor() {
    const monitorName = document.getElementById('monitor-select').value;
    const code = state.codeEditors.main?.getValue() || document.getElementById('monitor-code').value;
    const enabled = document.getElementById('monitor-enabled').checked;

    if (!monitorName || !code.trim()) {
        showValidationErrors('Monitor name and code are required');
        return;
    }

    // Hide validation errors when saving
    hideValidationErrors();

    try {
        const additionalFiles = {};
        state.additionalFiles.forEach(file => {
            additionalFiles[file.fileName] = file.content;
        });

        const response = await fetch(`${state.apiUrl}/monitor/register/${monitorName}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                monitor_code: code,
                additional_files: additionalFiles
            })
        });

        const result = await response.json();

        if (response.ok) {
            showToast('Monitor saved successfully!');
            
            // Handle enabled state
            if (!enabled) {
                await fetch(`${state.apiUrl}/monitor/${monitorName}/disable`, { method: 'POST' })
                    .catch(error => console.error('Error disabling monitor:', error));
            }
        } else {
            // Show detailed save errors in the error panel
            if (result.error) {
                showValidationErrors(result.error);
            } else if (result.message) {
                showValidationErrors(result.message);
            } else {
                showValidationErrors('Save failed');
            }
        }
    } catch (error) {
        console.error('Save error:', error);
        showValidationErrors(`Network error: ${error.message}`);
    }
}
