# Variables Monitor
Demonstrates the variables feature for maintaining monitor-level state. Variables store information about the monitor's execution, not about individual issues.

**How it works**: The monitor uses a variable to bookmark the last timestamp processed. This prevents reprocessing the same events across multiple monitor executions and makes searches more efficient. Variables are persisted across monitor runs and can store any data needed for monitor-level state management.
