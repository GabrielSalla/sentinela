pip install poetry --no-cache-dir
poetry install --only main

plugins=$(python ./tools/get_plugins_list.py)

if ! [ "x$plugins" = "x" ]; then
    poetry install --only $plugins
fi
