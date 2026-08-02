"""HTML extraction (CP-1-02): visible text, meta tags, title, canonical URL."""

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.copilot.ingestion.extract.text import normalize_text


def html_to_text(html: str | None) -> str:
    """Strip scripts/styles/navigation chrome and return visible text."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    return normalize_text(soup.get_text(" ", strip=True))


def extract_meta(html: str | None) -> dict[str, str]:
    """Collect ``<meta name|property content>`` pairs (OG, twitter, description...)."""
    meta: dict[str, str] = {}
    if not html:
        return meta
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("meta"):
        for key in ("name", "property"):
            name = tag.get(key)
            if isinstance(name, str) and name:
                content = tag.get("content")
                if isinstance(content, str):
                    meta.setdefault(name.strip(), content.strip())
    return meta


def page_title(html: str | None) -> str | None:
    """Return the ``<title>`` text (normalized), or None."""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title
    return normalize_text(title.string) if title and title.string else None


def canonical_url(html: str | None, base_url: str | None = None) -> str | None:
    """Return the ``<link rel=canonical>`` href resolved against ``base_url``."""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("link", rel="canonical"):
        href = link.get("href")
        if isinstance(href, str) and href:
            return urljoin(base_url, href) if base_url else href
    return None
