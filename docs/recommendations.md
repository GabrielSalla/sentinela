# Recommendations
## Deployment
Avoid unnecessarily complex deployments. Scale the architecture only when required.

Recommended progression:
1. **Start with a single container/pod** running both the controller and executor. A single instance can handle a large number of monitors concurrently, and only a persistent PostgreSQL database is required.
2. **Tune the configuration** before scaling out. If the single instance starts reaching its limits, adjust the configuration parameters. The optimal settings depend on the workload (for example, many lightweight monitors versus a few resource-intensive ones).
3. **Separate the controller and executors** only when additional scalability is needed. This enables horizontal scaling but also requires an external queue.

## Credentials
For production deployments, it is recommended to separate database credentials into three distinct scopes:
- **Runtime credentials**: Grant read and write access to all tables except `Monitors` and `CodeModules`, which should be read-only. This prevents the running application from modifying monitors at runtime. It is also recommended to disable monitor registration through the API to avoid unexpected erros.
- **CI – Validation**: Add a CI step that validates monitors before they are registered. This step should **not** have any database credentials, preventing malicious or untrusted code from accessing the production database during validation.
- **CI – Registration**: After validation and code review, execute the monitor registration step. The credentials used in this stage should have read and write access only to the `Monitors` and `CodeModules` tables.

This separation ensures that monitors can only be modified through the CI/CD pipeline and are subject to your review and approval process.
