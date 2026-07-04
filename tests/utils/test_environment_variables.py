import os

import utils.environment_variables as environment_variables


def test_clean(monkeypatch):
    """'clean' should remove database-related environment variables while preserving others"""
    monkeypatch.setenv("DATABASE_HOST", "localhost")
    monkeypatch.setenv("DATABASE_PORT", "5432")
    monkeypatch.setenv("APP_ENV", "test")

    environment_variables.clean()

    assert "DATABASE_HOST" not in os.environ
    assert "DATABASE_PORT" not in os.environ
    assert os.environ["APP_ENV"] == "test"


def test_clean_empty(monkeypatch):
    """'clean' should handle an empty environment without raising errors"""
    monkeypatch.setattr(os, "environ", {})

    environment_variables.clean()

    assert os.environ == {}
