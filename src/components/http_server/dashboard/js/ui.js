function switchTab(tabId) {
    document.querySelectorAll('.tab-button, .tab-pane').forEach(el => el.classList.remove('active'));

    const activeButton = document.querySelector(`.tab-button[data-tab-id="${tabId}"]`);
    activeButton?.classList.add('active');

    const activePane = document.getElementById(tabId);
    activePane?.classList.add('active');

    document.getElementById('delete-file-btn').classList.toggle('show', tabId !== 'code-tab');
    state.activeTab = tabId;

    setTimeout(() => {
        const editor = tabId === 'code-tab' ? state.codeEditors.main : state.codeEditors[tabId];
        refreshEditor(editor);
    }, 50);
}

function toggleAddFilePopover() {
    document.getElementById('add-file-popover').classList.toggle('active');
}
