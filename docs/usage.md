# Deployment
## Configs and secrets
The basic configs are set through the `configs.yaml` file. This file is read when the application starts and all the settings will be loaded.

The application will try to load the configs file through the path defined in the `CONFIGS_FILE` environment variable. If this variable is not defined, it'll look for the file in the root directory of the application.

THe monitors path is also defined in the `configs.yaml` file. By default, it's set to the `sample_monitors` folder, but it can be changed to another folder if desired. The `configs.yaml` file also have other configurations that can be adjusted.

For the secrets, the application expects them to be set as environment variables.
- `DATABASE_APPLICATION`: The database DSN that will be used to connect to the application database. This database will not be accessible through the databases interface for the monitors.
- Every variable that starts with `DATABASE`, besides the application database, will have a connection pool instantiated, that can be used in the monitors to query data from them.
- `SLACK_TOKEN` and `SLACK_APP_TOKEN` will be used as the token to send messages to Slack and to start the websocket, to receive the events from interactions with the Sentinela Slack app.
- `AWS_ENDPOINT_URL`: The AWS endpoint to be used for local testing, without the need of a real SQS queue. When using the `motoserver` container as an AWS mock, it should be `http://motoserver:5000`. Don't set this environment variable when using a real SQS queue.
- `AWS_REGION_NAME`: The AWS region where the SQS queue is.
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_SESSION_TOKEN`: The service credentials to access the AWS SQS queue.

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
In production deployment, it's recommended that the controller and executors to be deployed in different containers or pods (in case of a kubernetes deployment). With this method a SQS queue is required to allow the controller communicate with the executors.

The deployment should set the necessary environment variables for all the instances for them to work properly.

Controllers and executors can be started passing them as parameters.
```shell
# Controller
python3 . controller

# Executor
python3 . executor
```
