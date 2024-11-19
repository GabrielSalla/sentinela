# Registering a monitor
Once the monitor code has been created, it needs to be registered on Sentinela. The process for registering a new monitor or updating an existing one is the same.

![Registering a monitor process](./images/monitor_register.png)

## Monitor Composition
A monitor consists of:
- **Main Code File**: The `.py` file containing the monitor's definition.
- **Optional Additional Files**: Supporting resources used during the monitor's execution, such as SQL query files or other data files.

## Registration Process
To register a monitor, use the POST method with the `monitors/register/` route, providing all the required information in the request.

1. **Request URL**:
   Format the URL as `monitors/register/{monitor_name}`, where `{monitor_name}` is the name of the monitor being created or updated.
   Example: `monitors/register/my_monitor`

2. **Request Payload**:
   The payload should include the following fields:
   - `monitor_code`: The content of the monitor’s main `.py` file content.
   - `additional_files`: Optional field with an object where the keys are the names of additional files, and the values are their content.

Example:
```json
{
    "monitor_code": "...",
    "additional_files": {
        "search_query.sql": "select * from users where id = $1;"
    }
}
```

## Monitor register tool
To simplify the registration process, a Python script is available in the `tools` folder.

The following example demonstrates how to use the script to register a new monitor:

```bash
python tools/register_monitor.py \
    my_monitor \
    monitors/my_monitor/my_monitor.py \
    monitors/my_monitor/search_query.sql \
    monitors/my_monitor/update_query.sql
```

In this example:
- `my_monitor` is the name of the monitor being registered.
- `monitors/my_monitor/my_monitor.py` is the main monitor file.
- `monitors/my_monitor/search_query.sql` and `monitors/my_monitor/update_query.sql` are additional files used by the monitor.

## Monitor execution
Once registered, Sentinela will load all registered monitors during its next monitor load cycle. This cycle is determined by the `monitors_load_schedule` setting in the `configs.yaml` file.
