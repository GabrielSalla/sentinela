async function loadMonitors() {
    const apiUrl = window.location.origin;

    try {
        const response = await fetch(`${apiUrl}/monitor/list`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        state.monitors = await response.json();
        updateMonitorSelect();

        toggleVisibility('monitor-section', true);

    } catch (error) {
        console.error('Connection error:', error);
        showToast(`Connection failed: ${error.message}`, 'error');
    }
}

function updateMonitorSelect() {
    const select = document.getElementById('monitor-select');
    select.innerHTML = '';

    const placeholderOption = document.createElement('option');
    placeholderOption.value = '';
    placeholderOption.textContent = 'Choose a monitor';
    placeholderOption.disabled = true;
    placeholderOption.hidden = true;
    select.appendChild(placeholderOption);

    const createOption = document.createElement('option');
    createOption.value = '___CREATE_NEW___';
    createOption.textContent = 'Create new monitor';
    createOption.style.fontStyle = 'italic';
    createOption.style.color = '#58a6ff';
    select.appendChild(createOption);

    state.monitors.forEach(monitor => {
        const option = document.createElement('option');
        option.value = monitor.name;
        option.textContent = monitor.name;
        select.appendChild(option);
    });

    select.value = '';
}

async function loadMonitorInfo() {
    const monitorName = document.getElementById('monitor-select').value;

    hideValidationErrors();

    if (!monitorName) {
        toggleVisibility('monitor-controls', false);
        toggleVisibility('monitor-form', false);
        toggleVisibility('new-monitor-section', false);
        return;
    }

    if (monitorName === '___CREATE_NEW___') {
        toggleVisibility('monitor-controls', false);
        toggleVisibility('monitor-form', false);
        toggleVisibility('new-monitor-section', true);
        document.getElementById('new-monitor-name-input').focus();
        return;
    }

    toggleVisibility('new-monitor-section', false);

    switchTab('code-tab');

    const existsOnServer = state.monitors.some(m => m.id !== undefined && m.name === monitorName);

    if (existsOnServer) {
        await loadExistingMonitor(monitorName);
    } else {
        setNewMonitor();
    }
}

async function loadExistingMonitor(monitorName) {
    try {
        const response = await fetch(`${window.location.origin}/monitor/${monitorName}`);
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

function setNewMonitor() {
    state.currentMonitor = { enabled: true, code: '', additional_files: {} };
    state.additionalFiles = {};

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

    state.additionalFiles = monitorInfo.additional_files || {};

    updateAdditionalFileTabs();

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

    state.monitors.push({ name: monitorName, enabled: true });
    updateMonitorSelect();

    document.getElementById('monitor-select').value = monitorName;

    document.getElementById('new-monitor-name-input').value = '';

    setNewMonitor();
}

function cancelNewMonitor() {
    document.getElementById('monitor-select').value = '';
    document.getElementById('new-monitor-name-input').value = '';
    toggleVisibility('new-monitor-section', false);
    loadMonitorInfo();
}

async function validateMonitor() {
    const code = document.getElementById('monitor-code').value;

    if (!code.trim()) {
        showValidationErrors('Monitor code is required');
        return;
    }

    hideValidationErrors();

    try {
        const response = await fetch(`${window.location.origin}/monitor/validate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ monitor_code: code })
        });

        const result = await response.json();

        if (response.ok) {
            showToast('Monitor validated successfully!');
        } else {
            showValidationErrors(result);
        }
    } catch (error) {
        console.error('Validation error:', error);
        showValidationErrors(`Network error: ${error.message}`);
    }
}

async function saveMonitor() {
    const monitorName = document.getElementById('monitor-select').value;
    const code = document.getElementById('monitor-code').value;
    const enabled = document.getElementById('monitor-enabled').checked;

    if (!monitorName || !code.trim()) {
        showValidationErrors('Monitor name and code are required');
        return;
    }

    hideValidationErrors();

    try {
        const response = await fetch(`${window.location.origin}/monitor/register/${monitorName}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                monitor_code: code,
                additional_files: state.additionalFiles
            })
        });

        const result = await response.json();

        if (response.ok) {
            showToast('Monitor saved successfully!');

            if (enabled) {
                await fetch(`${window.location.origin}/monitor/${monitorName}/enable`, { method: 'POST' })
                    .catch(error => console.error('Error enabling monitor:', error));
            }
            else {
                await fetch(`${window.location.origin}/monitor/${monitorName}/disable`, { method: 'POST' })
                    .catch(error => console.error('Error disabling monitor:', error));
            }
        } else {
            showValidationErrors(result);
        }
    } catch (error) {
        console.error('Save error:', error);
        showValidationErrors(`Network error: ${error.message}`);
    }
}
