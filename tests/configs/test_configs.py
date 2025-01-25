import configs.configs_loader as configs_loader


def test_configs_logging_friendly(monkeypatch):
    """'Configs' should be compatible with 'friendly' logs"""
    monkeypatch.setitem(
        configs_loader.loaded_configs, "logging", {"mode": "friendly", "format": "%(message)s"}
    )
    assert configs_loader.Configs(**configs_loader.loaded_configs) is not None


def test_configs_logging_json(monkeypatch):
    """'Configs' should be compatible with 'JSON' logs"""
    monkeypatch.setitem(
        configs_loader.loaded_configs,
        "logging",
        {
            "mode": "json",
            "fields": {
                "timestamp": "created",
                "level": "levelname",
                "file_path": "pathname",
                "logger_name": "name",
                "function_name": "funcName",
                "line_number": "lineno",
                "message": "message",
            },
        },
    )
    assert configs_loader.Configs(**configs_loader.loaded_configs) is not None


def test_configs_queue_internal(monkeypatch):
    """'Configs' should be compatible with 'internal' queue"""
    monkeypatch.setitem(configs_loader.loaded_configs, "queue", {"type": "internal"})
    assert configs_loader.Configs(**configs_loader.loaded_configs) is not None


def test_configs_queue_sqs(monkeypatch):
    """'Configs' should be compatible with 'SQS' queue"""
    monkeypatch.setitem(
        configs_loader.loaded_configs,
        "queue",
        {
            "type": "sqs",
            "name": "test",
            "url": "http://localhost",
            "region": "us-west-1",
            "create_queue": False,
        },
    )
    assert configs_loader.Configs(**configs_loader.loaded_configs) is not None
