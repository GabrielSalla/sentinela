# How to run
## Development execution
Development execution should be used when developing or testing the platform features. It's not intended to be used to develop monitors as it might set variables that might interfere with the monitors execution.

To run the application in development mode, use the following command.
```shell
make run-dev
```

For testing purposes, sometimes it's useful to start a container and be able to execute multiple commands without needing to create a new container every time. This is useful when testing features, for example, as it's possible to run `pytest` for a selected list of tests. To start a container in `shell` mode, use the following command.
```shell
# Migrate the database
# Only necessary when it's the first time executing or if there're new versions
make migrate-dev

# Start the application container in shell mode
make run-shell-dev
```

To run tests, linter and type checking for the whole project, use the following commands, respectively.
```shell
make test-dev
make linter
make mypy
```

## Local execution
Local execution should be used when developing monitors and should not be used in production.

For local development, set the secrets in the `.env.secrets`, as specified in the [Configs and secrets](#configs-and-secrets) section.

When running the application locally, it's recommended to use the internal queue instead of the SQS queue for a faster and more fluid process, but it's possible to use the AWS mock or a real SQS queue.

To start the **controller** and a single **executor** (with concurrent internal executors) in the same container, run the following command.
```shell
# Only necessary when it's the first time executing or if there're new versions
make migrate-local

# Start the application
make run-local
```

This will start the database and the application.

## Production deployment
### Building the image
The [Dockerfile](../Dockerfile) is a starting point for building the application image. This file implements the logic to install all the enabled plugins dependencies correctly.

```shell
# Install the dependencies for the application and enabled plugins
poetry install --no-root --only $(python ./tools/get_plugins_list.py)
```

### Deploying the application
In production deployment, it's recommended that the controller and executors to be deployed in different containers or pods (in case of a Kubernetes deployment). With this method a SQS queue is required to allow the controller communicate with the executors.

The files provided in the [Kubernetes template](../resources/kubernetes_template) directory can be used as a reference for a Kubernetes deployment.

All services must have the environment variables set as specified in the [Configs and secrets](#configs-and-secrets) section.

Controllers and executors can be started specifying them as parameters.
```shell
# Controller
python3 src/main.py controller

# Executor
python3 src/main.py executor
```
