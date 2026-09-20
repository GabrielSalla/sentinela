import importlib
import os

import pytest

import plugins.ntfy.ntfy as ntfy


@pytest.fixture(scope="module")
def tokens_setup(monkeypatch_module):
    monkeypatch_module.setattr(ntfy, "tokens", {})


def test_ntfy_loads_and_clears_tokens(monkeypatch, tokens_setup):
    """'ntfy' should load 'NTFY_TOKEN_*' env vars into 'tokens' and clear them"""
    assert ntfy.tokens == {}

    monkeypatch.setenv("NTFY_TOKEN_MYAPP", "tk_123")
    monkeypatch.setenv("NTFY_TOKEN_OTHER", "tk_456")
    monkeypatch.setenv("NTFY_SERVER_URL", "keep")

    reloaded = importlib.reload(ntfy)

    assert reloaded.tokens == {"myapp": "tk_123", "other": "tk_456"}
    assert "NTFY_TOKEN_MYAPP" not in os.environ
    assert "NTFY_TOKEN_OTHER" not in os.environ
    assert os.environ["NTFY_SERVER_URL"] == "keep"
