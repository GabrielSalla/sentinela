# Validating a monitor
Validating a monitor is a important step before registering it. This process ensures that the monitor code is correct and can be executed by Sentinela. This is useful when using a deployment pipeline to ensure that the monitor is correctly implemented before being deployed.

## Validation Process
```
POST monitors/validate/
```

The payload should include the following fields:
- `monitor_code`: The content of the monitor’s main `.py` file content.

Example:
```json
{
    "monitor_code": "...",
}
```

## Responses
The response will contain the status of the validation process. The field `status` will be set to `monitor_validated` if the monitor was successfully validated.

Example:
```json
{
    "status": "monitor_validated",
}
```

If the validation fails, the `status` field will be set to `error` and the field `message` will contain the error message. Depending on the error, additional fields may be present to help diagnose the issue.

Example:
```json
{
    "status": "error",
    "message": "Module didn't pass check",
    "error": "Monitor has the following errors:\n  'monitor_options' is required"
}
```
