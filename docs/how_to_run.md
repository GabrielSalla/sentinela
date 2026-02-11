# How to Run

## Development Execution
Development execution should be used when developing or testing the platform features. **It is not intended for developing monitors**, as it might set variables that interfere with monitor execution.

1. Migrate the database to the latest version. This is only necessary when running for the first time or after updates.
    ```shell
    make migrate-dev
    ```
2. Run the application in development mode.
    ```shell
    make run-dev
    ```

For testing purposes, it can be useful to start a container and execute multiple commands without creating a new container each time. This is helpful when testing features, such as running `pytest` for a selected list of tests.

1. Start the application container in shell mode.
    ```shell
    make run-shell-dev
    ```
2. When inside the container, the application can be run in development mode.
    ```shell
    sentinela controller executor
    ```
    or omitting the parameters to run both the controller and executor.

The quality checks can also be run using the following commands:
1. Run the tests.
    ```shell
    make test-dev
    ```
2. Run the linter (ruff).
    ```shell
    make linter
    ```
3. Run the type checker (mypy).
    ```shell
    make mypy
    ```

## Local Execution - Single Container
Local execution is recommended for developing monitors. It should not be used in production but provides a quick way to experiment with the application before committing to a more complex deployment.

**Pros**:
- Quick to set up and run with the included `docker-compose` and config files.
- Easy to create and modify monitors from the host machine.
- No need for external services like a database or queues, as everything runs locally.

**Cons**:
- Difficult to scale horizontally.
- Creating and modifying monitors from outside the host can be cumbersome, as the client must connect to the controller.
- Hard to monitor the application.
- Running the database locally increases the risk of data loss.

When running the application locally, it is recommended to use the internal queue instead of the SQS queue for faster and smoother operation. However, it is also possible to use the AWS queue mock or a real SQS queue.

1. Set the secrets in the `.env.secrets` file and environment variables in the `docker/docker-compose-local.yml` file, as specified in the [Configuration](./configuration.md) documentation.
2. Migrate the database to the latest version. This is only necessary when running for the first time or after updates.
    ```shell
    make migrate-local
    ```
3. Start the application. The local database will also be started.
    ```shell
    make run-local
    ```

## Local Execution - Multiple Containers
For a more scalable deployment, it is recommended to use separate containers for the controller and executor. This approach allows running multiple executor containers, increasing concurrency when processing a high number of monitors. This setup can still run on a single machine without requiring external services.

**Pros**:
- Quick to set up and run with the included `docker-compose` and config files.
- Easy to create and modify monitors from the host machine.
- Easy to scale horizontally by increasing the number of executor replicas.
- No need for external services like a database or queues, as everything runs locally.

**Cons**:
- A local container for the queue is required if not using an external queue. One is already included in the `docker-compose-scalable.yml` file.
- Creating and modifying monitors from outside the host can be cumbersome, as the client must connect to the controller.
- Hard to monitor the application.
- Running the database locally increases the risk of data loss.

The `docker-compose` file for this setup includes a SQS queue mock, which is used by default. However, it is also possible to use the internal queue or a real SQS queue.

1. Set the secrets in the `.env.secrets` file and environment variables in the `docker/docker-compose-scalable.yml` file, as specified in the [Configuration](./configuration.md) documentation.
2. Set the `replicas` parameter in the `docker/docker-compose-scalable.yml` file to the desired number of executors.
3. Migrate the database to the latest version. This is only necessary when running for the first time or after updates.
    ```shell
    make migrate-scalable
    ```
4. Start a container for the controller and executors.
    ```shell
    make run-scalable
    ```

## Production Deployment
For production deployment, it is recommended to use a more complex setup with multiple containers or pods (in the case of a Kubernetes deployment) to allow for better resource management and scaling. This setup requires a database, a message queue, and the application itself.

**Pros**:
- Allows horizontal scaling of executors by adding more containers or pods.
- Persistent storage with an external database.
- Enables monitoring the application with external tools.
- Allows creating and modifying monitors from any client that can connect to the controller.

**Cons**:
- More complex to set up and maintain.
- Creating and modifying monitors can be more complicated, as a connection to the controller is required.
- Requires an external database and message queue.

### Building the Image
The [Dockerfile](../Dockerfile) is a starting point for building the application image. This file implements the logic to install all dependencies for the enabled plugins.

1. Install the dependencies for the application and enabled plugins.
    ```shell
    poetry install --no-root --only $(get_plugins_list)
    ```

### Deploying the Application
In production deployment, it is recommended to deploy the controller and executors in separate containers or pods (in the case of a Kubernetes deployment). This method requires an external queue to allow communication between the controller and executors. A persistent database is also recommended to prevent data loss.

The files provided in the [Kubernetes template](../resources/kubernetes_template) directory can be used as a reference for a Kubernetes deployment.

All services must have the environment variables set as specified in the [Configuration](./configuration.md) documentation.

Controllers and executors can be run by specifying them as parameters when starting the application:
1. Run the controller.
    ```shell
    sentinela controller
    ```
2. Run the executor.
    ```shell
    sentinela executor
    ```
