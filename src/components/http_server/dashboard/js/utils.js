// Utility functions
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function toggleVisibility(elementId, show) {
    document.getElementById(elementId).classList.toggle('hidden', !show);
}

function refreshEditor(editor) {
    if (!editor) return;
    
    // Use requestAnimationFrame for better performance
    requestAnimationFrame(() => {
        editor.refresh();
    });
}
