function fetchWithAuth(url, options = {}) {
    return fetch(url, { credentials: "include", ...options });
}

function dashboardApp() {
    const savedSection = localStorage.getItem('current-section');
    return {
        currentSection: savedSection === 'overview' || savedSection === 'editor' ? savedSection : 'overview',
        monitors: [],
        alerts: [],
        issues: [],
        selectedMonitor: null,
        selectedMonitorDetails: null,
        selectedAlert: null,
        selectedIssue: null,
        editorMonitors: {},
        monitorsLoading: false,
        monitorDetailsLoading: false,
        alertsLoading: false,
        issuesLoading: false,
        refreshInterval: null,

        currentMonitor: null,
        additionalFiles: {},
        activeTab: 'code-tab',
        monitorHasPendingChanges: false,
        showAddFilePopover: false,
        newFileName: '',
        sentinela_configs: {},
        currentUser: null,
        usersList: [],
        dropIssueIds: '',
        dropResults: [],
        droppingIssues: false,

        settings: {
            overviewFilterIncludeInternalMonitors: true,
            overviewFilterWithAlerts: false,
            notificationIntervalSeconds: 60,
            browserNotificationsEnabled: true,
        },
        showSettingsModal: false,
        settingsHandler: null,
        docCollapsed: false,

        desktopNotificationsSupported: false,
        desktopNotificationsPermission: 'default',
        desktopNotificationsHandler: null,

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

        async loadConfigs() {
            try {
                const response = await fetchWithAuth(`${window.location.origin}/configs`);
                const data = await response.json();
                if (data.configs) {
                    this.sentinela_configs = data.configs;
                }
            } catch (error) {
                console.error('Error loading configs:', error);
                this.sentinela_configs = {};
            }
        },

        init() {
            window.dashboardAppInstance = this;
            this.initializeSettings();
            this.restoreColumnWidths();
            this.restoreActiveTab();
            this.initializeDesktopNotifications();
            this.ensureAuth().then((authenticated) => {
                if (!authenticated) return;
                this.showSection(this.currentSection);
            });
            initializeCodeEditor();
            this.loadConfigs();
            this.loadMonitorsForEditor();
            this.$nextTick(() => this.initializeResizeHandles());
        },

        async ensureAuth() {
            try {
                const response = await fetchWithAuth(`${window.location.origin}/auth/me`);
                if (response.status === 401) {
                    window.location.href = '/dashboard/login.html';
                    return false;
                }
                const data = await response.json();
                if (data.require_change_password) {
                    window.location.href = '/dashboard/change-password.html';
                    return false;
                }
                this.currentUser = data;
                return true;
            } catch (error) {
                console.error('Error checking auth:', error);
                return false;
            }
        },

        async logout() {
            await fetchWithAuth(`${window.location.origin}/auth/logout`, { method: 'POST' });
            window.location.href = '/dashboard/login.html';
        },

        async loadUsers() {
            try {
                const response = await fetchWithAuth(`${window.location.origin}/auth/users`);
                if (response.status === 401) {
                    window.location.href = '/dashboard/login.html';
                    return;
                }
                if (!response.ok) return;
                this.usersList = await response.json();
            } catch (error) {
                console.error('Error loading users:', error);
            }
        },

        async createUser() {
            const username = document.getElementById('new-username').value.trim();
            const role = document.getElementById('new-role').value;
            if (!username) {
                showToast('Username is required', 'error');
                return;
            }
            try {
                const response = await fetchWithAuth(`${window.location.origin}/auth/users`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, role })
                });
                const result = await response.json();
                if (response.ok) {
                    await this.copyInviteLink(result.invite_url);
                    document.getElementById('new-username').value = '';
                    await this.loadUsers();
                } else {
                    showToast(result.message || 'Failed to create user', 'error');
                }
            } catch (error) {
                console.error('Error creating user:', error);
                showToast('Connection failed', 'error');
            }
        },

        async copyInviteLink(inviteUrl) {
            const link = `${window.location.origin}${inviteUrl}`;
            try {
                await navigator.clipboard.writeText(link);
                showToast('Invite link copied to clipboard');
            } catch (error) {
                console.error('Error copying invite link:', error);
                showToast('Could not copy invite link automatically', 'error');
            }
        },

        async recreateInvite(username) {
            try {
                const response = await fetchWithAuth(`${window.location.origin}/auth/users/${encodeURIComponent(username)}/invite`, {
                    method: 'POST'
                });
                const result = await response.json();
                if (response.ok) {
                    await this.copyInviteLink(result.invite_url);
                } else {
                    showToast(result.message || 'Failed to create invite link', 'error');
                }
            } catch (error) {
                console.error('Error creating invite link:', error);
                showToast('Connection failed', 'error');
            }
        },

        async setUserActive(username, active) {
            const action = active ? 'enable' : 'disable';
            try {
                const response = await fetchWithAuth(`${window.location.origin}/auth/users/${encodeURIComponent(username)}/${action}`, {
                    method: 'POST'
                });
                const result = await response.json();
                if (response.ok) {
                    showToast(`User ${action}d`);
                } else {
                    showToast(result.message || `Failed to ${action} user`, 'error');
                }
                await this.loadUsers();
            } catch (error) {
                console.error(`Error ${action}ing user:`, error);
                showToast('Connection failed', 'error');
            }
        },

        async dropIssues() {
            if (!this.canExecuteCommand('issue_drop')) {
                showToast('Issue drop not available (disabled or insufficient role)', 'error');
                return;
            }
            const issueIds = [...new Set(this.dropIssueIds.split(/[\s,]+/).filter(Boolean))];
            if (issueIds.length === 0) {
                showToast('At least one issue ID is required', 'error');
                return;
            }
            if (!window.confirm(`Drop ${issueIds.length} issue(s)?`)) return;

            this.droppingIssues = true;
            this.dropResults = [];
            try {
                for (const issueId of issueIds) {
                    if (!/^\d+$/.test(issueId)) {
                        this.dropResults.push({ id: issueId, success: false, message: 'Invalid issue ID' });
                        continue;
                    }

                    const response = await fetchWithAuth(`/issue/${encodeURIComponent(issueId)}/drop`, {
                        method: 'POST'
                    });
                    const result = await response.json();
                    this.dropResults.push({
                        id: issueId,
                        success: response.ok,
                        message: response.ok ? 'Drop queued' : (result.message || 'Drop failed')
                    });
                }
                this.dropIssueIds = '';
            } catch (error) {
                console.error('Error dropping issues:', error);
                showToast('Connection failed', 'error');
            } finally {
                this.droppingIssues = false;
            }
        },

        initializeSettings() {
            this.settingsHandler = createDashboardSettingsHandler(this);
            this.settingsHandler.restoreSettings();
        },

        initializeDesktopNotifications() {
            this.desktopNotificationsHandler = createDesktopNotificationHandler(this);
            this.desktopNotificationsHandler.initialize();
            this.desktopNotificationsSupported = this.desktopNotificationsHandler.supported;
            this.desktopNotificationsPermission = this.desktopNotificationsHandler.permission;
        },

        async requestDesktopNotificationsPermission() {
            if (!this.desktopNotificationsHandler) {
                this.desktopNotificationsPermission = Notification.permission;
                return;
            }

            await this.desktopNotificationsHandler.requestPermission();
            this.desktopNotificationsPermission = this.desktopNotificationsHandler.permission;
        },

        async notifyForUnacknowledgedAlerts() {
            if (!this.desktopNotificationsHandler) {
                return;
            }

            await this.desktopNotificationsHandler.notifyForUnacknowledgedAlerts();
        },

        restoreActiveTab() {
            const savedSection = localStorage.getItem('current-section');
            if (savedSection) {
                this.currentSection = savedSection;
            }
        },

        showSection(sectionName) {
            this.currentSection = sectionName;
            if (sectionName === 'overview' || sectionName === 'editor') {
                localStorage.setItem('current-section', sectionName);
            }
            if (sectionName === 'overview') {
                this.loadOverview();
            } else if (sectionName === 'users') {
                this.stopAutoRefresh();
                this.loadUsers();
            } else {
                this.stopAutoRefresh();
            }
        },

        async loadOverview() {
            await this.loadActiveMonitors();
            this.startAutoRefresh();
        },

        restoreSettings() {
            if (!this.settingsHandler) {
                this.initializeSettings();
            }
            return this.settingsHandler.restoreSettings();
        },

        saveSettings() {
            if (!this.settingsHandler) {
                this.initializeSettings();
            }
            return this.settingsHandler.saveSettings();
        },

        openSettingsModal() {
            if (!this.settingsHandler) {
                this.initializeSettings();
            }
            return this.settingsHandler.openSettingsModal();
        },

        closeSettingsModal() {
            if (!this.settingsHandler) {
                this.initializeSettings();
            }
            return this.settingsHandler.closeSettingsModal();
        },

        renderMarkdown(text) {
            if (!text) return '';
            if (typeof marked !== 'undefined' && marked.parse) {
                return marked.parse(text);
            }
            return `<pre style="white-space:pre-wrap;color:var(--text)">${text}</pre>`;
        },

        saveSettingsAndClose() {
            if (!this.settingsHandler) {
                this.initializeSettings();
            }
            return this.settingsHandler.saveSettingsAndClose();
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
            document.querySelectorAll('.resize-handle').forEach(handle => {
                let startX, startWidth, column;

                const getMaxWidth = (columnId) => {
                    return (columnId === 'monitors-column' || columnId === 'alerts-column') ? 600 : Infinity;
                };

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

            document.querySelectorAll('.resize-handle-h').forEach(handle => {
                let startY, startHeight, target;

                const onMouseMove = (e) => {
                    if (!target) return;
                    const newHeight = Math.max(60, startHeight + (startY - e.clientY));
                    target.style.height = `${newHeight}px`;
                    e.preventDefault();
                };

                const onMouseUp = () => {
                    if (target) {
                        const key = `doc-section-height`;
                        localStorage.setItem(key, target.style.height);
                    }
                    handle.classList.remove('dragging');
                    document.removeEventListener('mousemove', onMouseMove);
                    document.removeEventListener('mouseup', onMouseUp);
                    target = null;
                };

                handle.addEventListener('mousedown', (e) => {
                    const selector = handle.dataset.resize;
                    target = selector ? document.querySelector(`.${selector}`) : null;
                    if (!target) return;

                    startY = e.clientY;
                    startHeight = target.offsetHeight;
                    handle.classList.add('dragging');

                    document.addEventListener('mousemove', onMouseMove);
                    document.addEventListener('mouseup', onMouseUp);

                    e.preventDefault();
                    e.stopPropagation();
                });
            });
        },

        onFilterChange() {
            this.saveSettings();
            this.loadActiveMonitors();
        },

        async fetchData(url, errorMessage) {
            const response = await fetchWithAuth(url);
            if (response.status === 401) {
                window.location.href = '/dashboard/login.html';
                throw new Error('Unauthorized');
            }
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
                    if (!this.settings.overviewFilterIncludeInternalMonitors)
                        filtered = filtered.filter(m => !m.name.startsWith('internal.'));
                    if (this.settings.overviewFilterWithAlerts)
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

        async loadMonitorDetails(monitorName, showLoading = true) {
            if (!monitorName) {
                this.selectedMonitorDetails = null;
                return;
            }

            if (showLoading) {
                this.monitorDetailsLoading = true;
            }

            try {
                const data = await this.fetchData(`/monitor/${encodeURIComponent(monitorName)}`);
                if (this.selectedMonitor?.name === monitorName) {
                    this.selectedMonitorDetails = data;
                }
            } catch (error) {
                console.error('Error loading monitor details:', error);
                if (this.selectedMonitor?.name === monitorName) {
                    this.selectedMonitorDetails = null;
                }
            } finally {
                if (showLoading) {
                    this.monitorDetailsLoading = false;
                }
            }
        },

        async loadIssuesForAlert(alertId, showLoading = true) {
            await this.loadData(`/alert/${alertId}/issues`, 'issues', 'issuesLoading', showLoading);
        },

        selectMonitor(monitor) {
            this.selectedMonitor = monitor;
            this.selectedMonitorDetails = null;
            this.selectedAlert = null;
            this.selectedIssue = null;
            this.issues = [];
            this.loadAlertsForMonitor(monitor.id);
            this.loadMonitorDetails(monitor.name);
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
            const commandByAction = {
                acknowledge: 'alert_acknowledge',
                lock: 'alert_lock',
                solve: 'alert_solve',
            };
            const command = commandByAction[action];
            if (command && !this.canExecuteCommand(command)) {
                showToast(`Failed to ${action} alert`, 'error');
                return false;
            }
            const response = await fetchWithAuth(`/alert/${alert.id}/${action}`, { method: 'POST' });

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
                alert.is_priority_acknowledged = true;
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
            this.refreshInterval = setInterval(async () => {
                await this.loadActiveMonitors(false);
                if (this.selectedMonitor) {
                    await this.loadAlertsForMonitor(this.selectedMonitor.id, false);
                    await this.loadMonitorDetails(this.selectedMonitor.name, false);
                }
                if (this.selectedAlert)
                    await this.loadIssuesForAlert(this.selectedAlert.id, false);
                await this.notifyForUnacknowledgedAlerts();
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

        getMonitorStatusClass(monitor) {
            if (!monitor) return 'monitor-status-badge waiting';
            if (monitor.running) return 'monitor-status-badge running';
            if (monitor.queued) return 'monitor-status-badge queued';
            return 'monitor-status-badge waiting';
        },

        getMonitorStatusTitle(monitor) {
            if (!monitor) return 'Waiting schedule';
            if (monitor.running) return 'Running';
            if (monitor.queued) return 'Queued';
            return 'Waiting schedule';
        },

        isAlertAcknowledged(alert) {
            if (!alert) return false;
            return alert.is_priority_acknowledged === true;
        },

        isAlertLocked(alert) {
            if (!alert) return false;
            return alert.locked === true;
        },

        getStatusBadgeClass(isActive) {
            return isActive ? 'badge-status-active' : 'badge-status-inactive';
        },

        canExecuteCommand(command) {
            const config = this.sentinela_configs?.http_server?.commands?.[command];
            if (config?.enabled === false) return false;
            if (!this.currentUser) return false;
            if (this.currentUser.role === 'admin') return true;
            return (config?.required_role ?? 'user') === 'user';
        },

        canToggleMonitorEnabled() {
            if (!this.currentMonitor || this.currentMonitor.isNew) return false;
            const target = this.currentMonitor.enabled ? 'monitor_disable' : 'monitor_enable';
            return this.canExecuteCommand(target);
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
            return Object.values(this.editorMonitors).sort((a, b) => a.name.localeCompare(b.name));
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
            Object.keys(this.additionalFiles).forEach(fileName => {
                deleteCodeEditor(fileName);
            });
            const files = {};
            if (data.documentation != null) {
                files['README.md'] = data.documentation;
            }
            Object.assign(files, data.additional_files || {});
            this.additionalFiles = files;
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
            Object.keys(this.additionalFiles).forEach(fileName => {
                deleteCodeEditor(fileName);
            });
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
                const formatResponse = await fetchWithAuth(`${window.location.origin}/monitor/format_name/${encodeURIComponent(monitorName)}`, {
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
                Object.keys(this.additionalFiles).forEach(fileName => {
                    deleteCodeEditor(fileName);
                });
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
            if (!this.canExecuteCommand('monitor_validate')) {
                showValidationErrors('Monitor validation not available (disabled or insufficient role)');
                return;
            }
            const code = document.getElementById('monitor-code').value;

            if (!code.trim()) {
                showValidationErrors('Monitor code is required');
                return;
            }

            hideValidationErrors();

            try {
                const response = await fetchWithAuth(`${window.location.origin}/monitor/validate`, {
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
            if (!this.canExecuteCommand('monitor_register')) {
                showValidationErrors('Monitor registration not available (disabled or insufficient role)');
                return;
            }
            const monitorName = document.getElementById('monitor-select').value;
            const code = document.getElementById('monitor-code').value;
            const enabled = this.currentMonitor?.enabled ?? document.getElementById('monitor-enabled').checked;

            if (!monitorName || !code.trim()) {
                showValidationErrors('Monitor name and code are required');
                return;
            }

            hideValidationErrors();

            try {
                const response = await fetchWithAuth(`${window.location.origin}/monitor/register/${monitorName}`, {
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
                    if (!this.canExecuteCommand(`monitor_${endpoint}`)) {
                        console.warn(`Monitor ${endpoint} not available (disabled or insufficient role)`);
                    } else {
                        await fetchWithAuth(`${window.location.origin}/monitor/${monitorName}/${endpoint}`, { method: 'POST' })
                            .catch(error => console.error(`Error ${endpoint}ing monitor:`, error));
                    }

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

        async toggleMonitorEnabled(event) {
            const checkbox = event.target;
            const action = checkbox.checked ? 'enable' : 'disable';
            try {
                const response = await fetchWithAuth(`${window.location.origin}/monitor/${this.currentMonitor.name}/${action}`, { method: 'POST' });
                if (response.ok) {
                    this.currentMonitor.enabled = checkbox.checked;
                    if (this.editorMonitors[this.currentMonitor.name]) {
                        this.editorMonitors[this.currentMonitor.name].enabled = checkbox.checked;
                    }
                    showToast(`Monitor ${checkbox.checked ? 'enabled' : 'disabled'} successfully`);
                } else {
                    checkbox.checked = this.currentMonitor.enabled;
                    const result = await response.json().catch(() => ({}));
                    showToast(result.message || `Failed to ${action} monitor`, 'error');
                }
            } catch (error) {
                checkbox.checked = this.currentMonitor.enabled;
                console.error(`Error ${action}ing monitor:`, error);
                showToast('Connection failed', 'error');
            }
        },
    };
}
