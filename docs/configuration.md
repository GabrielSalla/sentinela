# Configuration
The basic configs are set through the `configs.yaml` file. This file is read when the application starts and all the settings will be loaded. The documentation found at [Configuration file](configuration_file.md) provides an overview of the configuration parameters available.

The monitors path is also defined in the `configs.yaml` file. By default, it's set to the `example_monitors` folder, but it can be changed to another folder if desired. The `configs.yaml` file also have other configurations that can be adjusted.

# Environment variables
> [!IMPORTANT]
> Check the documentation for the plugins that are being used to see if they have environment variables of their own.

## `CONFIGS_FILE`
The application will try to load the configs file through the path defined in the `CONFIGS_FILE` environment variable. If this variable is not defined, it'll look for the file in the root directory of the application.

Example:
```
CONFIGS_FILE=configs.yaml
```

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
