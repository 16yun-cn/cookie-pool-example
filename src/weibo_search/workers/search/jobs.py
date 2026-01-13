"""RQ job functions for search."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from weibo_search.config import get_logger, get_settings
from weibo_search.models import KeywordTask
from weibo_search.storage.log_writer import get_search_log
from weibo_search.storage.redis_client import CookieStore, SearchResultStore
from weibo_search.workers.cookie.jobs import ensure_cookie_pool
from weibo_search.workers.search.parser import parse_search_response
from weibo_search.workers.search.session_fetcher import SessionFetcher

logger = get_logger("search")


def _refresh_cookie_pool(store: CookieStore, settings) -> Optional["CookieBundle"]:
    """Attempt to refresh the cookie pool and return a valid bundle."""
    logger.warning("No valid cookies, attempting to refresh pool")
    ensure_cookie_pool(min_size=1, headless=settings.browser_headless)
    return store.get_valid()


def search_keyword_job(
    keyword: str,
    page: int = 1,
    max_pages: Optional[int] = None,
) -> dict[str, Any]:
    """RQ job to search a keyword.
    
    This job:
    1. Gets a valid cookie from the pool
    2. Creates a SessionFetcher with the cookie
    3. Searches the keyword (optionally multiple pages)
    4. Parses and stores results
    5. Logs the results
    
    Args:
        keyword: Search keyword
        page: Starting page number
        max_pages: Maximum pages to fetch (default from settings)
        
    Returns:
        Dict with success status, results summary
    """
    settings = get_settings()
    search_log = get_search_log()
    
    if max_pages is None:
        max_pages = settings.max_pages
    
    # Get a valid cookie (auto-refresh if empty)
    store = CookieStore()
    bundle = store.get_valid()
    
    if bundle is None:
        bundle = _refresh_cookie_pool(store, settings)
        if bundle is None:
            error = "No valid cookies in pool (refresh failed)"
            logger.error(error)
            search_log.write_search(
                keyword=keyword,
                page=page,
                posts_count=0,
                cookie_id="",
                success=False,
                error=error,
            )
            return {"success": False, "error": error, "needs_cookie": True}
    
    logger.info(f"Searching '{keyword}' with cookie {bundle.id} (max_pages={max_pages})")
    start_time = datetime.now()
    
    # Create fetcher
    fetcher = SessionFetcher(bundle)
    result_store = SearchResultStore()
    
    total_posts = 0
    pages_fetched = 0
    errors = []
    refresh_attempts = 0
    
    try:
        current_page = page
        
        while current_page <= max_pages:
            logger.debug(f"Fetching page {current_page}")
            
            # Search with retries for network errors
            raw_response = None
            network_retries = 0
            
            while network_retries <= settings.max_retries:
                raw_response = fetcher.search(keyword, current_page)
                
                if raw_response is not None:
                    break
                
                # Network failure (Timeout etc)
                network_retries += 1
                if network_retries <= settings.max_retries:
                    logger.warning(f"Page {current_page}: Network error (likely timeout), resetting session and retrying ({network_retries}/{settings.max_retries})")
                    fetcher.close() # Force new session/connection on retry
                    time.sleep(2)
            
            if raw_response is None:
                errors.append(f"Page {current_page}: No response after {settings.max_retries} retries")
                break
            
            # Check for invalid cookie
            if raw_response.get("ok") == -100:
                logger.warning(f"Cookie {bundle.id} is invalid (ok:-100)")
                store.mark_invalid(bundle.id)
                errors.append(f"Cookie invalid at page {current_page}")
                refresh_attempts += 1

                if refresh_attempts > settings.max_retries:
                    logger.error("Exceeded cookie refresh retries")
                    break

                # Refresh cookie and retry same page
                new_bundle = _refresh_cookie_pool(store, settings)
                if new_bundle is None:
                    errors.append("Cookie refresh failed")
                    break

                # Swap to new bundle + fetcher
                bundle = new_bundle
                fetcher.close()
                fetcher = SessionFetcher(bundle)
                continue
            
            # Parse results
            result = parse_search_response(
                keyword=keyword,
                page=current_page,
                raw_response=raw_response,
                cookie_bundle_id=bundle.id,
            )
            
            # Store results
            result_data = result.model_dump(mode="json")
            result_store.save(keyword, current_page, result_data)
            
            posts_count = len(result.posts)
            total_posts += posts_count
            pages_fetched += 1
            
            logger.info(f"Page {current_page}: {posts_count} posts")
            
            # Log this page
            search_log.write_search(
                keyword=keyword,
                page=current_page,
                posts_count=posts_count,
                cookie_id=bundle.id,
                success=True,
            )
            
            # Save full result for debugging/replay
            search_log.write_search_result(
                keyword=keyword,
                page=current_page,
                data=raw_response,
                cookie_id=bundle.id,
            )
            
            # Check if there are more results
            if posts_count == 0:
                logger.debug("No more results")
                break
            
            current_page += 1
            refresh_attempts = 0
            
            # Delay between requests
            if current_page <= max_pages:
                time.sleep(settings.search_delay)
        
        success = pages_fetched > 0
        return {
            "success": success,
            "keyword": keyword,
            "pages_fetched": pages_fetched,
            "total_posts": total_posts,
            "cookie_id": bundle.id,
            "errors": errors if errors else None,
        }
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Search finished: {keyword} - "
            f"{total_posts} posts in {pages_fetched} pages "
            f"(duration={duration:.2f}s, success={success})"
        )
        
        return {
            "success": success,
            "keyword": keyword,
            "pages_fetched": pages_fetched,
            "total_posts": total_posts,
            "cookie_id": bundle.id,
            "duration_seconds": duration,
            "errors": errors if errors else None,
        }
        
    except Exception as e:
        error = str(e)
        logger.exception(f"Search error: {error}")
        search_log.write_search(
            keyword=keyword,
            page=page,
            posts_count=0,
            cookie_id=bundle.id,
            success=False,
            error=error,
        )
        return {"success": False, "error": error}
        
    finally:
        fetcher.close()


def search_keywords_from_jsonl(
    jsonl_path: str,
    max_pages: Optional[int] = None,
) -> dict[str, Any]:
    """Search all keywords from a JSONL file.
    
    Args:
        jsonl_path: Path to keywords.jsonl file
        max_pages: Maximum pages per keyword
        
    Returns:
        Summary of all searches
    """
    path = Path(jsonl_path)
    if not path.exists():
        return {"success": False, "error": f"File not found: {jsonl_path}"}
    
    keywords = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                task = KeywordTask(**data)
                keywords.append(task)
            except Exception as e:
                logger.warning(f"Failed to parse line: {e}")
    
    if not keywords:
        return {"success": False, "error": "No keywords found"}
    
    # Sort by priority
    keywords.sort(key=lambda k: k.priority)
    
    logger.info(f"Loaded {len(keywords)} keywords from {jsonl_path}")
    
    results = []
    success_count = 0
    
    for task in keywords:
        logger.info(f"Processing keyword: {task.keyword} (priority={task.priority})")
        result = search_keyword_job(task.keyword, max_pages=max_pages)
        results.append({
            "keyword": task.keyword,
            "category": task.category,
            "result": result,
        })
        if result.get("success"):
            success_count += 1
    
    return {
        "success": success_count > 0,
        "total_keywords": len(keywords),
        "success_count": success_count,
        "results": results,
    }
