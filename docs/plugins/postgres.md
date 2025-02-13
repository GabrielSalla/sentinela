# Postgres Plugin
The Postgres plugin offers a PostgreSQL database pool to be used with que `query` function.

## Enabling
To enable the PostgreSQL plugin, add `postgres` to the `plugins` list in the configuration file.

## Environment variables
The PostgreSQL pool will be used when the database DSN starts with one of the following patterns:
- `postgres://`
- `postgres+asyncpg://`
- `postgresql://`
- `postgresql+asyncpg://`

The default pool parameters are:
- `min_size`: 0
- `max_size`: 5
- `timeout`: 10
- `max_inactive_connection_lifetime`: 120
- `server_settings`: `{"application_name": "sentinela_pool"}`

For more information about the pool parameters, check the [asyncpg documentation](https://magicstack.github.io/asyncpg/current/).
