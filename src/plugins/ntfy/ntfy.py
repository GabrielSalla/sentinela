import os

tokens: dict[str, str] = {}

for env_var, token in list(os.environ.items()):
    if env_var.startswith("NTFY_TOKEN_"):
        tokens[env_var.removeprefix("NTFY_TOKEN_")] = token
        # Clear the environment variable
        del os.environ[env_var]
