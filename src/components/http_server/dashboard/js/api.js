// Connection functions
async function connectToSentinela() {
    const serverUrl = document.getElementById('server-url').value || 'localhost:8000';
    
    state.apiUrl = serverUrl.startsWith('http') ? serverUrl : `http://${serverUrl}`;

    // Save the server URL to localStorage for future use
    localStorage.setItem('sentinela-server-url', serverUrl);

    try {
        const response = await fetch(`${state.apiUrl}/monitor/list`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        state.monitors = await response.json();
        updateMonitorSelect();
        showToast('Connected successfully!');
        
        toggleVisibility('monitor-section', true);
        toggleVisibility('welcome-message', false);

    } catch (error) {
        console.error('Connection error:', error);
        showToast(`Connection failed: ${error.message}`, 'error');
    }
}

function updateMonitorSelect() {
    const select = document.getElementById('monitor-select');
    select.innerHTML = '';
    
    // Add placeholder option that is disabled and hidden from dropdown
    const placeholderOption = document.createElement('option');
    placeholderOption.value = '';
    placeholderOption.textContent = 'Choose a monitor';
    placeholderOption.disabled = true;
    placeholderOption.hidden = true;
    select.appendChild(placeholderOption);
    
    // Add "Create new monitor" option as the first visible item
    const createOption = document.createElement('option');
    createOption.value = '___CREATE_NEW___';
    createOption.textContent = '+ Create new monitor...';
    createOption.style.fontStyle = 'italic';
    createOption.style.color = '#58a6ff';
    select.appendChild(createOption);

    state.monitors.forEach(monitor => {
        const option = document.createElement('option');
        option.value = monitor.name;
        option.textContent = monitor.name;
        select.appendChild(option);
    });

    // Set to placeholder by default
    select.value = '';
}
