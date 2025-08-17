document.addEventListener('click', (e) => {
    if (!e.target.closest('.popover') && !e.target.closest('.add-file-btn') && !e.target.closest('.add-file-popover')) {
        document.querySelectorAll('.popover').forEach(p => p.classList.remove('active'));
        document.getElementById('add-file-popover').classList.remove('active');
    }
});

document.addEventListener('DOMContentLoaded', () => {
    initializeCodeEditor();
    loadMonitors();

    // Add keyboard shortcuts
    document.getElementById('new-file-name').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') createAdditionalFile();
    });

    document.getElementById('new-monitor-name-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') createNewMonitor();
    });
});
