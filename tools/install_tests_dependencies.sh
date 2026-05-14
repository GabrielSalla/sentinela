plugins=$(get_plugins_list tests)

if ! [ "x$plugins" = "x" ]; then
    poetry install --only dev,$(echo "$plugins" | tr ' ' ',')
else
    poetry install --only dev
fi
