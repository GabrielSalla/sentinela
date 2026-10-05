# Sentinela: is the application behaving correctly?
Sentinela is open-source **application-logic monitoring** in Python. It detects application rule violations and data inconsistencies that need correlating data across databases/APIs, applying custom logic, and tracking each affected entity until resolved.

If the problem can be expressed as *"a Python function returning a list of failing entities"* — via SQL, API calls, files, or any Python code joining multiple sources — Sentinela fits.

Typical cases: **stuck orders** (paid but never shipped), **missing invoices**, **double charges**, **failed reconciliation**, **invalid registration data**, **state-transition violations**.

Traditional observability (Prometheus / Grafana / Datadog) answers *"is the system healthy?"* (CPU, latency, error rates). Sentinela answers *"is the application correct?"* (per order / user / transaction). Most setups run both. See [When to use Sentinela](when_to_use_sentinela.md) and [Real Use Cases](real_use_cases.md).

## How it works
Write three Python functions per monitor — Sentinela schedules, tracks, alerts, and auto-resolves:
1. `search()` — find current issues (e.g. orders stuck in `awaiting_delivery`
   while shipment is `completed`).
2. `update(issues)` — refresh data for active issues by ID (fast, keyed lookup).
3. `is_solved(issue)` — return `True` when the entity is back to normal.

Each issue is one entity: one order, one user, one transaction. Issues roll up into alerts. Priority escalates P5 → P1 based on the rule you choose: oldest issue age, issue count, or a numeric field in the issue. You can acknowledge an alert (mark as seen) or lock it (freeze it so new issues open a fresh alert). Notifications go out via plugins (Slack, ntfy, custom).

Start with [Overview](overview.md), then [Building a Monitor](monitor.md) and [Monitor lifecycle](monitor_lifecycle.md).

## Search terms for this category
Application invariant monitoring, application logic monitoring, business invariant monitoring, business process monitoring, data quality monitoring, database consistency monitoring, entity-level issue tracking, cross-system validation, automated reconciliation, state-machine monitoring.
