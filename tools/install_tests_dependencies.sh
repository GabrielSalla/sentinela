plugins=$(get_plugins_list)

poetry install --only dev
if ! [ "x$plugins" = "x" ]; then
    poetry install --only $plugins
fi
