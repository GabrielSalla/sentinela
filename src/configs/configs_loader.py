import os
from typing import Any, Literal

import yaml
from pydantic.dataclasses import Field, dataclass


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
class InternalQueueConfig:
    type: Literal["internal"]


@dataclass
class SQSQueueConfig:
    type: Literal["sqs"]
    name: str
    url: str
    region: str
    create_queue: bool = False


@dataclass
class HttpServerConfig:
    port: int


@dataclass
class Configs:
    load_sample_monitors: bool
    sample_monitors_path: str
    internal_monitors_path: str
    monitors_load_schedule: str

    application_database_settings: ApplicationDatabaseConfig

    queue_wait_message_time: int
    queue_visibility_time: int

    http_server: HttpServerConfig

    time_zone: str

    controller_process_schedule: str
    controller_concurrency: int
    controller_procedures: dict[str, dict[str, Any]]

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

    logging: FriendlyLogConfig | JsonLogConfig = Field(discriminator="mode")
    application_queue: InternalQueueConfig | SQSQueueConfig = Field(discriminator="type")


with open(os.environ.get("CONFIGS_FILE", "configs.yaml"), "r") as file:
    loaded_configs = yaml.load(file.read(), Loader=yaml.FullLoader)

configs = Configs(**loaded_configs)
