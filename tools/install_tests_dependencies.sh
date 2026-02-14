plugins=$(get_plugins_list tests)

if ! [ "x$plugins" = "x" ]; then
    poetry install --only dev,$plugins
else
    poetry install --only dev
fi
