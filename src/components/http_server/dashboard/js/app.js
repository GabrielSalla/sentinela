// Event listeners
document.addEventListener('click', (e) => {
    if (!e.target.closest('.popover') && !e.target.closest('.add-file-btn') && !e.target.closest('.add-file-popover')) {
        document.querySelectorAll('.popover').forEach(p => p.classList.remove('active'));
        document.getElementById('add-file-popover').classList.remove('active');
    }
});

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    // Load previously saved server URL from localStorage
    const savedServerUrl = localStorage.getItem('sentinela-server-url');
    if (savedServerUrl) {
        document.getElementById('server-url').value = savedServerUrl;
    }

    initializeCodeEditor();
    connectToSentinela();

    // Add keyboard shortcuts
    document.getElementById('server-url').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') connectToSentinela();
    });

    document.getElementById('new-file-name').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') createAdditionalFile();
    });

    document.getElementById('new-monitor-name-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') createNewMonitor();
    });

    // Auto-reconnect on URL change
    let urlChangeTimeout;
    document.getElementById('server-url').addEventListener('input', () => {
        clearTimeout(urlChangeTimeout);
        urlChangeTimeout = setTimeout(connectToSentinela, 1000);
    });
});
