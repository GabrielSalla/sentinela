# When to use Sentinela

> **Sentinela answers "Is the business behaving correctly?"**  
> **Traditional observability tools answer "Is the system behaving correctly?"**  
> Both are complementary, not competing solutions.

Sentinela is optimized for **business invariant monitoring** -- detecting violations of business rules that require correlating data across multiple sources, applying custom logic, and tracking individual entities over time. It is not designed for real-time metric collection, log aggregation, or infrastructure health checks.

## Business invariants vs infrastructure observability

| | Business invariant monitoring | Infrastructure observability |
|---|---|---|
| **Question** | Is the business process correct? | Is the system healthy? |
| **Data** | Database records, API responses, business events | CPU, memory, latency, error rates, logs |
| **Granularity** | Entity-level (per order, per user, per transaction) | Aggregate (p95 latency, avg CPU, error count) |
| **Logic** | Complex, multi-step, state-aware | Thresholds on time-series |
| **Lifecycle** | Track issue until resolved | Alert while condition holds |
| **Example** | Orders stuck in `awaiting_delivery` while shipment is `completed` | CPU > 90% for 5 minutes |

## Comparison

| Use Case | Sentinela | Prometheus / Grafana | Datadog / New Relic |
|---|---|---|---|
| Orders stuck in processing | Query orders + shipments DB tables, track each order until resolved | Cannot correlate order/shipment state without custom exporters | Requires custom metrics + app instrumentation |
| Invoices not generated | Poll billing DB for missing invoices, auto-resolve when created | Needs app to expose `invoices_generated` metric | Same -- needs custom metric emission |
| Users charged twice | Cross-reference payments + refunds DB, track each affected user | Cannot detect without application-level metrics | Requires custom event submission |
| API latency spikes | Not the right tool -- no real-time metric ingestion | Native -- histogram + alert on p99 | Native -- APM + dashboards |
| CPU saturation | Not the right tool -- no OS-level metrics | Native -- node exporter + alert rules | Native -- infrastructure monitoring |

## When Sentinela is the best choice

Sentinela excels when:

- **The problem requires joining data from multiple sources** -- e.g., correlating orders in one table with shipments in another, or cross-referencing payments with refunds.
- **Each occurrence is a distinct entity that must be tracked individually** -- e.g., "user 123 was charged twice" creates one trackable issue for user 123.
- **The condition involves state machines or multi-step validation** -- e.g., an order should move through `created -> paid -> shipped -> delivered` and you need to detect any deviation.
- **Resolution can be detected automatically** -- e.g., when the invoice is finally generated, Sentinela sees it and closes the issue.
- **The data is accessible via SQL, APIs, or any Python code** -- Sentinela just need to reach the data.

Scenarios where this applies:

- **Orders stuck in processing** -- An order was paid but never shipped. Query the orders and shipments tables, detect the mismatch, track the order until it ships.
- **Invoices not generated** -- A subscription was renewed but no invoice was created. Query subscriptions and invoices, create an issue per missing invoice, resolve when invoice appears.
- **Users charged twice** -- A payment was processed but the refund for a canceled transaction never went through. Cross-reference payments and refunds, track each affected user.
- **Failed reconciliation** -- Daily settlement amounts don't match transaction records. Compare totals, flag the date as an issue, resolve when reconciled.

## When traditional observability tools are the best choice

Traditional observability tools (Prometheus/Grafana, Datadog, New Relic) excel when:

- **The signal is a time-series metric** -- CPU, memory, disk, request latency, error rate, throughput.
- **You need real-time or sub-minute alerting** -- Sentinela operates on cron-driven cycles, typically minutes apart.
- **The data comes from OS-level or runtime-level instrumentation** -- Node exporter, cAdvisor, application runtime metrics, JVM stats.
- **You need log aggregation and search** -- Structured or unstructured log analysis, tracing, debugging.
- **The problem is infrastructure-level** -- Host down, disk full, network partition, certificate expiry (when detected from the infrastructure side).

Scenarios where this applies:

- **API latency spikes** -- Instrument endpoints with p50/p95/p99 histograms, alert on degradation, correlate with deployments.
- **CPU saturation** -- Node exporter + alert when CPU > 90% for 5 minutes, scale up or investigate.
- **Memory leak** -- Track RSS over time, alert on sustained growth, trigger heap dump.
- **5xx error rate increase** -- Monitor HTTP error rate by endpoint, alert on anomaly, drill into logs.
- **Disk space running out** -- Alert when disk usage > 85%, automate cleanup or scale storage.

## When to use both together

The most robust setups use Sentinela alongside traditional observability. They cover different failure modes and complement each other.

**Example: orders stuck in processing**

1. **Sentinela** monitors the business invariant: an order is stuck in `awaiting_delivery` while the shipment is `completed`. It tracks each affected order, periodically refreshes its status, and resolves the issue when the order transitions to `completed`.
2. **Prometheus/Grafana** monitors the system: API latency for the order update endpoint, error rate on the shipment webhook, database connection pool saturation, queue depth for the order processing worker.

If the order processing pipeline slows down, Prometheus catches the latency spike and DB saturation. If an order slips through without being updated, Sentinela catches the business logic failure. The two tools together provide full coverage from infrastructure to business logic.

**Example: users charged twice**

1. **Sentinela** cross-references payments and refunds to detect double charges, tracks each user, and resolves when the refund is issued.
2. **Datadog** monitors the payment service: transaction success rate, payment gateway latency, error rates, host-level metrics.

When the payment gateway has an intermittent failure, Datadog alerts the platform team. When a race condition causes a double charge despite the gateway working correctly, Sentinela catches it. Without Sentinela, the double charge might go unnoticed until a customer complains.

## Rule of Thumb

Ask these questions when deciding which tool to use:

1. **Can the problem be detected by a single SQL query or API call that returns a list of failing entities?**

   Yes: Sentinela.

   No: consider observability tools.

2. **Is the problem about a specific business entity (order, user, transaction) rather than an aggregate metric?**

   Entity: Sentinela.

   Aggregate (p95, avg, rate): observability tools.

3. **Does the problem involve a business logic state machine with multiple state transitions?**

   Business state machines are a strong signal for Sentinela. When an entity moves through states like `pending -> approved -> invoiced -> paid -> reconciled`, traditional tools can only alert on error rates at the API level. They cannot tell you that entity X is stuck in `approved` while entity Y skipped `invoiced` entirely. Sentinela models the exact state machine, detects every deviation, tracks each entity individually, and resolves when the state normalizes.

   Yes (multi-state business logic): Sentinela.

   No (simple threshold or static condition): either tool may work.

4. **Does the problem require joining data from 2+ systems (DB tables, APIs, services)?**

   Yes: Sentinela.

   No: observability tools may be simpler.

5. **Can the system itself tell you there's a problem via a metric (latency, error rate, saturation)?**

   Yes: start with observability tools.

   No (e.g., the system silently fails without error logs): Sentinela.

