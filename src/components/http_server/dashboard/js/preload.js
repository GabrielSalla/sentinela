// Apply stored column widths before page render to prevent flicker
(function() {
    const columns = ['monitors', 'alerts', 'issues'];

    columns.forEach(name => {
        const width = localStorage.getItem(`column-width-${name}`);
        if (width) {
            const style = document.createElement('style');
            style.textContent = `#${name}-column { width: ${width}; flex: none; }`;
            document.head.appendChild(style);
        }
    })
})()
