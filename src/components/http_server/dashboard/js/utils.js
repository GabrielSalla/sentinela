function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    setTimeout(() => toast.classList.remove('show'), 5000);
}

function toggleVisibility(elementId, show) {
    document.getElementById(elementId).classList.toggle('hidden', !show);
}

function refreshEditor(editor) {
    if (editor) {
        requestAnimationFrame(() => editor.refresh());
    }
}

function clearSelection(selector) {
    document.querySelectorAll(selector).forEach(el => el.classList.remove('selected'));
}

function findBadgeByText(element, text) {
    return Array.from(element.querySelectorAll('.list-item-badge')).find(badge => badge.textContent === text);
}

function updateBadgeStatus(badge, isActive) {
    if (badge) {
        badge.classList.toggle('badge-status-inactive', !isActive);
        badge.classList.toggle('badge-status-active', isActive);
    }
}
