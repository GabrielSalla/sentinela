let selectedMonitor = null;
let selectedAlert = null;
let selectedIssue = null;
let refreshInterval = null;

async function loadOverview() {
    restoreMonitorFilters();
    await loadActiveMonitors();
    startAutoRefresh();
    setupMonitorFilters();
}

function restoreMonitorFilters() {
    const includeInternal = localStorage.getItem('monitor-filter-include-internal');
    const withAlerts = localStorage.getItem('monitor-filter-with-alerts');

    if (includeInternal !== null) {
        document.getElementById('include-internal-filter').checked = includeInternal === 'true';
    }

    if (withAlerts !== null) {
        document.getElementById('with-alerts-filter').checked = withAlerts === 'true';
    }
}

function saveMonitorFilters() {
    const includeInternal = document.getElementById('include-internal-filter').checked;
    const withAlerts = document.getElementById('with-alerts-filter').checked;

    localStorage.setItem('monitor-filter-include-internal', includeInternal);
    localStorage.setItem('monitor-filter-with-alerts', withAlerts);
}

function setupMonitorFilters() {
    const includeInternalCheckbox = document.getElementById('include-internal-filter');
    const withAlertsCheckbox = document.getElementById('with-alerts-filter');

    includeInternalCheckbox.addEventListener('change', () => {
        saveMonitorFilters();
        loadActiveMonitors();
    });
    withAlertsCheckbox.addEventListener('change', () => {
        saveMonitorFilters();
        loadActiveMonitors();
    });
}

