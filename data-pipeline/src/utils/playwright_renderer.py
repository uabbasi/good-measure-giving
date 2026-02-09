"""
Playwright-based JavaScript renderer for SPA pages.

Used as a fallback when static HTML scraping returns empty content.
Manages browser lifecycle for efficiency (single browser per session).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PlaywrightRenderer:
    """
    Renders JavaScript-heavy pages using Playwright.

    Uses a single browser instance per session for efficiency.
    Falls back gracefully if Playwright is not installed or fails.
    """

    def __init__(self, headless: bool = True, timeout_ms: int = 15000):
        """
        Initialize the renderer.

        Args:
            headless: Run browser in headless mode (default True)
            timeout_ms: Page load timeout in milliseconds (default 15s)
        """
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._playwright = None
        self._browser = None
        self._context = None
        self._initialized = False
        self._available = None  # None = not checked, True/False = checked

    def _ensure_initialized(self) -> bool:
        """
        Lazily initialize Playwright and browser.

        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return self._available

        if self._available is False:
            return False

        try:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            self._context = self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720},
            )
            self._initialized = True
            self._available = True
            logger.info("Playwright browser initialized for JS rendering")
            return True

        except ImportError:
            logger.warning("Playwright not installed. Run: uv pip install playwright && playwright install chromium")
            self._available = False
            return False
        except Exception as e:
            logger.warning(f"Failed to initialize Playwright: {e}. Run: playwright install chromium")
            self._available = False
            return False

    def render(self, url: str) -> Optional[str]:
        """
        Render a page with JavaScript and return the HTML.

        Args:
            url: URL to render

        Returns:
            Rendered HTML content, or None if rendering failed
        """
        if not self._ensure_initialized():
            return None

        try:
            page = self._context.new_page()
            try:
                # Navigate and wait for network to settle
                page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)

                # Get the rendered HTML
                html = page.content()

                logger.debug(f"Playwright rendered {url}: {len(html)} chars")
                return html

            finally:
                page.close()

        except Exception as e:
            logger.warning(f"Playwright render failed for {url}: {e}")
            return None

    def close(self):
        """Close the browser and cleanup resources."""
        if self._context:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None

        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        self._initialized = False
        logger.debug("Playwright browser closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        self.close()
        return False

    def __del__(self):
        """Destructor - ensure cleanup."""
        self.close()
