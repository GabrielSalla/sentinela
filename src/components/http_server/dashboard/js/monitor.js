async function loadMonitors() {
    const apiUrl = window.location.origin;

    try {
        const response = await fetch(`${apiUrl}/monitor/list`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const monitorsArray = await response.json();
        state.monitors = {};
        monitorsArray.forEach(monitor => {
            state.monitors[monitor.name] = monitor;
        });
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

    Object.values(state.monitors).forEach(monitor => {
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

    const existsOnServer = state.monitors[monitorName] && state.monitors[monitorName].id !== undefined;

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
    state.currentMonitor = { enabled: true, code: MONITOR_TEMPLATE, additional_files: {} };
    state.additionalFiles = {};

    showMonitorUI();

    document.getElementById('monitor-enabled').checked = true;

    if (state.codeEditors.main) {
        state.codeEditors.main.setValue(state.currentMonitor.code);
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

async function createNewMonitor() {
    const monitorName = document.getElementById('new-monitor-name-input').value.trim();
    if (!monitorName) {
        showToast('Monitor name is required', 'error');
        return;
    }

    try {
        const formatResponse = await fetch(`${window.location.origin}/monitor/format_name/${encodeURIComponent(monitorName)}`, {
            method: 'POST'
        });

        if (!formatResponse.ok) {
            throw new Error(`HTTP ${formatResponse.status}: ${formatResponse.statusText}`);
        }

        const formatResult = await formatResponse.json();
        const formattedName = formatResult.formatted_name;

        const existingMonitor = state.monitors[formattedName];

        if (existingMonitor) {
            showToast(`Monitor with formatted name "${formattedName}" already exists. Loading existing monitor.`, 'info');

            document.getElementById('monitor-select').value = formattedName;
            document.getElementById('new-monitor-name-input').value = '';

            await loadExistingMonitor(formattedName);
            return;
        }

        state.monitors[formattedName] = { name: formattedName, enabled: true };
        updateMonitorSelect();

        document.getElementById('monitor-select').value = formattedName;
        document.getElementById('new-monitor-name-input').value = '';

        setNewMonitor();

        if (formattedName !== monitorName) {
            showToast(`Monitor name formatted from "${monitorName}" to "${formattedName}"`, 'info');
        }

    } catch (error) {
        console.error('Error creating monitor:', error);
        showToast(`Error creating monitor: ${error.message}`, 'error');
    }
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
