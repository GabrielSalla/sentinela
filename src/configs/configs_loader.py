import os
from typing import Any, Literal

import yaml
from pydantic.dataclasses import dataclass
from pydantic.fields import Field


@dataclass
class InternalMonitorsNotificationConfig:
    enabled: bool
    notification_class: str
    params: dict[str, Any] = Field(default_factory=dict)


@dataclass
class FriendlyLogConfig:
    mode: Literal["friendly"]
    format: str | None = None


@dataclass
class JsonLogConfig:
    mode: Literal["json"]
    fields: dict[str, str] | None = None


@dataclass
class ApplicationDatabaseConfig:
    pool_size: int


@dataclass
class HttpServerConfig:
    port: int
    log_level: Literal["default", "warning", "error", "none"] = "default"
    dashboard_enabled: bool = False


@dataclass
class ControllerProcedureConfig:
    schedule: str
    params: dict[str, str | int | float | bool | None] | None = None


@dataclass
class Configs:
    plugins: list[str]

    load_sample_monitors: bool
    sample_monitors_path: str
    internal_monitors_path: str
    internal_monitors_notification: InternalMonitorsNotificationConfig

    monitors_load_schedule: str

    application_database_settings: ApplicationDatabaseConfig

    application_queue: dict[str, Any]

    http_server: HttpServerConfig

    time_zone: str

    controller_process_schedule: str
    controller_concurrency: int
    controller_procedures: dict[str, ControllerProcedureConfig]

    executor_concurrency: int
    executor_sleep: int
    executor_monitor_timeout: int
    executor_reaction_timeout: int
    executor_request_timeout: int
    executor_monitor_heartbeat_time: int

    max_issues_creation: int

    database_default_acquire_timeout: int
    database_default_query_timeout: int
    database_close_timeout: int
    database_log_query_metrics: bool

    databases_pools_configs: dict[str, dict[str, Any]]

    log_all_events: bool

    logging: FriendlyLogConfig | JsonLogConfig = Field(discriminator="mode")


with open(os.environ.get("CONFIGS_FILE", "configs.yaml"), "r") as file:
    loaded_configs = yaml.load(file.read(), Loader=yaml.FullLoader)

configs = Configs(**loaded_configs)
