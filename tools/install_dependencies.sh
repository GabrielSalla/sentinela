poetry install --only main

plugins=$(get_plugins_list)

if ! [ "x$plugins" = "x" ]; then
    poetry install --only $plugins
fi
