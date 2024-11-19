import os
from dataclasses import dataclass
from typing import Any

import yaml
from dataclass_type_validator import dataclass_validate


@dataclass_validate(strict=True)
@dataclass
class Configs:
    load_sample_monitors: bool
    sample_monitors_path: str
    internal_monitors_path: str
    monitors_load_schedule: str

    logging: dict[str, Any]

    application_database_settings: dict[str, Any]

    application_queue: dict[str, Any]
    queue_wait_message_time: int
    queue_visibility_time: int

    http_server: dict[str, Any]

    time_zone: str

    controller_process_schedule: str
    controller_concurrency: int
    slack_websocket_enabled: bool

    executor_concurrency: int
    executor_sleep: int
    executor_monitor_timeout: int
    executor_reaction_timeout: int
    executor_request_timeout: int

    max_issues_creation: int

    database_default_acquire_timeout: int
    database_default_query_timeout: int
    database_close_timeout: int
    database_log_query_metrics: bool

    databases_pools_configs: dict[str, dict[str, Any]]

    log_all_events: bool

    notifications_issue_show_limit: int


with open(os.environ.get("CONFIGS_FILE", "configs.yaml"), "r") as file:
    loaded_configs = yaml.load(file.read(), Loader=yaml.FullLoader)

configs = Configs(**loaded_configs)
