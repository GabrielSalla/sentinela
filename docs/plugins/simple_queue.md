# Simple Queue

Simple Queue is an in-memory HTTP queue for deployments where the controller and executors run in separate containers. It listens on `0.0.0.0:5000`.

Start it with:

```shell
python -m simple_queue.simple_queue
```

## Queue Settings

Configure the plugin used to access Simple Queue under `application_queue`:

```yaml
application_queue:
  type: plugin.simple_queue.queues.http
  url: http://simple-queue:5000
```

The plugin type must match the queue plugin implementation. `url` must be reachable from every Sentinela container. The queue uses a `2` second long-poll timeout and a `15` second visibility lease.

Messages are stored in memory and are lost when the container stops. Use a persistent external queue for production workloads.
