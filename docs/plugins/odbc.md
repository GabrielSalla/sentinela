# ODBC Plugin
The ODBC plugin offers an ODBC database pool to be used with the `query` function.

## Enabling
To enable the ODBC plugin, add `odbc` to the `plugins` list in the configuration file.

## Environment variables
The ODBC pool will be used when the database DSN starts with the following pattern:
- `odbc://`

Example:
```
DATABASE_DSN=odbc://Driver=postgresql;Server=postgres;Port=5432;Database=postgres;UID=postgres;PWD=postgres
```

> [!WARNING]
> **The system must have the appropriate ODBC driver manager and the database-specific ODBC driver installed and configured.**

The default pool parameters are:
- `minsize`: 0
- `maxsize`: 5
- `timeout`: 10
- `max_inactive_connection_lifetime`: 120

For more information about ODBC configuration, check the [pyodbc documentation](https://github.com/mkleehammer/pyodbc/wiki).
