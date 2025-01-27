# Configuration
The basic configs are set through the `configs.yaml` file. This file is read when the application starts and all the settings will be loaded.

THe monitors path is also defined in the `configs.yaml` file. By default, it's set to the `sample_monitors` folder, but it can be changed to another folder if desired. The `configs.yaml` file also have other configurations that can be adjusted.

> [!IMPORTANT]
> Check the documentation for the plugins that are being used to see if they have environment variables of their own.

# Environment variables
## `CONFIGS_FILE`
The application will try to load the configs file through the path defined in the `CONFIGS_FILE` environment variable. If this variable is not defined, it'll look for the file in the root directory of the application.

Example:
```
CONFIGS_FILE=configs.yaml
```

## `SENTINELA_PLUGINS`
To enable a plugin, set the environment variable `SENTINELA_PLUGINS` with the name of the desired plugin. When enabling multiple plugins, separate them with commas.
- To enable the Slack plugin, the environment variable should be set as `SENTINELA_PLUGINS=slack`.
- To enable multiple plugins, the environment variable should be set as `SENTINELA_PLUGINS=plugin_1,plugin_2`.

## `DATABASE_APPLICATION`
Specifies the database DSN that will be used to connect to the application database. This database will not be accessible through the databases interface for the monitors.

Example:
```
DATABASE_APPLICATION=postgresql+asyncpg://postgres:postgres@postgres:5432/postgres
```

## `DATABASE_{NAME}`
Every variable that starts with `DATABASE`, besides the application database, will have a connection pool instantiated, that can be used in the monitors to query data from them. The variable must contain the DSN to be used to connect to the database.

For an environment variable `DATABASE_ABC`, the connection pool will be available with the name `abc`, that will be able to be used in the `query` function.

Example:
```
DATABASE_ABC=postgres://postgres:postgres@postgres:5432/postgres
```

## `AWS_ENDPOINT_URL`
`AWS_ENDPOINT_URL` specifies the AWS endpoint to be used for local testing, without the need of a real SQS queue. When using the `motoserver` container as an AWS mock, it should be `http://motoserver:5000`. Don't set this environment variable when using a real SQS queue.

Example:
```
AWS_ENDPOINT_URL=http://motoserver:5000
```

## `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_SESSION_TOKEN`
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_SESSION_TOKEN` specifies the service credentials to access the AWS SQS queue.

If the credentials does not include the session token, the `AWS_SESSION_TOKEN` environment variable should not be set.

Example:
```
AWS_ACCESS_KEY_ID=ACCESSKEYID
AWS_SECRET_ACCESS_KEY=SECRETACCESSKEY
AWS_SESSION=SESSIONTOKEN
```

or, when not using a session token,

```
AWS_ACCESS_KEY_ID=ACCESSKEYID
AWS_SECRET_ACCESS_KEY=SECRETACCESSKEY
```
