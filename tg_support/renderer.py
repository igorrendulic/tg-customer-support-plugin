from __future__ import annotations


class RenderError(RuntimeError):
    pass


class PlaywrightRenderer:
    def render(self, url: str) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RenderError("Playwright rendering requested but playwright is not installed.") from exc

        with sync_playwright() as p:  # pragma: no cover - browser integration
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            html = page.content()
            browser.close()
            return html
