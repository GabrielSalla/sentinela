function showSection(sectionName, event) {
    document.querySelectorAll('.section-content').forEach(section => {
        section.style.display = 'none';
    });
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.getElementById(`${sectionName}-section`).style.display = 'block';
    if (event) {
        event.target.classList.add('active');
    }
    if (sectionName === 'overview') {
        loadOverview();
    } else {
        stopAutoRefresh();
    }
}

document.addEventListener('click', (e) => {
    const isPopoverClick = e.target.closest('.popover, .add-file-btn, .add-file-popover');
    if (!isPopoverClick) {
        document.querySelectorAll('.popover, #add-file-popover').forEach(p => p.classList.remove('active'));
    }
});

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('overview-section').style.display = 'block';
    loadOverview();
    initializeCodeEditor();
    loadMonitors();

    const addEnterKey = (id, fn) => {
        document.getElementById(id).addEventListener('keypress', (e) => {
            if (e.key === 'Enter') fn();
        });
    };

    addEnterKey('new-file-name', createAdditionalFile);
    addEnterKey('new-monitor-name-input', createNewMonitor);
});
