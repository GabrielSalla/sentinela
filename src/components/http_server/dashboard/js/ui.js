// UI helper functions
function switchTab(tabId) {
    // Update UI state
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));

    // Activate selected tab
    const activeButton = Array.from(document.querySelectorAll('.tab-button'))
        .find(btn => btn.onclick?.toString().includes(`switchTab('${tabId}')`));
    
    if (activeButton) activeButton.classList.add('active');

    const activePane = document.getElementById(tabId);
    if (activePane) activePane.classList.add('active');

    // Update delete button visibility
    document.getElementById('delete-file-btn').classList.toggle('show', tabId !== 'code-tab');

    state.activeTab = tabId;

    // Refresh active editor
    setTimeout(() => {
        if (tabId === 'code-tab') {
            refreshEditor(state.codeEditors.main);
        } else {
            const fileIndex = tabId.split('-')[2];
            refreshEditor(state.codeEditors[`file-${fileIndex}`]);
        }
    }, 50);
}

function toggleAddFilePopover() {
    document.getElementById('add-file-popover').classList.toggle('active');
}

function toggleCustomPopover(popoverId) {
    const popover = document.querySelector(`#${popoverId}`).parentElement;
    
    // Close other popovers
    document.querySelectorAll('.popover').forEach(p => {
        if (p !== popover) p.classList.remove('active');
    });
    
    popover.classList.toggle('active');
}
