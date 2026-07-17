# Query Monitor
Demonstrates using the `query` function to fetch data from a database. Shows how to connect to and execute queries against configured databases.

**How it works**: The monitor executes a simple `SELECT current_timestamp;` query on the 'local' database. In `search()`, it creates a single non-solvable issue with the database timestamp. In `update()`, it refreshes the timestamp field with the latest database value. The actual query can be replaced with real data retrieval for production monitoring.
