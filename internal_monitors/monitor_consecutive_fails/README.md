# Monitor Consecutive Fails
Checks for monitors with a high number of consecutive failed executions.

**How it works**: The monitor queries the application database to find enabled monitors whose failed executions since the last successful execution exceed the threshold. Uses a `ValueRule` with the `greater_than` operation on the `failed_count` field. Priority thresholds: moderate >= 3, high >= 5, critical >= 10. Issues are automatically solved when the monitor becomes disabled or the `failed_count` drops to 0.
