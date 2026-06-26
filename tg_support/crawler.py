from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from tg_support.config import SeedConfig, canonicalize_url
from tg_support.renderer import PlaywrightRenderer
from tg_support.storage.db import SupportDatabase


class Fetcher(Protocol):
    def get(self, url: str, timeout: int = 20): ...


@dataclass(frozen=True)
class CrawlResult:
    url: str
    page_id: int | None
    rendered: bool
    status: str
    discovered: tuple[str, ...] = ()
    error: str | None = None


def extract_page(html: str, base_url: str) -> tuple[str | None, str, list[str], bool]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))
    links = []
    for link in soup.find_all("a", href=True):
        href = urljoin(base_url, link["href"])
        if urlparse(href).scheme not in {"http", "https"}:
            continue
        links.append(canonicalize_url(href))
    app_shell = len(text.split()) < 25 and bool(soup.find(id="root") or soup.find(id="app"))
    return title, text, sorted(set(links)), app_shell


def in_scope(url: str, seed: SeedConfig) -> bool:
    parsed_url = urlparse(url)
    parsed_seed = urlparse(seed.scope or seed.url)
    scope_path = parsed_seed.path.rstrip("/") or "/"
    return parsed_url.netloc == parsed_seed.netloc and (scope_path == "/" or parsed_url.path == scope_path or parsed_url.path.startswith(f"{scope_path}/"))


class WebCrawler:
    def __init__(self, db: SupportDatabase, fetcher: Fetcher | None = None, renderer: PlaywrightRenderer | None = None):
        self.db = db
        self.fetcher = fetcher or requests
        self.renderer = renderer or PlaywrightRenderer()

    def crawl_seed(self, seed: SeedConfig) -> CrawlResult:
        url = canonicalize_url(seed.url)
        try:
            response = self.fetcher.get(url, timeout=20)
            response.raise_for_status()
            html = response.text
            title, text, links, app_shell = extract_page(html, url)
            rendered = False
            if seed.render == "always" or (seed.render == "auto" and app_shell):
                html = self.renderer.render(url)
                title, text, links, _ = extract_page(html, url)
                rendered = True
            if seed.render == "never" and app_shell:
                text = ""
            discovered = tuple(link for link in links if in_scope(link, seed))
            page_id = self.db.upsert_page(url, title, text, rendered=rendered)
            return CrawlResult(url, page_id, rendered, "ok", discovered)
        except Exception as exc:
            page_id = self.db.upsert_page(url, None, "", status="error", error=str(exc))
            return CrawlResult(url, page_id, False, "error", (), str(exc))

    def crawl_seed_deep(self, seed: SeedConfig, max_depth: int = 2) -> list[CrawlResult]:
        start_url = canonicalize_url(seed.url)
        scope = seed.scope or seed.url
        pending: list[tuple[str, int]] = [(start_url, 0)]
        visited: set[str] = set()
        results: list[CrawlResult] = []

        while pending:
            url, depth = pending.pop(0)
            if url in visited:
                continue
            visited.add(url)

            result = self.crawl_seed(SeedConfig(url, render=seed.render, scope=scope))
            results.append(result)

            if depth >= max_depth:
                continue
            for link in result.discovered:
                if link not in visited:
                    pending.append((link, depth + 1))

        return results
