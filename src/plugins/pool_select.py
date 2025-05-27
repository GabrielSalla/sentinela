import logging
from typing import cast

import plugins
from databases.protocols import Pool

_logger = logging.getLogger("pool_select")


def get_plugin_pool(pool_type: str) -> type[Pool] | None:
    for plugin_name, plugin in plugins.loaded_plugins.items():
        plugin_pools = getattr(plugin, "pools", None)

        if plugin_pools is None:
            continue

        for pool_class_name in plugin_pools.__all__:
            pool_class = getattr(plugin_pools, pool_class_name, None)

            if pool_class is None:
                _logger.error(f"Plugin '{plugin_name}' pool '{pool_class_name}' class not found")
                continue

            if pool_type not in pool_class.PATTERNS:
                continue

            if not isinstance(pool_class, Pool):
                _logger.error(
                    f"Plugin '{plugin_name}' pool '{pool_class.__name__}' accepts the type "
                    f"'{pool_type}' but has invalid interface"
                )
                continue

            _logger.info(f"Using plugin '{plugin_name}' for pool with pattern '{pool_type}'")
            return cast(type[Pool], pool_class)

    _logger.error(f"Unable to find pool for pattern '{pool_type}'")
    return None
