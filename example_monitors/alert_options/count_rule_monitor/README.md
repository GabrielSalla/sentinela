# Alert Options - Count Rule Monitor
Demonstrates the `CountRule`. The alert priority is determined by the number of active issues. More active issues trigger higher priority alerts.

**How it works**: The monitor creates 5 random issues every search cycle. The alert priority increases based on the total count of active issues linked to the alert. Issues can be automatically solved based on a severity field that fluctuates randomly.
