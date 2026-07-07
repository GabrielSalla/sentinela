# Command line interface
Execute Sentinela commands through a CLI.

Operations:
- `run`: Execute Sentinela as a controller, executor or both.
- `validate`: Validate a monitor.
- `register`: Register a monitor.

All commands have instructions when executed with `-h` or `--help`.
```bash
sentinela -h
```

## Run
Start sentinela in with only controller, executor or both.

```bash
sentinela run [{controller,executor} ...]
```

Arguments:
- `modes`: List of modes to run. If none are provided, both the controller and executor will run.

Examples:
```bash
sentinela run controller  # Start Sentinela with only the controller
sentinela run executor  # Start Sentinela with only the executor
sentinela run controller executor  # Start Sentinela with both the controller and executor
sentinela run  # Start Sentinela with both the controller and executor
```

## Validate monitor
Validate a monitor without using the API.

```bash
sentinela validate monitor_file
```

Arguments:
- `monitor_file`: Path to the monitor .py code file.

Example:
```bash
sentinela validate monitors/my_monitor/my_monitor.py
```


## Register monitor
Register a monitor without using the API. This is the only way to register a monitor when the HTTP route to register a monitor is disabled.

```bash
sentinela register monitor_name monitor_file [additional_files ...]
```

Arguments:
- `monitor_name`: The monitor name to be registered.
- `monitor_file`: Path to the monitor .py code file.
- `additional_files`: Optional. List of paths of additional files of the monitor.

Examples:
```bash
sentinela register my_monitor monitors/my_monitor/my_monitor.py
sentinela register other_monitor monitors/other_monitor/other_monitor.py monitors/other_monitor/my_query.sql
```
