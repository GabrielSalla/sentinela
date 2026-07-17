# Non-Solvable Issues Monitor
Demonstrates configuring issues as non-solvable. Non-solvable issues require manual intervention to be solved and cannot be automatically resolved by the monitor logic.

**How it works**: The monitor simulates finding deactivated users and creates issues for them. With `solvable=False` and `unique=True`, only one issue per user is created. If the same user appears in subsequent searches, no new issue is generated. These issues can only be solved manually through the dashboard or notifications, when available.
