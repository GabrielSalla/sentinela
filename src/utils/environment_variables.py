import os


def clean() -> None:
    for env_var_name in os.environ.keys():
        if not env_var_name.startswith("DATABASE_"):
            continue

        del os.environ[env_var_name]
