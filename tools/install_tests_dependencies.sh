plugins=$(python ./tools/get_plugins_list.py tests)

poetry install --only dev
if ! [ "x$plugins" = "x" ]; then
    poetry install --only $plugins
fi
