const codeEditorInstances = {};

const CODEMIRROR_CONFIG = {
    theme: 'material-darker',
    lineNumbers: true,
    indentUnit: 4,
    tabSize: 4,
    indentWithTabs: false,
    lineWrapping: true,
    autoCloseBrackets: true,
    matchBrackets: true,
};

function getLanguageFromFileName(fileName) {
    const extension = fileName.split('.').pop().toLowerCase();
    const languageMap = {
        'py': 'python',
        'json': { name: 'javascript', json: true },
        'yaml': 'yaml',
        'yml': 'yaml',
        'sql': 'sql',
        'md': 'markdown',
    };
    return languageMap[extension] || null;
}

function createCodeEditor(element, mode, value = '') {
    return CodeMirror.fromTextArea(element, {
        ...CODEMIRROR_CONFIG,
        mode: mode,
        value: value
    });
}

function markMonitorChanges() {
    if (window.dashboardAppInstance?.currentMonitor) {
        window.dashboardAppInstance.monitorHasPendingChanges = true;
    }
}

function initializeCodeEditor() {
    const mainCodeEditor = document.getElementById('monitor-code');
    const editor = createCodeEditor(mainCodeEditor, 'python');
    codeEditorInstances.main = editor;

    editor.on('change', () => {
        mainCodeEditor.value = editor.getValue();
        markMonitorChanges();
    });
}

function initializeAdditionalFileEditor(fileName) {
    const container = document.getElementById(fileName);
    if (!container) return;

    const textarea = document.createElement('textarea');
    textarea.id = `editor-${fileName}`;
    textarea.value = window.dashboardAppInstance.additionalFiles[fileName];

    const contentDiv = container.querySelector('.file-editor-content');
    contentDiv.appendChild(textarea);

    const mode = getLanguageFromFileName(fileName);
    const editor = createCodeEditor(textarea, mode, window.dashboardAppInstance.additionalFiles[fileName]);
    codeEditorInstances[fileName] = editor;

    editor.on('change', () => {
        window.dashboardAppInstance.additionalFiles[fileName] = editor.getValue();
        markMonitorChanges();
    });

    refreshEditor(editor);
}

function getCodeEditor(editorKey) {
    return codeEditorInstances[editorKey];
}

function deleteCodeEditor(editorKey) {
    if (codeEditorInstances[editorKey]) {
        codeEditorInstances[editorKey].toTextArea();
        delete codeEditorInstances[editorKey];
    }
}

function refreshEditor(editor) {
    if (editor && editor.refresh) {
        editor.refresh();
    }
}
