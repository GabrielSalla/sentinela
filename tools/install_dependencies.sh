poetry install --only main

plugins=$(get_plugins_list)

if ! [ "x$plugins" = "x" ]; then
    poetry install --only $(echo "$plugins" | tr ' ' ',')
fi

# Install the dependencies for the plugins
for plugin in $plugins; do
    plugin_name="${plugin#plugin-}"
    setup_script_path="src/plugins/$plugin_name/setup.sh"
    if [ -f "$setup_script_path" ]; then
        echo "Running $setup_script_path"
        sh $setup_script_path
    else
        echo "No setup script found for plugin '$plugin' at $setup_script_path"
    fi
done
