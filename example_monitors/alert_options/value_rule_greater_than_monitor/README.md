# Alert Options - Value Rule Greater Than Monitor
Demonstrates the `ValueRule` with the `greater_than` operation. The alert priority is determined by a specific numerical value from the issue data.

**How it works**: The monitor tracks a single issue with an `error_rate` that oscillates from 0 to 100, back and forth. Alert priority increases when the error rate exceeds configured thresholds. The issue is never automatically solved, demonstrating continuous monitoring of a metric.
