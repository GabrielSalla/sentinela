function createDesktopNotificationHandler(app) {
    return {
        supported: typeof Notification !== 'undefined',
        permission: typeof Notification !== 'undefined' ? Notification.permission : 'denied',
        lastShownAt: null,
        alertStates: {},

        initialize() {
            this.supported = typeof Notification !== 'undefined';
            if (!this.supported || app.settings.browserNotificationsEnabled === false) return;

            this.permission = Notification.permission;
            if (this.permission === 'default') {
                this.requestPermission();
            }
        },

        async requestPermission() {
            if (!this.supported || app.settings.browserNotificationsEnabled === false || Notification.permission !== 'default') {
                this.permission = Notification.permission;
                return;
            }

            this.permission = await Notification.requestPermission();
        },

        isPageActive() {
            return typeof document !== 'undefined'
                && document.visibilityState === 'visible'
                && document.hasFocus();
        },

        async notifyForUnacknowledgedAlerts() {
            if (app.currentSection !== 'overview' || !app.settings.browserNotificationsEnabled || !this.supported || Notification.permission !== 'granted' || this.isPageActive()) {
                return;
            }

            const monitorsWithAlerts = app.monitors.filter(monitor => monitor.enabled && monitor.active_alerts > 0);
            const unacknowledgedAlerts = [];
            const currentAlertStates = {};

            for (const monitor of monitorsWithAlerts) {
                try {
                    const alerts = await app.fetchData(`/monitor/${monitor.id}/alerts`, `Error loading alerts for ${monitor.name}`);
                    alerts.forEach(alert => {
                        const isAcknowledged = alert.is_priority_acknowledged;
                        currentAlertStates[alert.id] = isAcknowledged;
                        if (!isAcknowledged) {
                            unacknowledgedAlerts.push({
                                id: alert.id,
                                monitorName: monitor.name,
                            });
                        }
                    });
                } catch (error) {
                    console.error(`Error loading alerts for monitor ${monitor.name}:`, error);
                }
            }

            const currentAlertIds = unacknowledgedAlerts
                .sort((a, b) => a.id - b.id)
                .map(alert => alert.id);
            const previousAlertStates = this.alertStates || {};
            const immediateAlerts = unacknowledgedAlerts.filter(alert => {
                const previousState = previousAlertStates[alert.id];
                return previousState === undefined || previousState === true;
            });
            const hasImmediateAlerts = immediateAlerts.length > 0;
            const now = Date.now();
            const intervalFn = app.settingsHandler?.normalizeNotificationInterval?.bind(app.settingsHandler);
            const notificationIntervalMs = (intervalFn ? intervalFn(app.settings.notificationIntervalSeconds) : app.settings.notificationIntervalSeconds) * 1000;
            const shouldRepeatNotification = this.lastShownAt !== null
                && (now - this.lastShownAt) >= notificationIntervalMs;
            const shouldNotify = hasImmediateAlerts || shouldRepeatNotification;

            if (!currentAlertIds.length) {
                this.alertStates = {};
                this.lastShownAt = null;
                return;
            }

            if (!shouldNotify) {
                this.alertStates = currentAlertStates;
                return;
            }

            const notificationAlerts = shouldRepeatNotification || !hasImmediateAlerts
                ? unacknowledgedAlerts
                : immediateAlerts;
            const alertSummary = notificationAlerts.length === 1
                ? `${notificationAlerts[0].monitorName} has an unacknowledged alert`
                : `${notificationAlerts.map(alert => `${alert.monitorName} (#${alert.id})`).join('\n')}`;

            const notification = new Notification(notificationAlerts.length === 1 ? 'Unacknowledged alert' : `${notificationAlerts.length} unacknowledged alerts`, {
                body: alertSummary,
                tag: `sentinela-unacknowledged-alerts-${Date.now()}`,
            });

            notification.onclick = () => {
                try {
                    window.focus();
                } catch (error) {
                    console.error('Unable to focus dashboard window:', error);
                }
            };

            this.lastShownAt = now;
            this.alertStates = currentAlertStates;
        },
    };
}
