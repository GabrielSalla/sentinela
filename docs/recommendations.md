# Recommendations
## Deployment
Avoid unnecessarily complex deployments. Scale the architecture only when required.

Recommended progression:
1. **Start with a single container/pod** running both the controller and executor. A single instance can handle a large number of monitors concurrently, and only a persistent PostgreSQL database is required.
2. **Tune the configuration** before scaling out. If the single instance starts reaching its limits, adjust the configuration parameters. The optimal settings depend on the workload (for example, many lightweight monitors versus a few resource-intensive ones).
3. **Separate the controller and executors** only when additional scalability is needed. This enables horizontal scaling but also requires an external queue.

## Credentials
For production deployments, it is recommended to separate database credentials into three distinct scopes:
- **Runtime credentials**: To prevent the running application from modifying monitors code at runtime it's recommended to:
  - Grant `select`, `insert` and `update` permissions to all tables except `Monitors` and `CodeModules`.
  - Grant `select` and `update` permissions to the `Monitors` table.
  - Grant `select` permission to the `CodeModules` table.
  - Disable monitor registration through the API to avoid unexpected erros.
- **CI – Validation**: Add a CI step that validates monitors before they are registered. This step should **not** have any database credentials, preventing malicious or untrusted code from accessing the production database during validation.
- **CI – Registration**: After validation and code review, execute the monitor registration step. The credentials used in this stage should have `select`, `insert` and `update` permissions to the `Monitors` and `CodeModules` tables only.

This separation ensures that monitors can only be modified through the CI/CD pipeline and are subject to your review and approval process.
