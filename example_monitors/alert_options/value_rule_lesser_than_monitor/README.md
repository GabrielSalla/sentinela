# Alert Options - Value Rule Less Than Monitor
Demonstrates the `ValueRule` with the `less_than` operation. The alert priority is determined by a specific numerical value from the issue data.

**How it works**: Similar to the Greater Than Monitor but in reverse. This monitor tracks a single issue with a `success_rate` that oscillates from 0 to 100, back and forth. Alert priority increases when the success rate drops below thresholds, demonstrating monitoring for degraded performance.