function startAutoRefresh() {
    stopAutoRefresh();
    refreshInterval = setInterval(() => {
        loadActiveMonitors(true);
        if (selectedMonitor) loadAlertsForMonitor(selectedMonitor.id, true);
        if (selectedAlert) loadIssuesForAlert(selectedAlert.id, true);
    }, 5000);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

async function loadActiveMonitors(isAutoRefresh = false) {
    const monitorsListEl = document.getElementById('monitors-list');
    const includeInternal = document.getElementById('include-internal-filter')?.checked || false;
    const withAlerts = document.getElementById('with-alerts-filter')?.checked || false;

    try {
        const response = await fetch('/monitor/list');
        const monitors = await response.json();

        let activeMonitors = monitors.filter(monitor => monitor.enabled);

        if (!includeInternal) {
            activeMonitors = activeMonitors.filter(m => !m.name.startsWith('internal.'));
        }

        if (withAlerts) {
            activeMonitors = activeMonitors.filter(m => m.active_alerts > 0);
        }

        if (activeMonitors.length === 0) {
            monitorsListEl.innerHTML = '<p class="placeholder-text">No monitors match the filters</p>';
            return;
        }

        const regularMonitors = activeMonitors.filter(m => !m.name.startsWith('internal.')).sort((a, b) => a.name < b.name ? -1 : 1);
        const internalMonitors = activeMonitors.filter(m => m.name.startsWith('internal.')).sort((a, b) => a.name < b.name ? -1 : 1);
        const sortedMonitors = [...regularMonitors, ...internalMonitors];

        if (isAutoRefresh) {
            const existingMonitors = Array.from(monitorsListEl.querySelectorAll('.monitor-item'));
            const existingMonitorsMap = new Map(existingMonitors.map(el => {
                const monitorName = el.querySelector('.list-item-name').textContent;
                return [monitorName, el];
            }));

            sortedMonitors.forEach(monitor => {
                const existingElement = existingMonitorsMap.get(monitor.name);

                if (existingElement) {
                    const existingBadge = existingElement.querySelector('.badge-alert');
                    if (monitor.active_alerts > 0) {
                        if (existingBadge) {
                            existingBadge.textContent = monitor.active_alerts;
                        } else {
                            existingElement.innerHTML = `
                                <div class="list-item-name">${monitor.name}</div>
                                <span class="badge badge-alert">${monitor.active_alerts}</span>
                            `;
                        }
                    } else if (existingBadge) {
                        existingBadge.remove();
                    }
                } else {
                    const itemEl = document.createElement('div');
                    itemEl.className = 'list-item monitor-item';
                    if (selectedMonitor?.name === monitor.name) {
                        itemEl.classList.add('selected');
                    }
                    itemEl.onclick = (event) => selectMonitor(monitor, event);
                    itemEl.innerHTML = `
                        <div class="list-item-name">${monitor.name}</div>
                        ${monitor.active_alerts > 0 ? `<span class="badge badge-alert">${monitor.active_alerts}</span>` : ''}
                    `;
                    monitorsListEl.appendChild(itemEl);
                }
            });

            const currentMonitorNames = new Set(sortedMonitors.map(m => m.name));
            existingMonitors.forEach(el => {
                const monitorName = el.querySelector('.list-item-name').textContent;
                if (!currentMonitorNames.has(monitorName)) {
                    el.remove();
                }
            });
        } else {
            monitorsListEl.innerHTML = '';
            sortedMonitors.forEach(monitor => {
                const itemEl = document.createElement('div');
                itemEl.className = 'list-item monitor-item';
                itemEl.onclick = (event) => selectMonitor(monitor, event);
                itemEl.innerHTML = `
                    <div class="list-item-name">${monitor.name}</div>
                    ${monitor.active_alerts > 0 ? `<span class="badge badge-alert">${monitor.active_alerts}</span>` : ''}
                `;
                monitorsListEl.appendChild(itemEl);
            });
        }
    } catch (error) {
        console.error('Error loading monitors:', error);
        monitorsListEl.innerHTML = '<p class="placeholder-text">Error loading monitors</p>';
    }
}

function selectMonitor(monitor, event) {
    selectedMonitor = monitor;
    selectedAlert = null;

    clearSelection('#monitors-list .list-item');
    if (event) {
        event.target.closest('.list-item').classList.add('selected');
    }

    loadAlertsForMonitor(monitor.id);
    document.getElementById('issues-list').innerHTML = '<p class="placeholder-text">Select an alert to view issues</p>';
}

async function loadAlertsForMonitor(monitorId, isAutoRefresh = false) {
    const alertsListEl = document.getElementById('alerts-list');

    if (!isAutoRefresh) {
        alertsListEl.innerHTML = '<p class="loading-text">Loading alerts...</p>';
    }

    try {
        const response = await fetch(`/monitor/${monitorId}/alerts`);

        if (!response.ok) {
            throw new Error('Failed to load alerts');
        }

        const alerts = await response.json();

        if (alerts.length === 0) {
            alertsListEl.innerHTML = '<p class="placeholder-text">No active alerts for this monitor</p>';
            return;
        }

        const previouslySelectedAlertId = selectedAlert ? selectedAlert.id : null;

        if (isAutoRefresh) {
            const existingAlerts = new Map();
            alertsListEl.querySelectorAll('.alert-item').forEach(el => {
                const alertId = parseInt(el.querySelector('[id^="alert-actions-"]').id.replace('alert-actions-', ''));
                existingAlerts.set(alertId, el);
            });

            const currentAlertIds = new Set(alerts.map(a => a.id));

            alerts.forEach(alert => {
                const existingElement = existingAlerts.get(alert.id);

                if (existingElement) {
                    const nameDiv = existingElement.querySelector('.list-item-name');
                    nameDiv.innerHTML = `#${alert.id} ${getPriorityBadge(alert.priority)} ${getStatusBadge('Acknowledged', alert.acknowledged)} ${getStatusBadge('Locked', alert.locked)}`;

                    const actionsDiv = existingElement.querySelector(`#alert-actions-${alert.id}`);
                    const [ackBtn, lockBtn] = actionsDiv.querySelectorAll('button');
                    if (ackBtn) ackBtn.disabled = alert.can_acknowledge !== true;
                    if (lockBtn) lockBtn.disabled = alert.can_lock !== true;
                } else {
                    alertsListEl.appendChild(createAlertElement(alert, previouslySelectedAlertId));
                }
            });

            existingAlerts.forEach((el, alertId) => {
                if (!currentAlertIds.has(alertId)) el.remove();
            });
        } else {
            alertsListEl.innerHTML = '';
            alerts.forEach(alert => alertsListEl.appendChild(createAlertElement(alert, previouslySelectedAlertId)));
        }
    } catch (error) {
        console.error('Error loading alerts:', error);
        if (!isAutoRefresh) {
            alertsListEl.innerHTML = '<p class="placeholder-text">Error loading alerts</p>';
        }
    }
}

function createAlertElement(alert, previouslySelectedAlertId) {
    const itemEl = document.createElement('div');
    itemEl.className = 'list-item alert-item';
    itemEl.style.cursor = 'pointer';

    const priorityBadge = getPriorityBadge(alert.priority);
    const acknowledgedBadge = getStatusBadge('Acknowledged', alert.acknowledged);
    const lockedBadge = getStatusBadge('Locked', alert.locked);
    const alertActionsId = `alert-actions-${alert.id}`;

    const ackButton = `<button class="alert-action-btn" ${alert.can_acknowledge !== true ? 'disabled' : ''} onclick="acknowledgeAlert(${alert.id}, event)">Ack</button>`;
    const lockButton = `<button class="alert-action-btn" ${alert.can_lock !== true ? 'disabled' : ''} onclick="lockAlert(${alert.id}, event)">Lock</button>`;
    const solveButton = alert.can_solve === true ? `<button class="alert-action-btn" onclick="solveAlert(${alert.id}, event)">Solve</button>` : '';

    const isExpanded = selectedAlert && selectedAlert.id === alert.id;

    itemEl.innerHTML = `
        <div class="list-item-name">
            #${alert.id} ${priorityBadge} ${acknowledgedBadge} ${lockedBadge}
        </div>
        <div class="list-item-info">
            Triggered: ${alert.created_at}
        </div>
        <div id="${alertActionsId}" class="alert-actions" style="display: ${isExpanded ? 'block' : 'none'};">
            ${ackButton}
            ${lockButton}
            ${solveButton}
        </div>
    `;

    itemEl.onclick = (event) => {
        selectAlert(alert, event);
        toggleAlertActions(alertActionsId);
    };

    if (previouslySelectedAlertId === alert.id) {
        itemEl.classList.add('selected');
        selectedAlert = alert;
    }

    return itemEl;
}

function selectAlert(alert, event) {
    selectedAlert = alert;

    document.querySelectorAll('#alerts-list .list-item').forEach(el => {
        el.classList.remove('selected');
        const actionsDiv = el.querySelector('.alert-actions');
        if (actionsDiv) actionsDiv.style.display = 'none';
    });

    if (event) {
        event.target.closest('.list-item').classList.add('selected');
    }

    loadIssuesForAlert(alert.id);
}


async function loadIssuesForAlert(alertId, isAutoRefresh = false) {
    const issuesListEl = document.getElementById('issues-list');

    if (!isAutoRefresh) {
        issuesListEl.innerHTML = '<p class="loading-text">Loading issues...</p>';
    }

    try {
        const response = await fetch(`/alert/${alertId}/issues`);

        if (!response.ok) {
            throw new Error('Failed to load issues');
        }

        const issues = await response.json();

        if (issues.length === 0) {
            issuesListEl.innerHTML = '<p class="placeholder-text">No active issues for this alert</p>';
            return;
        }

        if (isAutoRefresh) {
            const existingIssues = Array.from(issuesListEl.querySelectorAll('.issue-item'));
            const existingIssuesMap = new Map(existingIssues.map(el => {
                const issueId = parseInt(el.querySelector('[id^="issue-"]').id.replace('issue-', ''));
                return [issueId, el];
            }));

            issues.forEach(issue => {
                const existingElement = existingIssuesMap.get(issue.id);

                if (existingElement) {
                    const metadataDiv = existingElement.querySelector(`#issue-${issue.id} pre`);
                    const newMetadataJson = JSON.stringify(issue.data || {}, null, 2);
                    if (metadataDiv.textContent !== newMetadataJson) {
                        metadataDiv.textContent = newMetadataJson;
                    }
                } else {
                    const itemEl = createIssueElement(issue);
                    issuesListEl.appendChild(itemEl);
                }
            });

            const currentIssueIds = new Set(issues.map(i => i.id));
            existingIssues.forEach(el => {
                const issueId = parseInt(el.querySelector('[id^="issue-"]').id.replace('issue-', ''));
                if (!currentIssueIds.has(issueId)) {
                    el.remove();
                }
            });
        } else {
            issuesListEl.innerHTML = '';
            issues.forEach(issue => {
                const itemEl = createIssueElement(issue);
                issuesListEl.appendChild(itemEl);
            });
        }
    } catch (error) {
        console.error('Error loading issues:', error);
        if (!isAutoRefresh) {
            issuesListEl.innerHTML = '<p class="placeholder-text">Error loading issues</p>';
        }
    }
}

function createIssueElement(issue) {
    const itemEl = document.createElement('div');
    itemEl.className = 'list-item issue-item';
    itemEl.style.cursor = 'pointer';

    const metadataJson = JSON.stringify(issue.data || {}, null, 2);
    const issueId = `issue-${issue.id}`;

    const isExpanded = selectedIssue && selectedIssue.id === issue.id;

    itemEl.innerHTML = `
        <div class="list-item-name">
            #${issue.id} - ${issue.model_id}
        </div>
        <div class="list-item-info">
            Created: ${issue.created_at}
        </div>
        <div id="${issueId}" class="issue-metadata" style="display: ${isExpanded ? 'block' : 'none'};">
            <pre>${metadataJson}</pre>
        </div>
    `;

    itemEl.onclick = () => toggleIssueMetadata(issue, issueId);

    return itemEl;
}

function toggleIssueMetadata(issue, issueId) {
    const metadataEl = document.getElementById(issueId);
    const isVisible = metadataEl.style.display !== 'none';
    metadataEl.style.display = isVisible ? 'none' : 'block';
    selectedIssue = isVisible ? null : issue;
}

function toggleAlertActions(alertActionsId) {
    const actionsEl = document.getElementById(alertActionsId);
    if (actionsEl.style.display === 'none') {
        actionsEl.style.display = 'block';
    }
}

async function acknowledgeAlert(alertId, event) {
    event?.stopPropagation();

    try {
        const response = await fetch(`/alert/${alertId}/acknowledge`, { method: 'POST' });

        if (response.ok) {
            showToast('Alert acknowledged successfully');
            const alertItem = event.target.closest('.alert-item');
            if (alertItem) {
                const badge = findBadgeByText(alertItem.querySelector('.list-item-name'), 'Acknowledged');
                updateBadgeStatus(badge, true);
                event.target.disabled = true;
            }
        } else {
            showToast('Failed to acknowledge alert', 'error');
        }
    } catch (error) {
        console.error('Error acknowledging alert:', error);
        showToast('Error acknowledging alert', 'error');
    }
}

async function lockAlert(alertId, event) {
    event?.stopPropagation();

    try {
        const response = await fetch(`/alert/${alertId}/lock`, { method: 'POST' });

        if (response.ok) {
            showToast('Alert locked successfully');
            const alertItem = event.target.closest('.alert-item');
            if (alertItem) {
                const badge = findBadgeByText(alertItem.querySelector('.list-item-name'), 'Locked');
                updateBadgeStatus(badge, true);
                event.target.disabled = true;
            }
        } else {
            showToast('Failed to lock alert', 'error');
        }
    } catch (error) {
        console.error('Error locking alert:', error);
        showToast('Error locking alert', 'error');
    }
}

async function solveAlert(alertId, event) {
    event?.stopPropagation();

    try {
        const response = await fetch(`/alert/${alertId}/solve`, { method: 'POST' });

        if (response.ok) {
            showToast('Alert solved successfully');
            if (selectedMonitor) {
                loadAlertsForMonitor(selectedMonitor.id);
            }
        } else {
            showToast('Failed to solve alert', 'error');
        }
    } catch (error) {
        console.error('Error solving alert:', error);
        showToast('Error solving alert', 'error');
    }
}

function getPriorityBadge(priority) {
    const priorities = {
        1: { text: 'Critical', class: 'badge-priority-critical' },
        2: { text: 'High', class: 'badge-priority-high' },
        3: { text: 'Moderate', class: 'badge-priority-moderate' },
        4: { text: 'Low', class: 'badge-priority-low' },
        5: { text: 'Informational', class: 'badge-priority-low' }
    };

    const priorityInfo = priorities[priority] || priorities[5];
    return `<span class="list-item-badge ${priorityInfo.class}">${priorityInfo.text}</span>`;
}

function getStatusBadge(text, isActive) {
    const badgeClass = isActive ? 'badge-status-active' : 'badge-status-inactive';
    return `<span class="list-item-badge ${badgeClass}">${text}</span>`;
}
