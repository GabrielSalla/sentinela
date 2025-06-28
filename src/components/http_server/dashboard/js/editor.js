function getLanguageFromFileName(fileName) {
    const extension = fileName.split('.').pop().toLowerCase();
    const languageMap = {
        'py': 'python',
        'js': 'javascript', 
        'json': { name: 'javascript', json: true },
        'yaml': 'yaml',
        'yml': 'yaml',
        'sql': 'sql',
        'sh': 'shell',
        'md': 'markdown',
        'html': 'htmlmixed',
        'css': 'css',
        'xml': 'xml'
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

    // Clear existing additional file tabs and editors
    tabButtons.querySelectorAll('.tab-button:not([onclick="switchTab(\'code-tab\')"])').forEach(tab => tab.remove());
    tabContent.querySelectorAll('.tab-pane:not(#code-tab)').forEach(pane => pane.remove());

    // Cleanup existing editors
    Object.keys(state.codeEditors).forEach(key => {
        if (key !== 'main') {
            state.codeEditors[key].toTextArea();
            delete state.codeEditors[key];
        }
    });

    // Add additional file tabs
    state.additionalFiles.forEach((file, index) => {
        createFileTab(file, index);
    });
}

function createFileTab(file, index) {
    const tabId = `file-tab-${index}`;
    const mode = getLanguageFromFileName(file.fileName);

    // Create tab button
    const tabButton = document.createElement('button');
    tabButton.className = 'tab-button';
    tabButton.textContent = file.fileName;
    tabButton.onclick = () => switchTab(tabId);
    
    const deleteBtn = document.getElementById('delete-file-btn');
    deleteBtn.parentNode.insertBefore(tabButton, deleteBtn);

    // Create tab pane with editor
    const tabPane = document.createElement('div');
    tabPane.id = tabId;
    tabPane.className = 'tab-pane';

    const fileEditor = document.createElement('div');
    fileEditor.className = 'file-editor';

    const editorContent = document.createElement('div');
    editorContent.className = 'file-editor-content';

    const textarea = document.createElement('textarea');
    textarea.id = `editor-${index}`;
    textarea.value = file.content;

    editorContent.appendChild(textarea);
    fileEditor.appendChild(editorContent);
    tabPane.appendChild(fileEditor);
    document.querySelector('.tab-content').appendChild(tabPane);

    // Create CodeMirror editor
    setTimeout(() => {
        const editor = createCodeEditor(textarea, mode, file.content);
        state.codeEditors[`file-${index}`] = editor;
        
        editor.on('change', () => {
            state.additionalFiles[index].content = editor.getValue();
        });
        
        refreshEditor(editor);
    }, 50);
}

function createAdditionalFile() {
    const fileName = document.getElementById('new-file-name').value.trim();
    if (!fileName) return;

    if (state.additionalFiles.some(file => file.fileName === fileName)) {
        showToast('File already exists', 'error');
        return;
    }

    state.additionalFiles.push({ fileName, content: '' });
    updateAdditionalFileTabs();
    document.getElementById('new-file-name').value = '';
    toggleAddFilePopover();

    // Switch to the new file tab
    switchTab(`file-tab-${state.additionalFiles.length - 1}`);
}

function deleteCurrentFile() {
    if (state.activeTab === 'code-tab') return;
    
    const index = parseInt(state.activeTab.split('-')[2]);
    state.additionalFiles.splice(index, 1);
    updateAdditionalFileTabs();
    switchTab('code-tab');
}
