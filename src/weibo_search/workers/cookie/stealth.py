"""Stealth JavaScript injection utilities for anti-detection."""

# User-Agent for Android Mobile (Chrome 131)
UA_ANDROID_131 = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.6778.73 Mobile Safari/537.36"
)

# Stealth JavaScript to inject before page load
# This masks automation detection vectors
STEALTH_JS = f"""
// Override navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});

// Set realistic languages
Object.defineProperty(navigator, 'languages', {{get: () => ['zh-CN', 'zh', 'en-US', 'en']}});

// Fake plugins array (mobile browsers have some)
Object.defineProperty(navigator, 'plugins', {{get: () => [1, 2, 3, 4, 5]}});

// Set mobile platform
Object.defineProperty(navigator, 'platform', {{get: () => 'Linux armv8l'}});

// Override User-Agent (backup if CDP fails)
Object.defineProperty(navigator, 'userAgent', {{get: () => '{UA_ANDROID_131}'}});

// Ensure window.chrome exists
if (!window.chrome) {{ window.chrome = {{runtime: {{}}}}; }}

// Fake userAgentData for Client Hints
const __uaData = {{
  brands: [
    {{brand: "Chromium", version: "131"}},
    {{brand: "Google Chrome", version: "131"}},
    {{brand: "Not;A=Brand", version: "99"}}
  ],
  mobile: true,
  platform: "Android",
  getHighEntropyValues: async (hints) => {{
    return {{
      brands: __uaData.brands,
      mobile: true,
      platform: "Android",
      platformVersion: "14.0.0",
      architecture: "arm",
      model: "Pixel 7",
      uaFullVersion: "131.0.6778.73",
      fullVersionList: __uaData.brands.map(b => ({{brand: b.brand, version: b.version}})),
    }};
  }}
}};

try {{
  Object.defineProperty(navigator, 'userAgentData', {{get: () => __uaData}});
}} catch (e) {{}}
"""


def apply_stealth(page) -> None:
    """Apply stealth scripts to a DrissionPage ChromiumPage.
    
    This injects JavaScript to mask automation detection vectors and
    uses CDP to override User-Agent at the protocol level.
    
    Args:
        page: DrissionPage ChromiumPage instance
    """
    # Inject stealth script to run on every new document
    try:
        page.run_cdp("Page.addScriptToEvaluateOnNewDocument", source=STEALTH_JS)
    except Exception:
        pass
    
    # Override User-Agent via CDP (more reliable than JS)
    try:
        page.run_cdp(
            "Emulation.setUserAgentOverride",
            userAgent=UA_ANDROID_131,
            acceptLanguage="zh-CN,zh",
            platform="Android",
        )
    except Exception:
        pass


def get_navigator_info(page) -> dict:
    """Get navigator info for debugging.
    
    Args:
        page: DrissionPage ChromiumPage instance
        
    Returns:
        Dictionary with navigator properties
    """
    probes = {
        "userAgent": "navigator.userAgent",
        "platform": "navigator.platform",
        "language": "navigator.language",
        "languages": "navigator.languages",
        "webdriver": "navigator.webdriver",
        "plugins_len": "navigator.plugins.length",
        "hardwareConcurrency": "navigator.hardwareConcurrency",
        "deviceMemory": "navigator.deviceMemory",
    }
    
    result = {}
    for key, expr in probes.items():
        try:
            value = page.run_js(expr, as_expr=True)
            result[key] = value
        except Exception as e:
            result[key] = f"<error: {e}>"
    
    return result
