from __future__ import annotations

from tg_support.crawler import extract_page


def test_extract_page_detects_app_shell():
    title, text, links, app_shell = extract_page("<div id='root'></div><script src='app.js'></script>", "https://example.com")
    assert title is None
    assert text == ""
    assert links == []
    assert app_shell is True
