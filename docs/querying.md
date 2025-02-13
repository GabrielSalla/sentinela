# Querying databases
Sentinela offers an interface to easily query data from available databases.

To prevent each monitor from managing its own database credentials, Sentinela creates shared pools for each database. This allows multiple monitors to access the same databases securely and efficiently.

# Credentials
Database credentials are provided to the application through environment variables. Each variable must:
- Begin with `DATABASE`
- End with a unique identifier for each database

> [!Note]
> The variable `DATABASE_APPLICATION` is reserved for the application's internal database and isn't available to the monitors.

For a database named `users`, set up an environment variable `DATABASE_USERS` containing the DSN for the database connection.

> [!CAUTION]
> Environment variables are accessible by all monitors, and any monitor can read or expose them. Ensure that sensitive information is handled with care by reviewing all the created monitors.

# Querying data
Monitors can query data from available databases using the `query` function, provided in the `monitor_utils` module.

The function has the following parameters:
- `name`: Name of the database where the query will be executed. For an environment variable `DATABASE_USERS` the database name is `users`.
- `sql`: SQL query to execute.
- `args`: List of arguments to substitute within the SQL statement.
- `acquire_timeout`: Sets a timeout (in seconds) for acquiring a connection from the pool. Defaults to the `database_default_acquire_timeout` setting in the `configs.yaml` file.
- `query_timeout`: The maximum maximum duration (in seconds) to execute the query. Defaults to the `database_default_query_timeout` setting in the `configs.yaml` file.

> [!WARNING]
> Refer to each specific database engine's documentation for detailed usage guidelines on each parameter, as implementation details may vary.

Any exceptions raised while acquiring a connection or executing the query are propagated to the function call.

This means that connection errors, timeouts, and SQL execution issues will not be caught within the `query` function itself. Monitors should be prepared to handle these exceptions to ensure resilience and graceful error handling.

This design allows monitors to manage exceptions according to their specific requirements, offering flexibility for logging, retries, or fallback operations.

Query metrics can be logged automatically by setting the `database_log_query_metrics` to `true` in the `configs.yaml` file.

## PostgreSQL + `asyncpg` pools
For SQL formatting and arguments usage, check [asyncpg's official documentation](https://magicstack.github.io/asyncpg/current/usage.html).
