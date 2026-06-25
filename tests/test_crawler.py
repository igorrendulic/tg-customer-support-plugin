from __future__ import annotations

from tg_support.config import SeedConfig
from tg_support.crawler import WebCrawler


class Response:
    def __init__(self, text, status=200):
        self.text = text
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError("fetch failed")


class Fetcher:
    def __init__(self, html):
        self.html = html

    def get(self, url, timeout=20):
        return Response(self.html)


class Renderer:
    def __init__(self):
        self.called = False

    def render(self, url):
        self.called = True
        return "<html><title>Rendered</title><body><main>Rendered article body with useful support documentation.</main><a href='/blog/post'>Post</a></body></html>"


def test_static_page_is_persisted(db):
    html = "<html><title>Docs</title><body><main>Password reset instructions for users.</main></body></html>"
    result = WebCrawler(db, Fetcher(html), Renderer()).crawl_seed(SeedConfig("https://example.com/docs"))
    assert result.status == "ok"
    assert result.rendered is False
    assert db.count("pages") == 1


def test_app_shell_triggers_renderer_in_auto_mode(db):
    renderer = Renderer()
    html = "<html><body><div id='root'></div><script src='/assets/app.js'></script></body></html>"
    result = WebCrawler(db, Fetcher(html), renderer).crawl_seed(SeedConfig("https://example.com/blog", render="auto"))
    assert renderer.called is True
    assert result.rendered is True
    assert "https://example.com/blog/post" in result.discovered


def test_render_never_does_not_call_renderer(db):
    renderer = Renderer()
    html = "<html><body><div id='root'></div><script src='/assets/app.js'></script></body></html>"
    WebCrawler(db, Fetcher(html), renderer).crawl_seed(SeedConfig("https://example.com/blog", render="never"))
    assert renderer.called is False
