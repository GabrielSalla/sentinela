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
        mode: mode,
        theme: 'material-darker',
        lineNumbers: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: false,
        lineWrapping: true,
        autoCloseBrackets: true,
        matchBrackets: true,
        value: value
    });
}

function initializeCodeEditor() {
    const mainCodeEditor = document.getElementById('monitor-code');
    const editor = createCodeEditor(mainCodeEditor, 'python');
    state.codeEditors.main = editor;

    editor.on('change', () => {
        mainCodeEditor.value = editor.getValue();
    });
}

function updateAdditionalFileTabs() {
    const tabButtons = document.getElementById('tab-buttons');
    const tabContent = document.querySelector('.tab-content');

    tabButtons.querySelectorAll('.tab-button:not([onclick="switchTab(\'code-tab\')"])').forEach(tab => tab.remove());
    tabContent.querySelectorAll('.tab-pane:not(#code-tab)').forEach(pane => pane.remove());

    Object.keys(state.codeEditors).forEach(key => {
        if (key !== 'main') {
            state.codeEditors[key].toTextArea();
            delete state.codeEditors[key];
        }
    });

    Object.keys(state.additionalFiles).forEach(fileName => createFileTab(fileName));
}

function createFileTab(fileName) {
    const mode = getLanguageFromFileName(fileName);
    const content = state.additionalFiles[fileName];

    const tabButton = document.createElement('button');
    tabButton.className = 'tab-button';
    tabButton.textContent = fileName;
    tabButton.dataset.tabId = fileName;
    tabButton.onclick = () => switchTab(fileName);

    const deleteBtn = document.getElementById('delete-file-btn');
    deleteBtn.parentNode.insertBefore(tabButton, deleteBtn);

    const textarea = document.createElement('textarea');
    textarea.id = `editor-${fileName}`;
    textarea.value = content;

    const tabPane = document.createElement('div');
    tabPane.id = fileName;
    tabPane.className = 'tab-pane';
    tabPane.innerHTML = `<div class="file-editor"><div class="file-editor-content"></div></div>`;
    tabPane.querySelector('.file-editor-content').appendChild(textarea);
    document.querySelector('.tab-content').appendChild(tabPane);

    setTimeout(() => {
        const editor = createCodeEditor(textarea, mode, content);
        state.codeEditors[fileName] = editor;
        editor.on('change', () => state.additionalFiles[fileName] = editor.getValue());
        refreshEditor(editor);
    }, 50);
}

function createAdditionalFile() {
    const fileName = document.getElementById('new-file-name').value.trim();
    if (!fileName) return;

    if (state.additionalFiles[fileName]) {
        showToast('File already exists', 'error');
        return;
    }

    state.additionalFiles[fileName] = '';
    updateAdditionalFileTabs();
    document.getElementById('new-file-name').value = '';
    toggleAddFilePopover();
    switchTab(fileName);
}

function deleteCurrentFile() {
    const fileName = state.activeTab;
    if (fileName === 'code-tab' || !fileName || !(fileName in state.additionalFiles)) return;

    delete state.additionalFiles[fileName];
    updateAdditionalFileTabs();
    switchTab('code-tab');
}
