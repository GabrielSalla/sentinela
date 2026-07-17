# Monitor High Active Issues Count
Checks for monitors with an excessive number of active issues to prevent high resource usage.

**How it works**: The monitor queries the application database to find monitors with more than 500 active issues. Uses a `ValueRule` with the `greater_than` operation on the `active_issues_count` field. Priority thresholds: moderate >= 500, high >= 1000, critical >= 1500. Issues are automatically solved when the active issue count drops below 250.
