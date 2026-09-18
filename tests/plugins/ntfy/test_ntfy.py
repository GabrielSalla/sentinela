import importlib
import os

import plugins.ntfy.ntfy as ntfy


def test_ntfy_loads_and_clears_tokens(monkeypatch):
    """'ntfy' should load 'NTFY_TOKEN_*' env vars into 'tokens' and clear them"""
    monkeypatch.setenv("NTFY_TOKEN_MYAPP", "tk_123")
    monkeypatch.setenv("NTFY_TOKEN_OTHER", "tk_456")
    monkeypatch.setenv("NTFY_UNRELATED", "keep")

    reloaded = importlib.reload(ntfy)

    assert reloaded.tokens == {"MYAPP": "tk_123", "OTHER": "tk_456"}
    assert "NTFY_TOKEN_MYAPP" not in os.environ
    assert "NTFY_TOKEN_OTHER" not in os.environ
    assert os.environ["NTFY_UNRELATED"] == "keep"
