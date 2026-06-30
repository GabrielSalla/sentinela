function createDashboardSettingsHandler(app) {
    return {
        normalizeNotificationInterval(value) {
            const parsedValue = Number(value);
            if (!Number.isFinite(parsedValue) || parsedValue < 1) {
                return 60;
            }
            return Math.floor(parsedValue);
        },

        restoreSettings() {
            const storedSettings = localStorage.getItem('dashboard-settings');
            if (!storedSettings) {
                app.settings.overviewFilterIncludeInternalMonitors = app.settings.overviewFilterIncludeInternalMonitors !== false;
                app.settings.overviewFilterWithAlerts = app.settings.overviewFilterWithAlerts === true;
                return;
            }

            try {
                const parsedSettings = JSON.parse(storedSettings);
                app.settings = {
                    ...app.settings,
                    ...parsedSettings,
                };
            } catch (error) {
                console.error('Error restoring dashboard settings:', error);
            }

            app.settings.browserNotificationsEnabled = app.settings.browserNotificationsEnabled !== false;
            app.settings.notificationIntervalSeconds = this.normalizeNotificationInterval(app.settings.notificationIntervalSeconds);
            app.settings.overviewFilterIncludeInternalMonitors = app.settings.overviewFilterIncludeInternalMonitors !== false;
            app.settings.overviewFilterWithAlerts = app.settings.overviewFilterWithAlerts === true;
        },

        saveSettings() {
            app.settings.browserNotificationsEnabled = app.settings.browserNotificationsEnabled !== false;
            app.settings.notificationIntervalSeconds = this.normalizeNotificationInterval(app.settings.notificationIntervalSeconds);
            app.settings.overviewFilterIncludeInternalMonitors = app.settings.overviewFilterIncludeInternalMonitors !== false;
            app.settings.overviewFilterWithAlerts = app.settings.overviewFilterWithAlerts === true;
            localStorage.setItem('dashboard-settings', JSON.stringify(app.settings));
        },

        openSettingsModal() {
            app.showSettingsModal = true;
        },

        closeSettingsModal() {
            app.showSettingsModal = false;
        },

        saveSettingsAndClose() {
            this.saveSettings();
            this.closeSettingsModal();
            showToast('Settings saved');
        },
    };
}
