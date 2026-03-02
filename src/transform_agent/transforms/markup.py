"""
Markup format transforms: Markdown ↔ HTML ↔ Plain Text

Uses markdown-it-py (MD→HTML), markdownify (HTML→MD), beautifulsoup4 (HTML→text).
"""

from __future__ import annotations

from markdownify import markdownify as md_from_html
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup


_md_parser = MarkdownIt("commonmark", {"typographer": True})


# ---------------------------------------------------------------------------
# HTML → *
# ---------------------------------------------------------------------------

async def html_to_markdown(data: bytes, options: dict | None = None) -> bytes:
    html_str = data.decode()
    strip = (options or {}).get("strip_tags", None)  # list of tags to strip
    result = md_from_html(html_str, strip=strip)
    return result.encode()


async def html_to_plain_text(data: bytes, options: dict | None = None) -> bytes:
    html_str = data.decode()
    soup = BeautifulSoup(html_str, "html.parser")
    separator = (options or {}).get("separator", "\n")
    text = soup.get_text(separator=separator, strip=True)
    return text.encode()


# ---------------------------------------------------------------------------
# Markdown → *
# ---------------------------------------------------------------------------

async def markdown_to_html(data: bytes, options: dict | None = None) -> bytes:
    md_str = data.decode()
    html = _md_parser.render(md_str)
    wrap = (options or {}).get("wrap_body", False)
    if wrap:
        html = f"<!DOCTYPE html><html><body>{html}</body></html>"
    return html.encode()


async def markdown_to_plain_text(data: bytes, options: dict | None = None) -> bytes:
    md_str = data.decode()
    # Render to HTML first, then strip tags
    html = _md_parser.render(md_str)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    return text.encode()
