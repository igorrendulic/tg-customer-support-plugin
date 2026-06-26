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


class URLFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.urls = []

    def get(self, url, timeout=20):
        self.urls.append(url)
        return Response(self.pages[url])


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


def test_extract_page_ignores_non_http_links(db):
    html = """
    <html><title>Docs</title><body><main>Password reset instructions for users.</main>
    <a href="mailto:support@example.com">Email</a>
    <a href="tel:+15555550123">Call</a>
    <a href="/docs/reset">Reset</a>
    </body></html>
    """
    result = WebCrawler(db, Fetcher(html), Renderer()).crawl_seed(SeedConfig("https://example.com/docs"))

    assert result.status == "ok"
    assert result.discovered == ("https://example.com/docs/reset",)


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


def test_deep_crawl_follows_in_scope_links_to_depth(db):
    fetcher = URLFetcher(
        {
            "https://example.com/docs": "<html><title>Root</title><body><main>Root docs page with useful support content.</main><a href='/docs/a'>A</a><a href='/outside'>Outside</a></body></html>",
            "https://example.com/docs/a": "<html><title>A</title><body><main>Level one support documentation content.</main><a href='/docs/b'>B</a></body></html>",
            "https://example.com/docs/b": "<html><title>B</title><body><main>Level two support documentation content.</main><a href='/docs/c'>C</a></body></html>",
        }
    )

    results = WebCrawler(db, fetcher, Renderer()).crawl_seed_deep(SeedConfig("https://example.com/docs"), max_depth=2)

    assert [result.url for result in results] == [
        "https://example.com/docs",
        "https://example.com/docs/a",
        "https://example.com/docs/b",
    ]
    assert db.count("pages") == 3


def test_deep_crawl_does_not_follow_sibling_prefix_paths(db):
    fetcher = URLFetcher(
        {
            "https://example.com/docs": "<html><title>Root</title><body><main>Root docs page with useful support content.</main><a href='/docs/a'>A</a><a href='/docs-old'>Old</a></body></html>",
            "https://example.com/docs/a": "<html><title>A</title><body><main>Level one support documentation content.</main></body></html>",
        }
    )

    results = WebCrawler(db, fetcher, Renderer()).crawl_seed_deep(SeedConfig("https://example.com/docs"), max_depth=2)

    assert [result.url for result in results] == ["https://example.com/docs", "https://example.com/docs/a"]
    assert "https://example.com/docs-old" not in fetcher.urls


def test_deep_crawl_deduplicates_links(db):
    fetcher = URLFetcher(
        {
            "https://example.com/docs": "<html><title>Root</title><body><main>Root docs page with useful support content.</main><a href='/docs/a'>A1</a><a href='/docs/a/'>A2</a></body></html>",
            "https://example.com/docs/a": "<html><title>A</title><body><main>Level one support documentation content.</main><a href='/docs'>Root</a></body></html>",
        }
    )

    results = WebCrawler(db, fetcher, Renderer()).crawl_seed_deep(SeedConfig("https://example.com/docs"), max_depth=2)

    assert [result.url for result in results] == ["https://example.com/docs", "https://example.com/docs/a"]
    assert fetcher.urls == ["https://example.com/docs", "https://example.com/docs/a"]
