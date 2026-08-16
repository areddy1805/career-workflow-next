"""Deterministic job-description normalization for the inspection surface.

Job descriptions arrive as untrusted provider content in many shapes:
plain text, HTML, escaped HTML, JSON-encoded HTML, mixed/malformed HTML,
occasionally serialized source artifacts.  This module normalizes any of
them to readable plain text WITHOUT rendering HTML — the UI renders text
only, so scripts can never execute and no markup leaks to the user.

Boundary rules
--------------
- JSON-encoded strings are decoded first (a stored JD may literally be
  ``"<p>Company: ...</p>"`` including the quotes).
- HTML entities are unescaped repeatedly (handles ``&lt;p&gt;`` and
  double-escaped ``&amp;lt;p&amp;gt;``).
- Structural tags become line structure: block ends and <br> become
  newlines, <li> becomes a text bullet, headings land on their own line.
- ``<script>/<style>/<svg>/<iframe>/<object>/<embed>/<noscript>`` blocks
  are removed entirely (content included).
- Serialization artifacts (``element.innerHTML = "..."``,
  ``dangerouslySetInnerHTML={{...}}``) are removed only when they are
  clearly source/serialization syntax (assignment or JSX object form);
  a standalone ``innerHTML`` in prose is kept because it is a legitimate
  technical term in real JDs.
- Malformed markup degrades to readable text: stray ``<`` that does not
  begin a tag is preserved (``5 < 10``), leftover partial tags are
  removed, blank lines are collapsed.
"""

from __future__ import annotations

import html as _html
import json as _json
import re

__all__ = ["normalize_jd_to_text"]

_BLOCK_END = re.compile(
    r"</(?:p|div|li|tr|ul|ol|section|table|blockquote|td|th|h[1-6])>",
    re.IGNORECASE,
)
_LIST_ITEM = re.compile(r"<li\b[^>]*>", re.IGNORECASE)
_TABLE_ROW = re.compile(r"<tr\b[^>]*>", re.IGNORECASE)
_HEADING = re.compile(r"<h[1-6]\b[^>]*>", re.IGNORECASE)
_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_BLOCK_BLOCK = re.compile(
    r"<(script|style|svg|iframe|object|embed|noscript)\b[^>]*>.*?"
    r"</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_UNCLOSED_BLOCK = re.compile(
    r"<(script|style|iframe|object|embed)\b[^>]*>.*$",
    re.IGNORECASE | re.DOTALL,
)
_ANY_TAG = re.compile(r"<[^>]*>")
_PARTIAL_TAG = re.compile(r"<[a-zA-Z/][^>]{0,120}>")
_ENTITY = re.compile(r"&(?:[a-zA-Z#0-9]+|#x[0-9a-fA-F]+);")
_MULTI_BLANK = re.compile(r"\n{3,}")

# Serialization artifacts — only assignment/JSX-object syntax, so real
# technical prose ("Experience with innerHTML and DOM APIs") survives.
_ARTIFACTS = [
    re.compile(r"(?:\.|element\.)?innerHTML\s*=\s*(?:`[^`]*`|\"[^\"]*\"|'[^']*'|\{[^\n]{0,120}\})", re.IGNORECASE),
    re.compile(r"dangerouslySetInnerHTML\s*=\s*\{\{[^\n]{0,120}\}\}", re.IGNORECASE),
    re.compile(r"__html\s*[:=]\s*[^\n,}]{0,120}", re.IGNORECASE),
]

_WS_RUN = re.compile(r"[ \t]+\n")
_LEAD_WS = re.compile(r"^[ \t]+", re.MULTILINE)


def _decode_entities(text: str) -> str:
    """Unescape HTML entities until stable (handles double-escaped input)."""
    for _ in range(4):
        if not _ENTITY.search(text):
            break
        decoded = _html.unescape(text)
        if decoded == text:
            break
        text = decoded
    return text


def _unwrap_json_encoding(text: str) -> str:
    """Decode a stored-JD that is itself a JSON string (quotes included)."""
    stripped = text.strip()
    if not stripped:
        return text
    try:
        if stripped.startswith('"') and stripped.endswith('"'):
            value = _json.loads(stripped)
            if isinstance(value, str):
                return value
        elif stripped.startswith("'") and stripped.endswith("'"):
            value = _json.loads('"' + stripped[1:-1].replace('"', '\\"') + '"')
            if isinstance(value, str):
                return value
    except (ValueError, TypeError):
        pass
    return text


def _remove_artifacts(text: str) -> str:
    for pattern in _ARTIFACTS:
        text = pattern.sub(" ", text)
    return text


def normalize_jd_to_text(raw: object) -> str:
    """Normalize any stored JD shape into readable plain text.

    Returns '' when nothing usable is present.  Never raises on malformed
    input.  The output contains no HTML tags and no executable content.
    """
    if raw is None:
        return ""
    if not isinstance(raw, str):
        try:
            raw = str(raw)
        except Exception:
            return ""
    text = _unwrap_json_encoding(raw)
    text = _decode_entities(text)
    # Serialization artifacts first — source syntax is still intact here
    # (tag-to-line conversion below can split multi-line JSX objects).
    text = _remove_artifacts(text)
    # Drop executable/embedded blocks before touching anything else.
    text = _BLOCK_BLOCK.sub("\n", text)
    text = _UNCLOSED_BLOCK.sub("", text)
    # Structure → line breaks.
    text = _BREAK.sub("\n", text)
    text = _BLOCK_END.sub("\n", text)
    text = _LIST_ITEM.sub("\n- ", text)
    text = _TABLE_ROW.sub("\n", text)
    text = _HEADING.sub("\n", text)
    text = text.replace("</td>", " | ").replace("</th>", " | ")
    # Remove remaining tags (never executed — this is text).
    text = _ANY_TAG.sub("", text)
    text = _PARTIAL_TAG.sub("", text)
    text = _remove_artifacts(text)
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    # Collapse whitespace into a readable shape.
    text = _WS_RUN.sub("\n", text)
    text = _LEAD_WS.sub("", text)
    text = _MULTI_BLANK.sub("\n\n", text)
    text = text.strip()
    return text
