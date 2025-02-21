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
