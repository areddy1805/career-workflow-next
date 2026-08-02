"""JSON-LD extraction (CP-1-02).

Collects every ``<script type="application/ld+json">`` block and flattens
``@graph`` containers, so job-post schemas (JobPosting, Organization, ...)
are directly addressable by adapters.
"""

import json
from typing import Any

from bs4 import BeautifulSoup


def extract_jsonld(html: str | None) -> list[dict[str, Any]]:
    """Return all JSON-LD objects found in ``html`` (skips malformed blocks)."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    result: list[dict[str, Any]] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            _collect(data, result)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    _collect(item, result)
    return result


def _collect(node: dict[str, Any], result: list[dict[str, Any]]) -> None:
    graph = node.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            if isinstance(item, dict):
                result.append(item)
        return
    result.append(node)
