function hideValidationErrors() {
    document.getElementById('validation-errors').classList.remove('show');
}

function showValidationErrors(result) {
    const errorsContainer = document.getElementById('validation-errors');
    const errorsContent = document.getElementById('validation-errors-content');

    errorsContent.innerHTML = '';

    // Show the main message first (if present)
    if (result.message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'error-message';
        messageDiv.innerHTML = result.message.replace(/\n/g, '<br>');
        errorsContent.appendChild(messageDiv);
    }

    // Show detailed error information (if present)
    if (result.error) {
        const detailsDiv = document.createElement('div');
        detailsDiv.className = 'error-details';

        if (typeof result.error === 'string') {
            detailsDiv.innerHTML = result.error.replace(/\n/g, '<br>');
        } else if (Array.isArray(result.error)) {
            result.error.forEach((error) => {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error-item';

                let parts = [];
                if (error.loc && error.loc.length > 0) {
                    parts.push(`Location: ${error.loc.join('.')}`);
                }
                if (error.type) {
                    parts.push(`Type: ${error.type}`);
                }
                if (error.msg) {
                    parts.push(`Message: ${error.msg}`);
                }

                errorDiv.textContent = parts.join(' | ');
                detailsDiv.appendChild(errorDiv);
            });
        }

        errorsContent.appendChild(detailsDiv);
    }

    errorsContainer.classList.add('show');

    switchTab('code-tab');
}
