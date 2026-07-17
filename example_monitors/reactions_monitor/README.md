# Reactions Monitor
Demonstrates how to configure reactions. Reactions are async callbacks triggered by specific events during monitor execution.

**How it works**: Reactions are async functions that execute in response to specific monitor events (search completion, update completion, issue creation, etc.). They receive event payloads containing monitor and issue data. This example shows the available reactions with comments explaining when each runs and what data is available.
