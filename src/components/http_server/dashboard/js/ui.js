function switchTab(tabId) {
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));

    const activeButton = Array.from(document.querySelectorAll('.tab-button'))
        .find(btn => btn.onclick?.toString().includes(`switchTab('${tabId}')`));

    if (activeButton)
        activeButton.classList.add('active');

    const activePane = document.getElementById(tabId);
    if (activePane)
        activePane.classList.add('active');

    document.getElementById('delete-file-btn').classList.toggle('show', tabId !== 'code-tab');

    state.activeTab = tabId;

    setTimeout(() => {
        if (tabId === 'code-tab') {
            refreshEditor(state.codeEditors.main);
        } else {
            refreshEditor(state.codeEditors[tabId]);
        }
    }, 50);
}

function toggleAddFilePopover() {
    document.getElementById('add-file-popover').classList.toggle('active');
}

function toggleCustomPopover(popoverId) {
    const popover = document.querySelector(`#${popoverId}`).parentElement;

    document.querySelectorAll('.popover').forEach(p => {
        if (p !== popover) p.classList.remove('active');
    });

    popover.classList.toggle('active');
}
