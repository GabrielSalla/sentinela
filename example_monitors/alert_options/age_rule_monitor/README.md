# Alert Options - Age Rule Monitor
Demonstrates the `AgeRule`. The alert priority is determined by the age of the oldest active issue. Issues age over time, and older issues trigger higher priority alerts.

**How it works**: The monitor creates a new issue every 5 minutes and measures its age in seconds. As issues get older, they trigger higher priority alerts according to the configured thresholds. Issues are automatically resolved after 5 minutes have passed since creation.
