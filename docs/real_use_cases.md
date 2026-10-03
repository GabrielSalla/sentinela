# Real Use Cases

Here are real use cases encountered in day-to-day work across payments processing and data engineering. Each one solved a real problem that traditional observability missed.

Each case describes the problem, why it was hard to catch, and how the pattern maps to entity-level monitoring.

- [Payment Processing](#payment-processing)
  - Transactions Stuck in `processing`
  - Clients With Wrong Pricing Configuration
  - Acquirer and Antifraud Conversion Drops
- [Data Engineering](#data-engineering)
  - Airflow DAGs Left Deactivated
  - DAGs Running Too Long: Per-Table Thresholds
  - DAG Runs With Errors: Zero Tolerance Policy

A broad approach across these cases: even when a problem is fixed directly in the product, the monitor is kept active with a lower execution frequency. If the problem reappeared someday, it would surface again. This mirrors application testing, where a passing test is not removed just because the code works today.

Monitors also generated metrics that can be used for later analysis. Counts of open issues over time shows how often each problem recurred. Duration data shows how long issues stayed open before resolution. Together they help spot trends, compare periods, support post incident review, and track whether delivery and reliability improves.

Across cases, open issues are grouped into a single alert instead of one-off alerts per entity. With grouping, the team sees the full list in one place, with priority rising as the count grows. Acknowledging shows ownership and locking freezes the current set while handling. Notifications give the team a direct point to act on any problem that appears.

On noise and false positives, the approach is:
- When a problem could be identified with certainty, the team is notified as soon as possible.
- In gray areas, the issue started at low priority and escalated as certainty grew. Sometimes it is better to alert early and accept a false positive than to take too much time to act. The balance is calibrated against the cost of each problem.

Checks ran against a read replica of the production databases, adding no load to the primaries. Queries took seconds and ran every few minutes.

# Payment Processing

The approach to this kind of monitoring is straightforward. Just because something should not happen does not mean it does not need to be monitored. The product defines rules that **must** always hold, so those rules are monitored directly. When a deviation occurs, the team responsible for fixing it is notified, even in situations the product assumes will never happen.

## 1. Transactions Stuck in `processing`

### Background

- As payment processor, handling transactions through multiple states.
- Some transactions get stuck in the `processing` state and never advanced. The underlying reasons are unpredictable so there is no direct root cause to fix once.
- At the time, stuck transactions sat silent until a customer complaint or a manual sweep.
- Monitoring would notify the operations team whenever a problem is identified, allowing quick fixing.
- Monitoring worked as a safety net. Even though this should not happen in the product, if it happened the team would be prepared.

### Business Invariant

- Rule: every transaction leaves `processing` within seconds.
- Unit of problem: one transaction.

### Why entity-level monitoring fits

- There is no error log or metric spike. The system looked healthy while individual transactions are stuck.
- The causes are unknown, so there is no single failure to alert on. Checking the end state (still in `processing` past timeout) catches all of them.
- This needed entity-level tracking, with each stuck transaction staying open until someone resolved it.

### How this maps to monitoring

- Poll the read replica on a schedule and list transactions that are still in `processing` past the seconds-level timeout.
- Each stuck transaction becomes one issue, refreshed on each cycle so someone can see the current state.
- The issue stays open until the transaction leaves `processing` (after the manual fix), then it resolves.
- A sudden rise in stuck transactions over a short period signals a bigger problem in the product, not an isolated case.

### Observed outcome

- Operations team could see stuck transactions early instead of waiting for a complaint.
- Metrics on how many stuck transactions were detected helped prioritize solutions with the product team.

## 2. Clients With Wrong Pricing Configuration

### Background

- As payment processor, each client had pricing configured for transaction processing.
- The product had rules to prevent wrong pricing configuration, but in some scenarios it could still happen.
- When it happened, a default pricing is used, usually charging more than it should. The transactions processed normally otherwise, so the problem stayed silent.

### Business Invariant

- Rule: every client has valid pricing configuration, with no fallback to default pricing.
- Unit of problem: one client.

### Why entity-level monitoring fits

- There is no error log or metric spike. Transactions kept flowing, only with the wrong price.
- This needed per-client tracking, with each misconfigured client staying open until the configuration is fixed.

### How this maps to monitoring

- Poll the read replica on a schedule and list clients with wrong pricing configuration that falls back to the default value. A client configured correctly with the same pricing as the default is not an issue. The check is on the configuration, not on the price alone.
- Each misconfigured client becomes one issue, refreshed on each cycle so the team can see the current state.
- The issue stays open until the pricing configuration is corrected, then it resolves.

### Observed outcome

- Misconfigured clients surfaced early, before the billing impact grew.

## 3. Acquirer and Antifraud Conversion Drops

### Background

- As payment processor, transactions flowed through acquirers and antifraud checks before approval.
- A sudden change in refuses within a short time frame signaled a problem upstream or in routing, even when individual transactions looked normal.

### Business Invariant

- Rule: refuse patterns per acquirer and antifraud provider stay within expected behavior. Sudden changes get flagged.
- Unit of problem: one acquirer or antifraud provider in a time window.

### Why entity-level monitoring fits

- In principle this could be detected through logs, but the product did not generate enough structured information to calculate it with metrics at the time.
- This needed tracking per acquirer and antifraud provider over time, not a single global error rate.

### How this maps to monitoring

- Poll the read replica on a schedule and compare recent refuse behavior per acquirer and antifraud provider against expected behavior.
- Each degrading acquirer or antifraud provider becomes one issue, refreshed on each cycle.
- The issue stays open while the behavior stays off baseline, then it resolves when conversion recovers.

### Observed outcome

- Sudden drops surfaced early, before the impact spread across more transactions.
- Later the product evolved and this could be calculated with metrics, but the monitor stayed active as another way of detecting problems.

# Data Engineering

In the data engineering cases, grouping brought the DAGs together into one view. In cases where one-off Slack messages notified each problem, alerts were easy to miss and hard to manage, with no way to know if someone is already acting and no way to know if it is already solved.

## 1. Airflow DAGs Left Deactivated

### Background

- In the data engineering context, more than 1000 Airflow DAGs ingested data to the data lake, one DAG per table.
- DAGs should always be on. For maintenance in target tables, the team turned some DAGs off manually, then turned them back on.
- Sometimes DAGs are forgotten and left deactivated, so fresh data stopped arriving with no failure signal.

### Business Invariant

- Rule: no ingestion DAG stays deactivated longer than 2h.
- Unit of problem: one DAG, which maps to one table.

### Why entity-level monitoring fits

- With more than 1000 DAGs, a manual check is not viable.
- It's expected that DAGs can be deactivated during maintenance, so infra alerts cannot fire on every pause. This needed per-DAG tracking with a grace period.

### How this maps to monitoring

- Check DAG paused status on a schedule across all 1000+ DAGs.
- Only the selected DAGs are monitored. Backfill and special DAGs are left out.
- A DAG deactivated for less than 2h is ignored (maintenance grace period). Past 2h, it becomes one issue per DAG.
- The issue stays open while the DAG remains deactivated and resolves when it is turned back on.

### Observed outcome

- Alerts fire when a DAG is deactivated for more than 2h. Forgotten DAGs surface fast, without per-DAG Slack spam.

## 2. DAGs Running Too Long: Per-Table Thresholds

### Background

- Some of these ingestion DAGs sometimes took much longer than expected, either hanging or progressing slowly.
- Each table has a different normal duration, so one threshold for all tables does not fit. Tables that need their own timeout have it registered in a reference table. All other tables use a shared default time.

### Business Invariant

- Rule: no DAG run exceeds its table's registered timeout, or the shared default time when the table has no custom value.
- Unit of problem: one DAG run, which maps to one table (one DAG per table).

### Why entity-level monitoring fits

- Each table can carry its own limit. Join live running time from the Airflow database with the timeout registered for that table in the reference table, falling back to the shared default time when there is none.
- Aggregate duration metrics hide a single slow table. Tracking each overrunning table as its own issue allows different criteria per entity.

### How this maps to monitoring

- Query the Airflow database for currently running DAGs and compare each run's elapsed time against the timeout registered for that table, or the shared default time when there is none.
- Only the selected DAGs are monitored. Backfill DAGs are left out or given bigger time windows.
- Each table over its registered timeout or the shared default becomes one issue, with different criteria per table where needed.
- Run history per DAG can refine the expected maximum, making the alert time more assertive over time.
- The issue stays open while the run overruns and resolves when the run finishes.

### Observed outcome

- Slow tables are flagged individually against their registered timeout, or the shared default time.
- Alerting before the run breached its delivery window helped protect the data delivery SLA. The team could act while there is still time instead of declaring an incident after the SLA was missed.

## 3. DAG Runs With Errors: Zero Tolerance Policy

### Background

- The same 1000+ ingestion DAGs ran under a strict policy of no DAG runs with errors.
- With that volume, manually checking every run for failures does not scale. A single failed run could block fresh data without anyone noticing.
- Reporting with one Slack message per error was impossible to manage at that scale.

### Business Invariant

- Rule: no DAG has runs in an error state.
- Unit of problem: one DAG, which maps to one table (one DAG per table).

### Why entity-level monitoring fits

- Each DAG is a distinct entity to fix and rerun. A single total failure count hides which DAG needs action.
- Error state is visible in the Airflow database, so a scheduled check can list current failures without custom per-DAG alerting. The number of runs in error per DAG sets the urgency through a value rule.

### How this maps to monitoring

- Check recent DAG runs on a schedule and group runs in error by DAG name.
- Only the selected DAGs are monitored. Backfill and special DAGs are left out.
- Each DAG becomes one issue carrying the number of its runs in error. The issue stays open until that count returns to zero, then it resolves. A value rule escalates the alert as the count grows.

### Observed outcome

- The zero tolerance policy became enforceable. Any run with an error surfaced as an open issue until resolved.
- The team investigated each case, fixed when necessary, and reran. Automatic retries absorbed transients, so only real problems surfaced.

