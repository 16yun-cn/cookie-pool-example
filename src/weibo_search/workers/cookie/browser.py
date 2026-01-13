"""Browser-based cookie provider using DrissionPage."""

import time
from typing import Optional
from uuid import uuid4

from weibo_search.config import get_logger, get_settings
from weibo_search.models import CookieBundle
from weibo_search.workers.cookie.stealth import UA_ANDROID_131, apply_stealth, get_navigator_info

logger = get_logger("cookie")


class BrowserCookieProvider:
    """Generate cookies by visiting Weibo with a real browser.
    
    Uses DrissionPage ChromiumPage with:
    - Proxy via --proxy-server argument (no auth needed)
    - Stealth scripts for anti-detection
    - Headless/headful mode support
    
    Note: For IP rotation, close and reopen browser between sessions.
    """

    WARMUP_URL = "https://m.weibo.cn/"
    SEARCH_URL_TEMPLATE = "https://m.weibo.cn/search?containerid=100103type=1&q={keyword}"

    def __init__(
        self,
        headless: Optional[bool] = None,
        chrome_path: Optional[str] = None,
    ):
        settings = get_settings()
        self.settings = settings
        self.headless = headless if headless is not None else settings.browser_headless
        self.chrome_path = chrome_path or settings.chrome_path
        self.timeout = settings.browser_timeout
        self.cookie_wait_timeout = settings.cookie_wait_timeout
        
        self._page = None

    def generate_cookie(self, keyword: str = "测试") -> Optional[CookieBundle]:
        """Generate a cookie bundle by visiting Weibo.
        
        Args:
            keyword: Search keyword to navigate to (triggers full cookie flow)
            
        Returns:
            CookieBundle if successful, None otherwise
        """
        # Import here to avoid import errors if DrissionPage not installed
        try:
            from DrissionPage import ChromiumOptions, ChromiumPage
        except ImportError:
            logger.error("DrissionPage is required. Install with: pip install DrissionPage")
            return None

        # Configure browser options
        co = ChromiumOptions()
        # Ensure a fresh, isolated browser instance
        co.auto_port()
        co.new_env()
        
        # Set proxy directly (no auth needed)
        proxy_url = self.settings.proxy_url
        if proxy_url:
            co.set_argument("--proxy-server", proxy_url)
            logger.debug(f"Using proxy: {proxy_url}")
        
        co.set_user_agent(UA_ANDROID_131)
        co.set_argument("--disable-blink-features=AutomationControlled")
        co.set_argument("--no-sandbox")
        co.set_argument("--disable-gpu")
        co.set_argument("--ignore-certificate-errors")
        co.set_argument("--lang=zh-CN,zh")
        
        if self.headless:
            co.set_argument("--headless=new")
        
        if self.chrome_path:
            co.set_paths(browser_path=self.chrome_path)

        logger.info(f"Starting browser (headless={self.headless})")
        
        page = None
        try:
            page = ChromiumPage(co)
            self._page = page
            
            # Apply stealth scripts
            apply_stealth(page)
            
            # Warmup: visit homepage first
            logger.debug(f"Warming up: {self.WARMUP_URL}")
            page.get(self.WARMUP_URL)
            try:
                page.wait.doc_loaded()
            except Exception:
                pass
            time.sleep(1.5)
            
            logger.debug("After warmup:")
            if logger.isEnabledFor(10):  # DEBUG level
                nav_info = get_navigator_info(page)
                logger.debug(f"Navigator: {nav_info}")
            
            # Navigate to search page
            from urllib.parse import quote
            search_url = self.SEARCH_URL_TEMPLATE.format(keyword=quote(keyword))
            logger.debug(f"Navigating to: {search_url}")
            page.get(search_url)
            
            try:
                page.wait.doc_loaded()
            except Exception:
                pass
            time.sleep(1.0)
            
            # Wait for SUB cookie
            sub_cookie = None
            subp_cookie = None
            
            for i in range(self.cookie_wait_timeout):
                cookies_dict = self._get_cookies_dict(page)
                sub_cookie = cookies_dict.get("SUB")
                subp_cookie = cookies_dict.get("SUBP")
                
                if sub_cookie:
                    logger.info(f"Got SUB cookie after {i+1}s: {sub_cookie[:20]}...")
                    break
                
                time.sleep(1)
            
            if not sub_cookie:
                logger.error("Failed to get SUB cookie")
                if logger.isEnabledFor(10):
                    self._dump_debug_info(page)
                return None
            
            # Build cookie bundle
            bundle_id = uuid4().hex[:12]
            cookies_full = self._get_cookies_full(page)
            
            bundle = CookieBundle(
                id=bundle_id,
                sub=sub_cookie,
                subp=subp_cookie,
                cookies=cookies_full,
                user_agent=UA_ANDROID_131,
                platform="Android",
                user_agent_data={
                    "brands": [
                        {"brand": "Chromium", "version": "131"},
                        {"brand": "Google Chrome", "version": "131"},
                    ],
                    "mobile": True,
                    "platform": "Android",
                },
            )
            
            logger.info(f"Generated cookie bundle: {bundle_id}")
            return bundle
            
        except Exception as e:
            logger.error(f"Browser error: {e}")
            if page and logger.isEnabledFor(10):
                self._dump_debug_info(page)
            return None
            
        finally:
            if page:
                try:
                    page.quit()
                except Exception:
                    pass
            self._page = None

    def _get_cookies_dict(self, page) -> dict:
        """Get cookies as a simple dict."""
        try:
            cookies = page.cookies(all_domains=True)
            return cookies.as_dict()
        except Exception:
            try:
                cookies = page.cookies(all_domains=True)
                return {c["name"]: c["value"] for c in cookies}
            except Exception:
                return {}

    def _get_cookies_full(self, page) -> list[dict]:
        """Get full cookie information."""
        try:
            cookies = page.cookies(all_domains=True, all_info=True)
            return list(cookies)
        except Exception:
            return []

    def _dump_debug_info(self, page) -> None:
        """Dump debug info for troubleshooting."""
        try:
            logger.debug(f"page.url: {page.url}")
        except Exception as e:
            logger.debug(f"page.url: <error {e}>")
        
        try:
            logger.debug(f"page.title: {page.title}")
        except Exception as e:
            logger.debug(f"page.title: <error {e}>")
        
        try:
            html = page.html
            logger.debug(f"page.html_len: {len(html)}")
        except Exception as e:
            logger.debug(f"page.html_len: <error {e}>")
        
        # Dump cookies
        cookies = self._get_cookies_full(page)
        logger.debug(f"cookies: {len(cookies)} total")
        for c in cookies[:10]:
            logger.debug(f"  - {c.get('name')}={c.get('value', '')[:30]}...")

    def cleanup(self) -> None:
        """Clean up resources."""
        pass  # No extension cleanup needed
