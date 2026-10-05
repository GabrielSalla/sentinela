# Real Use Cases

These are real success cases encountered in day-to-day work across payments processing and data engineering. Each one solved a real problem that traditional observability missed.

Each case describes the problem, why it was hard to catch, and how the pattern maps to entity-level monitoring.

- [Payments Processing](#payments-processing)
  - Transactions Stuck in `processing`
  - Clients With Wrong Pricing Configuration
  - Acquirer and Antifraud Conversion Drops
  - Invalid Anticipations
  - Pending Requests Left Behind
  - Internal Processes Running Too Long
- [Data Engineering](#data-engineering)
  - Airflow DAGs Left Deactivated
  - DAGs Running Too Long: Per-Table Thresholds
  - DAG Runs With Errors: Zero Tolerance Policy
  - Database Replication Lag

A broad approach across these cases: even when a problem is fixed directly in the product, the monitor is kept active with a lower execution frequency. If the problem reappears someday, it surfaces again. This mirrors application testing, where a passing test is not removed just because the code works today.

Monitors also generate metrics that can be used for later analysis. Counts of open issues over time show how often each problem recurs. Duration data shows how long issues stay open before resolution. Together they help spot trends, compare periods, support post incident review, and track whether delivery and reliability improve.

Across cases, open issues are grouped into a single alert instead of one-off alerts per entity. With grouping, the team sees the full list in one place, with priority rising as the count grows. Acknowledging shows ownership and locking freezes the current set while handling. Notifications give the team a direct point to act on any problem that appears.

On noise and false positives, the approach is:
- When a problem can be identified with certainty, the team is notified as soon as possible.
- In gray areas, the issue starts at low priority and escalates as certainty grows. Sometimes it is better to alert early and accept a false positive than to take too much time to act. The balance is calibrated against the cost of each problem.

Checks run against a read replica of the production databases, adding no load to the primaries. Queries take seconds and run every few minutes.

# Payments Processing

The approach to this kind of monitoring is straightforward. Just because something should not happen does not mean it does not need to be monitored. The product defines rules that **must** always hold, so those rules are monitored directly. When a deviation occurs, the team responsible for fixing it is notified, even in situations the product assumes will never happen.

## 1. Transactions Stuck in `processing`

### Background

- As payment processor, handling transactions through multiple states.
- Some transactions get stuck in the `processing` state and never advance. The underlying reasons are unpredictable and hard to point to a direct root cause to fix.
- At the time, stuck transactions sat silent until a customer complaint or a manual sweep.
- Monitoring notifies the operations team whenever a problem is identified, allowing quick fixing.
- Monitoring works as a safety net. Even though this should not happen in the product, if it happens the team is prepared.

### Business Invariant

- Rule: every transaction leaves `processing` within seconds.
- Unit of problem: one transaction.

### Why entity-level monitoring fits

- There is no error log or metric spike. The system looks healthy while individual transactions are stuck.
- The causes are unknown, so there is no single failure to alert on. Checking the end state (still in `processing` past timeout) catches all of them.
- This needs entity-level tracking, with each stuck transaction staying open until someone resolves it.

### How this maps to monitoring

- Poll the read replica on a schedule and list transactions that are still in `processing` past the seconds-level timeout.
- Each stuck transaction becomes one issue, refreshed on each cycle so someone can see the current state.
- The issue stays open until the transaction leaves `processing` (after the manual fix), then it resolves.
- A sudden rise in stuck transactions over a short period signals a bigger problem in the product, not an isolated case.

### Observed outcome

- Operations team can see stuck transactions early instead of waiting for a complaint.
- Metrics on how many stuck transactions are detected help prioritize solutions with the product team.

## 2. Clients With Wrong Pricing Configuration

### Background

- As payment processor, each client has pricing configured for transaction processing.
- The product has rules to prevent wrong pricing configuration, but in some scenarios it can still happen.
- When it happens, a default pricing is used, usually charging more than it should. The transactions process normally otherwise, so the problem stays silent.

### Business Invariant

- Rule: every client has valid pricing configuration, with no fallback to default pricing.
- Unit of problem: one client.

### Why entity-level monitoring fits

- There is no error log or metric spike. Transactions keep flowing, only with the wrong price.
- This needs per-client tracking, with each misconfigured client staying open until the configuration is fixed.

### How this maps to monitoring

- Poll the read replica on a schedule and list clients with wrong pricing configuration that falls back to the default value. A client configured correctly with the same pricing as the default is not an issue. The check is on the configuration, not on the price alone.
- Each misconfigured client becomes one issue, refreshed on each cycle so the team can see the current state.
- The issue stays open until the pricing configuration is corrected, then it resolves.

### Observed outcome

- Misconfigured clients surface early, before the billing impact grows.

## 3. Acquirer and Antifraud Conversion Drops

### Background

- As payment processor, transactions flow through acquirers and antifraud checks before approval.
- A sudden change in refuses within a short time frame signals a problem upstream or in routing, even when individual transactions look normal.

### Business Invariant

- Rule: refuse patterns per acquirer and antifraud provider stay within expected behavior. Sudden changes get flagged.
- Unit of problem: one acquirer or antifraud provider in a time window.

### Why entity-level monitoring fits

- In principle this could be detected through logs, but the product did not generate enough structured information to calculate it with metrics at the time.
- This needs tracking per acquirer and antifraud provider over time, not a single global error rate.

### How this maps to monitoring

- Poll the read replica on a schedule and compare recent refuse behavior per acquirer and antifraud provider against expected behavior.
- Each degrading acquirer or antifraud provider becomes one issue, refreshed on each cycle.
- The issue stays open while the behavior stays off baseline, then it resolves when conversion recovers.

### Observed outcome

- Sudden drops surface early, before the impact spreads across more transactions.
- Later the product evolved and this can be calculated with metrics, but the monitor stays active as another way of detecting problems.

## 4. Invalid Anticipations

### Background

- Customers could request anticipation of future installments. Simulating the anticipation would mark these installments.
- If the customer confirmed the request, the marks stayed. If the request was not confirmed, the marks should have been cleaned.
- A bug left marks behind even when the anticipation was never confirmed, so installments stayed flagged with no valid anticipation. The product problem was hard to diagnose and fix, so bad marks kept appearing.

### Business Invariant

- Rule: every installment marked with an anticipation id has a matching anticipation row with that id.
- Unit of problem: one anticipation that exists in the installments but not in the anticipations table.

### Why entity-level monitoring fits

- There is no error log or metric spike. Later processing sees a flag and treats it as valid, so the problem stays silent.
- The cause sits in a simulation path that is hard to reproduce, so there is no single failure to alert on. Checking the end state (flag with no matching request) catches every case.
- This needs per-anticipation tracking, with each invalid anticipation staying open until it is cleaned from the installments.

### How this maps to monitoring

- Poll the read replica on a schedule and list anticipation ids present in the installments where no anticipation row exists with that id.
- Each invalid anticipation becomes one issue, refreshed on each cycle so the team can see the current state.
- The issue stays open while the invalid anticipation is still present in the installments, then it resolves once the marks are cleaned.

### Observed outcome

- Invalid anticipations surface early and the team can apply the cleanup fix before payout or settlement uses the wrong flag.
- Because the product bug is hard to fix, the monitor works as a safety net while the root cause is investigated.

## 5. Pending Requests Left Behind

### Background

- Some requests are processed asynchronously in batches.
- The scheduled processor runs, but some requests can still be left as `pending` when they should have been processed.
- Left behind requests sit silent with no retry and no failure signal.

### Business Invariant

- Rule: no request stays `pending` after its scheduled processor has run.
- Unit of problem: one request type with pending requests left behind.

### Why entity-level monitoring fits

- There is no error log or metric spike. All requests that get processed complete successfully, so the batch run looks successful while individual requests slip through. There is no way to see the problem until checking the pending requests directly.
- A single total pending count hides which request type needs action. This needs per-type tracking until each group leaves the `pending` state. Tracking each request individually would generate too many issues, so requests are grouped by type.

### How this maps to monitoring

- Poll the read replica on a schedule and group requests still in `pending` by request type after they should have been processed.
- Each request type becomes one issue carrying the number of its pending requests. The issue stays open until that count returns to zero, then it resolves.
- Grouping by type keeps the issue list small while still showing which flow needs action. Seeing which type piled up pointed directly to the processor that needs attention.

### Observed outcome

- Requests that slip through the batch surface fast instead of waiting for a downstream complaint.
- Counts of left behind requests over time show whether the processor is keeping up or dropping work under load.

## 6. Internal Processes Running Too Long

### Background

- Internal operational processes run in the background to keep daily operations running.
- Sometimes a process can last longer than expected, either hanging or progressing slowly.

### Business Invariant

- Rule: no internal process run exceeds the expected max duration.
- Unit of problem: one process run.

### Why entity-level monitoring fits

- Aggregate duration metrics hide a single slow run. Tracking each overrunning process as its own issue allows different limits.
- A slow run often means there are too many things to process or some bottleneck is holding it back.

### How this maps to monitoring

- Query the production database for currently running processes and compare each run elapsed time against the expected max.
- Each process over its limit becomes one issue, refreshed on each cycle so the team can see the current state.
- The issue stays open while the run overruns and resolves when the run finishes.

### Observed outcome

- Slow processes are flagged individually against their own limit.
- Alerting while the run is still going gives the team time to act instead of finding out after SLA windows are missed.

# Data Engineering

In the data engineering cases, grouping brings the DAGs together into one view. Where one-off Slack messages notify each problem, alerts are easy to miss and hard to manage, with no way to know if someone is already acting and no way to know if it is already solved.

## 1. Airflow DAGs Left Deactivated

### Background

- In the data engineering context, more than 1000 Airflow DAGs ingest data to the data lake, one DAG per table.
- DAGs should always be on. For maintenance in target tables, the team turns some DAGs off manually, then turns them back on.
- Sometimes DAGs are forgotten and left deactivated, so fresh data stops arriving with no failure signal.

### Business Invariant

- Rule: no ingestion DAG stays deactivated longer than 2h.
- Unit of problem: one DAG, which maps to one table.

### Why entity-level monitoring fits

- With more than 1000 DAGs, a manual check is not viable.
- It's expected that DAGs can be deactivated during maintenance, so infra alerts cannot fire on every pause. This needs per-DAG tracking with a grace period.

### How this maps to monitoring

- Check DAG paused status on a schedule across all 1000+ DAGs.
- Only the selected DAGs are monitored. Backfill and special DAGs are left out.
- A DAG deactivated for less than 2h is ignored (maintenance grace period). Past 2h, it becomes one issue per DAG.
- The issue stays open while the DAG remains deactivated and resolves when it is turned back on.

### Observed outcome

- Alerts fire when a DAG is deactivated for more than 2h. Forgotten DAGs surface fast, without per-DAG Slack spam.

## 2. DAGs Running Too Long: Per-Table Thresholds

### Background

- Some of these ingestion DAGs sometimes take much longer than expected, either hanging or progressing slowly.
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
- Alerting before the run breaches its delivery window helps protect the data delivery SLA. The team can act while there is still time instead of declaring an incident after the SLA is missed.

## 3. DAG Runs With Errors: Zero Tolerance Policy

### Background

- The same 1000+ ingestion DAGs run under a strict policy of no DAG runs with errors.
- With that volume, manually checking every run for failures does not scale. A single failed run can block fresh data without anyone noticing.
- Reporting with one Slack message per error is impossible to manage at that scale.

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

- The zero tolerance policy becomes enforceable. Any run with an error surfaces as an open issue until resolved.
- The team investigates each case, fixes when necessary, and reruns. Automatic retries absorb transients, so only real problems surface.

## 4. Database Replication Lag

### Background

- Tables are replicated from the source database to a target through the same replication service. Only the largest tables, that have frequent inserts, are monitored. Since all tables are replicated by the same service, measuring just a couple of them reflects the replication lag of the service as a whole.
- Replication setups include AWS DMS and Debezium with Kafka and an S3 sink.
- The source database reports its own replication lag, but that number does not show problems between the replication service and the target. Replication lag can look small at the source while the target falls behind.

### Business Invariant

- Rule: the latest entry in the monitored tables is no older than a fixed threshold.
- Unit of problem: one replication task.

### Why entity-level monitoring fits

- Source-side lag metrics miss stalls downstream of the source. Checking the target end state catches them regardless of where the delay happens.

### How this maps to monitoring

- On a schedule, check the delay of the latest entry in the largest tables. Since they replicate together, those measurements reflect the lag of the whole service.
- When the delay passes the fixed threshold, the replication task becomes one issue, refreshed on each cycle.
- The issue stays open while the target lags and resolves when fresh entries arrive.

### Observed outcome

- Lag surfaces during high throughput periods of the day, when the replication service falls behind under load.

