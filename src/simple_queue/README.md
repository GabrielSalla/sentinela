# Simple Queue

This service exists to provide a small HTTP queue for Sentinela deployments where the controller and executors run in separate containers.

Sentinela's internal queue only works inside one process. Running this service gives separate Sentinela containers a shared queue without requiring AWS SQS or another external queue service. It is intended for local development, tests, and simple deployments.

The service listens on port `5000` and provides message send, receive, visibility renewal, and delete operations for the queue plugin.

Messages are kept in memory, so they are lost when this container stops. Use a persistent external queue for production workloads.

## HTTP API

- `GET /status`: Returns `200` when the service is ready.
- `POST /messages`: Body `{"type": "...", "payload": {...}}`; returns message ID with status `201`.
- `GET /messages`: Returns one message as `{"id": "...", "content": {...}}`; `id` is the delivery token; returns `204` after the long-poll timeout.
- `POST /messages/{id}/visibility`: Extends message visibility lease; returns `204`.
- `DELETE /messages/{id}`: Deletes a successfully processed message; returns `204`.
