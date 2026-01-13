"""curl_cffi-based fetcher for Weibo search API.

Uses curl_cffi instead of DrissionPage SessionPage for proper HTTPS proxy support
and browser-matching TLS fingerprints.
"""

from typing import Any, Optional
from urllib.parse import quote

from curl_cffi import requests as curl_requests

from weibo_search.config import get_logger, get_settings
from weibo_search.models import CookieBundle
from weibo_search.workers.cookie.stealth import UA_ANDROID_131

logger = get_logger("search")


class CurlCffiFetcher:
    """Fetch Weibo search results using curl_cffi.
    
    Features:
    - Proper HTTPS proxy support (unlike requests.Session)
    - Browser-matching TLS/JA3 fingerprint via impersonate
    - Full cookie loading from CookieBundle
    - New session per search() call for IP rotation
    """

    SEARCH_API_URL = "https://m.weibo.cn/api/container/getIndex"

    def __init__(self, cookie_bundle: CookieBundle):
        """Initialize fetcher with a cookie bundle.
        
        Args:
            cookie_bundle: CookieBundle with cookies from browser session
        """
        self.bundle = cookie_bundle
        self.settings = get_settings()
        self._session = None

    def search(self, keyword: str, page: int = 1) -> Optional[dict[str, Any]]:
        """Search for a keyword.
        
        Reuses the session to maintain connection/IP across pages.
        
        Args:
            keyword: Search keyword
            page: Page number (1-indexed)
            
        Returns:
            Raw API response dict, or None on failure
        """
        # Build container ID with search params
        container_id = f"100103type=1&q={quote(keyword)}"
        
        # Build request parameters
        params = {
            "containerid": container_id,
            "page_type": "searchall",
            "page": str(page),
        }
        
        logger.debug(f"Searching: {keyword} (page={page})")
        
        try:
            session = self._get_or_create_session()
            response = session.get(self.SEARCH_API_URL, params=params)
            
            if response.status_code != 200:
                logger.error(f"API returned status {response.status_code}")
                return None
            
            try:
                data = response.json()
            except Exception as e:
                logger.error(f"Failed to parse JSON: {e}")
                return None
            
            if not isinstance(data, dict):
                logger.error(f"Invalid response type: {type(data)}")
                return None
            
            # Check response status
            ok = data.get("ok")
            if ok != 1:
                logger.warning(f"API returned ok={ok} for {keyword}")
                if ok == -100:
                    logger.error("Cookie likely invalid (ok:-100)")
            
            return data
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return None

    def _get_or_create_session(self):
        """Get or create the curl_cffi session."""
        if self._session:
            return self._session

        # Convert cookies to header string directly
        cookie_header = self._build_cookie_header()
        
        # Build headers
        headers = {
            "User-Agent": UA_ANDROID_131,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://m.weibo.cn/",
            "Cookie": cookie_header,
            # Client Hints to match UA_ANDROID_131 (Pixel 7 / Android 14)
            "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?1",
            "Sec-Ch-Ua-Platform": '"Android"',
        }
        
        proxy_url = self.settings.proxy_url
        if proxy_url and "localhost" in proxy_url:
            # Force IPv4 to avoid macOS IPv6/DNS issues with curl
            proxy_url = proxy_url.replace("localhost", "127.0.0.1")
        
        logger.debug(f"Creating session with proxy: {proxy_url}")

        self._session = curl_requests.Session(
            proxy=proxy_url,
            impersonate="chrome_android",
            headers=headers,
            timeout=self.settings.browser_timeout,
        )
        return self._session

    def _build_cookie_header(self) -> str:
        """Build Cookie header string from CookieBundle.
        
        Returns:
            Cookie header string (k=v; k2=v2)
        """
        cookies = {}
        
        # Load all cookies from bundle
        for cookie in self.bundle.cookies:
            name = cookie.get("name")
            value = cookie.get("value")
            if name and value:
                cookies[name] = value
        
        # Ensure SUB and SUBP are always present (overwrite if exists)
        cookies["SUB"] = self.bundle.sub
        if self.bundle.subp:
            cookies["SUBP"] = self.bundle.subp
            
        # Join into header string
        return "; ".join([f"{k}={v}" for k, v in cookies.items()])

    def close(self) -> None:
        """Close the session."""
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

# Alias for backward compatibility with jobs.py
SessionFetcher = CurlCffiFetcher
