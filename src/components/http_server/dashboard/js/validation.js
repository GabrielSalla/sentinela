function hideValidationErrors() {
    document.getElementById('validation-errors').classList.remove('show');
}

function showValidationErrors(result) {
    const errorsContainer = document.getElementById('validation-errors');
    const errorsContent = document.getElementById('validation-errors-content');

    let html = '';

    if (result.message) {
        html += `<div class="error-message">${result.message.replace(/\n/g, '<br>')}</div>`;
    }

    if (result.error) {
        html += '<div class="error-details">';

        if (typeof result.error === 'string') {
            html += result.error.replace(/\n/g, '<br>');
        } else if (Array.isArray(result.error)) {
            result.error.forEach((error) => {
                let parts = [];
                if (error.loc && error.loc.length > 0)
                    parts.push(`Location: ${error.loc.join('.')}`);
                if (error.type)
                    parts.push(`Type: ${error.type}`);
                if (error.msg)
                    parts.push(`Message: ${error.msg}`);
                html += `<div class="error-item">${parts.join(' | ')}</div>`;
            });
        }

        html += '</div>';
    }

    errorsContent.innerHTML = html;
    errorsContainer.classList.add('show');
}
