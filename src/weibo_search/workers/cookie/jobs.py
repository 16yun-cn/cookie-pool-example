"""RQ job functions for cookie generation."""

from typing import Any

from weibo_search.config import get_logger
from weibo_search.storage.log_writer import get_cookie_log
from weibo_search.storage.redis_client import CookieStore
from weibo_search.workers.cookie.browser import BrowserCookieProvider

logger = get_logger("cookie")


def generate_cookie_job(headless: bool = True, keyword: str = "测试") -> dict[str, Any]:
    """RQ job to generate a cookie bundle.
    
    This job:
    1. Creates a BrowserCookieProvider (headless or headful)
    2. Visits Weibo to get SUB cookie
    3. Stores the cookie bundle in Redis
    4. Logs the result
    
    Args:
        headless: Whether to run browser in headless mode
        keyword: Keyword to search (triggers cookie flow)
        
    Returns:
        Dict with success status, cookie_id if successful, error if failed
    """
    cookie_log = get_cookie_log()
    provider = BrowserCookieProvider(headless=headless)
    
    try:
        logger.info(f"Starting cookie generation (headless={headless})")
        
        bundle = provider.generate_cookie(keyword=keyword)
        
        if bundle is None:
            error = "Failed to generate cookie bundle"
            logger.error(error)
            cookie_log.write_cookie(
                bundle_id="",
                success=False,
                error=error,
            )
            return {"success": False, "error": error}
        
        # Store in Redis
        store = CookieStore()
        store.save(bundle)
        
        logger.info(f"Cookie saved: {bundle.id} (pool size: {store.pool_size()})")
        cookie_log.write_cookie(
            bundle_id=bundle.id,
            success=True,
            full_data=bundle.model_dump(mode="json"),
        )
        
        return {
            "success": True,
            "cookie_id": bundle.id,
            "pool_size": store.pool_size(),
        }
        
    except Exception as e:
        error = str(e)
        logger.exception(f"Cookie generation error: {error}")
        cookie_log.write_cookie(
            bundle_id="",
            success=False,
            error=error,
        )
        return {"success": False, "error": error}
        
    finally:
        provider.cleanup()


def ensure_cookie_pool(min_size: int = 1, headless: bool = True) -> dict[str, Any]:
    """Ensure cookie pool has at least min_size cookies.
    
    Args:
        min_size: Minimum pool size
        headless: Whether to run browser in headless mode
        
    Returns:
        Dict with current pool size and any cookies generated
    """
    store = CookieStore()
    # Clear expired cookies so pool size reflects actual usable cookies
    store.clear_expired()

    # If no valid cookies remain, treat pool as empty
    valid_bundle = store.get_valid()
    current_size = store.pool_size() if valid_bundle else 0
    
    if current_size >= min_size:
        logger.info(f"Cookie pool already has {current_size} cookies (min={min_size})")
        return {"success": True, "pool_size": current_size, "generated": 0}
    
    needed = min_size - current_size
    logger.info(f"Need to generate {needed} cookies (current={current_size}, min={min_size})")
    
    generated = 0
    errors = []
    
    for i in range(needed):
        result = generate_cookie_job(headless=headless)
        if result["success"]:
            generated += 1
        else:
            errors.append(result.get("error", "Unknown error"))
    
    return {
        "success": generated > 0,
        "pool_size": store.pool_size(),
        "generated": generated,
        "errors": errors if errors else None,
    }
