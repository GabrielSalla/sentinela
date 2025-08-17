function dashboardApp() {
    return {
        currentSection: 'overview',
        monitors: [],
        alerts: [],
        issues: [],
        selectedMonitor: null,
        selectedAlert: null,
        selectedIssue: null,
        includeInternal: true,
        withAlerts: false,
        editorMonitors: {},
        monitorsLoading: false,
        alertsLoading: false,
        issuesLoading: false,
        refreshInterval: null,

        currentMonitor: null,
        additionalFiles: {},
        activeTab: 'code-tab',
        monitorHasPendingChanges: false,
        showAddFilePopover: false,
        newFileName: '',

        switchTab(tabId) {
            this.activeTab = tabId;
            this.$nextTick(() => {
                const editor = tabId === 'code-tab' ? getCodeEditor('main') : getCodeEditor(tabId);
                if (editor) refreshEditor(editor);
            });
        },

        deleteCurrentFile() {
            const fileName = this.activeTab;
            if (fileName === 'code-tab' || !fileName || !(fileName in this.additionalFiles)) return;
            delete this.additionalFiles[fileName];
            this.$nextTick(() => {
                deleteCodeEditor(fileName);
            });
            this.switchTab('code-tab');
            this.monitorHasPendingChanges = true;
        },

        async createAdditionalFile() {
            const fileName = this.newFileName.trim();
            if (!fileName) return;
            if (fileName in this.additionalFiles) {
                showToast('File already exists', 'error');
                return;
            }
            this.additionalFiles[fileName] = '';
            this.newFileName = '';
            this.showAddFilePopover = false;
            await this.$nextTick();
            initializeAdditionalFileEditor(fileName);
            this.switchTab(fileName);
            this.monitorHasPendingChanges = true;
        },

        init() {
            window.dashboardAppInstance = this;
            this.restoreFilters();
            this.restoreColumnWidths();
            this.restoreActiveTab();
            this.showSection(this.currentSection);
            initializeCodeEditor();
            this.loadMonitorsForEditor();
            this.$nextTick(() => this.initializeResizeHandles());
        },

        restoreActiveTab() {
            const savedSection = localStorage.getItem('current-section');
            if (savedSection) {
                this.currentSection = savedSection;
            }
        },

        showSection(sectionName) {
            this.currentSection = sectionName;
            localStorage.setItem('current-section', sectionName);
            sectionName === 'overview' ? this.loadOverview() : this.stopAutoRefresh();
        },

        async loadOverview() {
            await this.loadActiveMonitors();
            this.startAutoRefresh();
        },

        restoreFilters() {
            const includeInternal = localStorage.getItem('monitor-filter-include-internal');
            const withAlerts = localStorage.getItem('monitor-filter-with-alerts');
            if (includeInternal !== null)
                this.includeInternal = includeInternal === 'true';
            if (withAlerts !== null)
                this.withAlerts = withAlerts === 'true';
        },

        saveFilters() {
            localStorage.setItem('monitor-filter-include-internal', this.includeInternal);
            localStorage.setItem('monitor-filter-with-alerts', this.withAlerts);
        },

        restoreColumnWidths() {
            ['monitors', 'alerts', 'issues'].forEach(name => {
                const width = localStorage.getItem(`column-width-${name}`);
                if (width) {
                    const col = document.getElementById(`${name}-column`);
                    if (col) {
                        col.style.width = width;
                        col.style.flex = 'none';
                    }
                }
            });
        },

        saveColumnWidth(columnId, width) {
            const key = `column-width-${columnId.replace('-column', '')}`;
            localStorage.setItem(key, width);
        },

        initializeResizeHandles() {
            const handles = document.querySelectorAll('.resize-handle');
            if (!handles.length) return;

            const getMaxWidth = (columnId) => {
                return (columnId === 'monitors-column' || columnId === 'alerts-column') ? 600 : Infinity;
            };

            handles.forEach(handle => {
                let startX, startWidth, column;

                const onMouseMove = (e) => {
                    if (!column) return;
                    const maxWidth = getMaxWidth(column.id);
                    const newWidth = Math.max(250, Math.min(maxWidth, startWidth + (e.clientX - startX)));
                    column.style.width = `${newWidth}px`;
                    column.style.flex = 'none';
                    e.preventDefault();
                };

                const onMouseUp = () => {
                    if (column) this.saveColumnWidth(column.id, column.style.width);
                    handle.classList.remove('dragging');
                    document.removeEventListener('mousemove', onMouseMove);
                    document.removeEventListener('mouseup', onMouseUp);
                    column = null;
                };

                handle.addEventListener('mousedown', (e) => {
                    column = document.getElementById(handle.dataset.column);
                    if (!column) return;

                    startX = e.clientX;
                    startWidth = column.offsetWidth;
                    handle.classList.add('dragging');

                    document.addEventListener('mousemove', onMouseMove);
                    document.addEventListener('mouseup', onMouseUp);

                    e.preventDefault();
                    e.stopPropagation();
                });
            });
        },

        onFilterChange() {
            this.saveFilters();
            this.loadActiveMonitors();
        },

        async fetchData(url, errorMessage) {
            const response = await fetch(url);
            if (!response.ok)
                throw new Error(errorMessage || `HTTP ${response.status}`);
            return response.json();
        },

        updateIfChanged(currentData, newData) {
            return JSON.stringify(currentData) !== JSON.stringify(newData);
        },

        async loadData(url, dataKey, loadingKey, showLoading, processData) {
            if (showLoading)
                this[loadingKey] = true;

            const loadData = async () => {
                const data = await this.fetchData(url);
                const processed = processData ? processData(data) : data;

                if (this.updateIfChanged(this[dataKey], processed))
                    this[dataKey] = processed;
            };

            const handleError = (error) => {
                console.error(`Error loading ${dataKey}:`, error);
                if (showLoading)
                    this[dataKey] = [];
            };

            try {
                await loadData();
            } catch (error) {
                handleError(error);
            } finally {
                if (showLoading) this[loadingKey] = false;
            }
        },

        async loadActiveMonitors(showLoading = true) {
            await this.loadData(
                '/monitor/list',
                'monitors',
                'monitorsLoading',
                showLoading,
                (monitors) => {
                    let filtered = monitors.filter(m => m.enabled);
                    if (!this.includeInternal)
                        filtered = filtered.filter(m => !m.name.startsWith('internal.'));
                    if (this.withAlerts)
                        filtered = filtered.filter(m => m.active_alerts > 0);
                    const regular = filtered.filter(m => !m.name.startsWith('internal.')).sort((a, b) => a.name.localeCompare(b.name));
                    const internal = filtered.filter(m => m.name.startsWith('internal.')).sort((a, b) => a.name.localeCompare(b.name));
                    return [...regular, ...internal];
                }
            );
        },

        async loadAlertsForMonitor(monitorId, showLoading = true) {
            await this.loadData(`/monitor/${monitorId}/alerts`, 'alerts', 'alertsLoading', showLoading);
        },

        async loadIssuesForAlert(alertId, showLoading = true) {
            await this.loadData(`/alert/${alertId}/issues`, 'issues', 'issuesLoading', showLoading);
        },

        selectMonitor(monitor) {
            this.selectedMonitor = monitor;
            this.selectedAlert = null;
            this.selectedIssue = null;
            this.issues = [];
            this.loadAlertsForMonitor(monitor.id);
        },

        selectAlert(alert) {
            this.selectedAlert = alert;
            this.selectedIssue = null;
            this.loadIssuesForAlert(alert.id);
        },

        toggleIssue(issue) {
            this.selectedIssue = this.selectedIssue?.id === issue.id ? null : issue;
        },

        async performAlertAction(alert, action, successMessage) {
            const response = await fetch(`/alert/${alert.id}/${action}`, { method: 'POST' });

            if (response.ok) {
                showToast(successMessage);
                return true;
            }

            showToast(`Failed to ${action} alert`, 'error');
            return false;
        },

        async acknowledgeAlert(alert, event) {
            event?.stopPropagation();
            const success = await this.performAlertAction(alert, 'acknowledge', 'Alert acknowledged successfully');
            if (success) {
                alert.acknowledged = true;
                this.startAutoRefresh();
            }
        },

        async lockAlert(alert, event) {
            event?.stopPropagation();
            const success = await this.performAlertAction(alert, 'lock', 'Alert locked successfully');
            if (success) {
                alert.locked = true;
                this.startAutoRefresh();
            }
        },

        async solveAlert(alert, event) {
            event?.stopPropagation();
            const success = await this.performAlertAction(alert, 'solve', 'Alert solved successfully');
            if (success && this.selectedMonitor) {
                this.loadAlertsForMonitor(this.selectedMonitor.id);
                this.startAutoRefresh();
            }
        },

        startAutoRefresh() {
            this.stopAutoRefresh();
            this.refreshInterval = setInterval(() => {
                this.loadActiveMonitors(false);
                if (this.selectedMonitor)
                    this.loadAlertsForMonitor(this.selectedMonitor.id, false);
                if (this.selectedAlert)
                    this.loadIssuesForAlert(this.selectedAlert.id, false);
            }, 5000);
        },

        stopAutoRefresh() {
            if (this.refreshInterval) {
                clearInterval(this.refreshInterval);
                this.refreshInterval = null;
            }
        },

        getPriorityBadge(priority) {
            const priorities = {
                1: { text: 'Critical', class: 'badge-priority-critical' },
                2: { text: 'High', class: 'badge-priority-high' },
                3: { text: 'Moderate', class: 'badge-priority-moderate' },
                4: { text: 'Low', class: 'badge-priority-low' },
                5: { text: 'Informational', class: 'badge-priority-low' }
            };
            return priorities[priority] || priorities[5];
        },

        getStatusBadgeClass(isActive) {
            return isActive ? 'badge-status-active' : 'badge-status-inactive';
        },

        async loadMonitorsForEditor() {
            const data = await this.fetchData(`${window.location.origin}/monitor/list`, 'Connection failed');
            this.editorMonitors = {};
            data.forEach(monitor => {
                if (!monitor.name.startsWith('internal.')) {
                    this.editorMonitors[monitor.name] = monitor;
                }
            });
        },

        get monitorsList() {
            return Object.values(this.editorMonitors);
        },

        async onMonitorSelect(event) {
            const monitorName = event.target.value;

            if (!monitorName) {
                this.currentMonitor = null;
                return;
            }

            if (monitorName === '___CREATE_NEW___') {
                this.currentMonitor = { isNew: true };
                return;
            }

            const existsOnServer = this.editorMonitors[monitorName]?.id !== undefined;
            existsOnServer ? await this.loadExistingMonitor(monitorName) : this.setNewMonitor();
        },

        async loadExistingMonitor(monitorName) {
            const data = await this.fetchData(`${window.location.origin}/monitor/${monitorName}`);
            this.currentMonitor = data;
            this.additionalFiles = data.additional_files || {};
            this.activeTab = 'code-tab';

            await this.$nextTick();

            const mainEditor = getCodeEditor('main');
            if (mainEditor) {
                mainEditor.setValue(this.currentMonitor.code);
                refreshEditor(mainEditor);
            }

            Object.keys(this.additionalFiles).forEach(fileName => {
                initializeAdditionalFileEditor(fileName);
            });

            this.monitorHasPendingChanges = false;
        },

        async setNewMonitor() {
            this.currentMonitor = { enabled: true, code: MONITOR_TEMPLATE, additional_files: {} };
            this.additionalFiles = {};
            this.activeTab = 'code-tab';

            await this.$nextTick();

            const mainEditor = getCodeEditor('main');
            if (mainEditor) {
                mainEditor.setValue(this.currentMonitor.code);
                refreshEditor(mainEditor);
            }

            this.monitorHasPendingChanges = false;
        },

        async createNewMonitor() {
            const monitorName = document.getElementById('new-monitor-name-input').value.trim();
            if (!monitorName) {
                showToast('Monitor name is required', 'error');
                return;
            }

            try {
                const formatResponse = await fetch(`${window.location.origin}/monitor/format_name/${encodeURIComponent(monitorName)}`, {
                    method: 'POST'
                });

                if (!formatResponse.ok) {
                    throw new Error(`HTTP ${formatResponse.status}: ${formatResponse.statusText}`);
                }

                const formatResult = await formatResponse.json();
                const formattedName = formatResult.formatted_name;

                const existingMonitor = this.editorMonitors[formattedName];

                if (existingMonitor && existingMonitor.id !== undefined) {
                    showToast(`Monitor with formatted name "${formattedName}" already exists. Loading existing monitor.`, 'info');
                    document.getElementById('new-monitor-name-input').value = '';
                    document.getElementById('monitor-select').value = formattedName;
                    await this.loadExistingMonitor(formattedName);
                    return;
                }

                this.editorMonitors[formattedName] = { name: formattedName, enabled: true };

                await this.$nextTick();
                document.getElementById('monitor-select').value = formattedName;
                document.getElementById('new-monitor-name-input').value = '';

                this.currentMonitor = { name: formattedName, enabled: true, code: MONITOR_TEMPLATE, additional_files: {} };
                this.additionalFiles = {};
                this.activeTab = 'code-tab';

                await this.$nextTick();

                const mainEditor = getCodeEditor('main');
                if (mainEditor) {
                    mainEditor.setValue(this.currentMonitor.code);
                    refreshEditor(mainEditor);
                }

                if (formattedName !== monitorName) {
                    showToast(`Monitor name formatted from "${monitorName}" to "${formattedName}"`, 'info');
                }

            } catch (error) {
                console.error('Error creating monitor:', error);
                showToast(`Error creating monitor: ${error.message}`, 'error');
            }
        },

        cancelNewMonitor() {
            document.getElementById('monitor-select').value = '';
            document.getElementById('new-monitor-name-input').value = '';
            this.currentMonitor = null;
        },

        async validateMonitor() {
            const code = document.getElementById('monitor-code').value;

            if (!code.trim()) {
                showValidationErrors('Monitor code is required');
                return;
            }

            hideValidationErrors();

            try {
                const response = await fetch(`${window.location.origin}/monitor/validate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ monitor_code: code })
                });

                const result = await response.json();
                if (response.ok) {
                    showToast('Monitor validated successfully!');
                } else {
                    showValidationErrors(result);
                }
            } catch (error) {
                console.error('Validation error:', error);
                showValidationErrors(`Network error: ${error.message}`);
            }
        },

        async saveMonitor() {
            const monitorName = document.getElementById('monitor-select').value;
            const code = document.getElementById('monitor-code').value;
            const enabled = this.currentMonitor?.enabled ?? document.getElementById('monitor-enabled').checked;

            if (!monitorName || !code.trim()) {
                showValidationErrors('Monitor name and code are required');
                return;
            }

            hideValidationErrors();

            try {
                const response = await fetch(`${window.location.origin}/monitor/register/${monitorName}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        monitor_code: code,
                        additional_files: this.additionalFiles
                    })
                });

                const result = await response.json();

                if (response.ok) {
                    showToast('Monitor saved successfully!');
                    const endpoint = enabled ? 'enable' : 'disable';
                    await fetch(`${window.location.origin}/monitor/${monitorName}/${endpoint}`, { method: 'POST' })
                        .catch(error => console.error(`Error ${endpoint}ing monitor:`, error));

                    this.monitorHasPendingChanges = false;
                    await this.loadMonitorsForEditor();
                } else {
                    showValidationErrors(result);
                }
            } catch (error) {
                console.error('Save error:', error);
                showValidationErrors(`Network error: ${error.message}`);
            }
        },

        toggleMonitorEnabled() {
            if (this.currentMonitor) {
                this.currentMonitor.enabled = !this.currentMonitor.enabled;
                this.monitorHasPendingChanges = true;
            }
        },
    };
}
