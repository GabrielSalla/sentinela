function hideValidationErrors() {
    document.getElementById('validation-errors').classList.remove('show');
}

function showValidationErrors(errors) {
    const errorsContainer = document.getElementById('validation-errors');
    const errorsContent = document.getElementById('validation-errors-content');
    
    errorsContent.innerHTML = '';
    
    if (typeof errors === 'string') {
        // Simple string error
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = errors;
        errorsContent.appendChild(errorDiv);
    } else if (Array.isArray(errors)) {
        // Array of validation errors
        errors.forEach(error => {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            
            let errorText = error.msg || error.message || 'Unknown error';
            if (error.loc && error.loc.length > 0) {
                errorText = `${error.loc.join('.')}: ${errorText}`;
            }
            if (error.type) {
                errorText = `[${error.type}] ${errorText}`;
            }
            
            errorDiv.textContent = errorText;
            errorsContent.appendChild(errorDiv);
        });
    } else if (typeof errors === 'object' && errors !== null) {
        // Object with error details
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = errors.message || errors.error || JSON.stringify(errors);
        errorsContent.appendChild(errorDiv);
        
        if (errors.details || errors.traceback) {
            const detailsDiv = document.createElement('div');
            detailsDiv.className = 'error-details';
            detailsDiv.textContent = errors.details || errors.traceback;
            errorsContent.appendChild(detailsDiv);
        }
    }
    
    errorsContainer.classList.add('show');
}
