import logging
from api.utils.redis_utils import redis_client

logger = logging.getLogger("cache_utils")


def clear_browse_cache() -> int:
    """
    Clears ALL Redis cache keys prefixed with cache:browse:*
    Use after bulk imports or when a full refresh is needed.
    """
    try:
        keys = redis_client.keys("cache:browse:*")
        if keys:
            count = redis_client.delete(*keys)
            logger.info(f"[cache] Bulk clear: removed {count} browse cache keys.")
            return count
        return 0
    except Exception as e:
        logger.error(f"[cache] Error during bulk clear: {e}")
        return 0


def invalidate_vendor(vendor_id: int) -> None:
    """
    Called whenever a Vendor is created, updated, or status-changed.
    Removes:
      - the specific vendor detail key
      - all vendor list keys (since counts/ordering may have changed)
      - the category aggregate key (vendor_count may change)
    """
    try:
        keys_to_delete: list[str] = []

        # Specific vendor detail
        keys_to_delete.append(f"cache:browse:vendors:detail:{vendor_id}")

        # All vendor list keys (any combination of filters)
        list_keys = redis_client.keys("cache:browse:vendors:list:*")
        keys_to_delete.extend(list_keys)

        # Category aggregate (vendor_count numbers change)
        keys_to_delete.append("cache:browse:categories")

        if keys_to_delete:
            redis_client.delete(*keys_to_delete)
            logger.info(
                f"[cache] Invalidated vendor #{vendor_id}: "
                f"{len(keys_to_delete)} keys removed."
            )
    except Exception as e:
        logger.error(f"[cache] Failed to invalidate vendor #{vendor_id}: {e}")


def invalidate_product(product_id: int, vendor_id: int | None = None) -> None:
    """
    Called whenever a Product is created, updated, or deleted.
    Removes:
      - the specific product detail key
      - all product list keys (search results and group lists are stale)
      - if vendor_id given, the vendor's detail key (product list embedded in it)
    """
    try:
        keys_to_delete: list[str] = []

        # Specific product detail
        keys_to_delete.append(f"cache:browse:products:detail:{product_id}")

        # All product list keys
        list_keys = redis_client.keys("cache:browse:products:list:*")
        keys_to_delete.extend(list_keys)

        # Vendor detail embeds all products — must be re-fetched
        if vendor_id is not None:
            keys_to_delete.append(f"cache:browse:vendors:detail:{vendor_id}")

        if keys_to_delete:
            redis_client.delete(*keys_to_delete)
            logger.info(
                f"[cache] Invalidated product #{product_id}: "
                f"{len(keys_to_delete)} keys removed."
            )
    except Exception as e:
        logger.error(f"[cache] Failed to invalidate product #{product_id}: {e}")
