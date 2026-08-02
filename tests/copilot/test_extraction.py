"""Unit tests for CP-1-02: text/HTML/JSON-LD/PDF extraction."""

import pytest

from src.copilot.ingestion.extract.html import (
    canonical_url,
    extract_meta,
    html_to_text,
    page_title,
)
from src.copilot.ingestion.extract.jsonld import extract_jsonld
from src.copilot.ingestion.extract.pdf import pdf_to_text
from src.copilot.ingestion.extract.text import normalize_text
from src.copilot.ingestion.models import ParseError

SAMPLE_HTML = """
<html><head>
  <title>  Senior   Backend Engineer at Acme  </title>
  <meta name="description" content="Build the future of data.">
  <meta property="og:title" content="Senior Backend Engineer">
  <meta property="og:url" content="https://acme.com/careers/42">
  <link rel="canonical" href="/careers/42">
  <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "JobPosting",
     "title": "Senior Backend Engineer", "hiringOrganization": {"name": "Acme"}}
  </script>
  <script type="application/ld+json">not json</script>
  <script type="application/ld+json">
    {"@context": "https://schema.org", "@graph": [
      {"@type": "BreadcrumbList"}, {"@type": "Organization", "name": "Acme Corp"}]}
  </script>
</head><body>
  <script>var junk = "should not appear";</script>
  <style>.hidden { display: none; }</style>
  <h1>Senior Backend Engineer</h1>
  <p>We are hiring a  <strong>backend</strong>  engineer.</p>
</body></html>
"""


# ------------------------------------------------------------ text


def test_normalize_text_collapses_whitespace():
    assert normalize_text("  We are\n hiring  a\tbackend   engineer  ") == (
        "We are hiring a backend engineer"
    )


def test_normalize_text_unicode_nfkc():
    # full-width latin folds to ASCII (case preserved; lowercase is not
    # normalization's job — fingerprinting lowercases separately)
    assert normalize_text("Ｈｅｌｌｏ　Ｗｏｒｌｄ") == "Hello World"


def test_normalize_text_empty():
    assert normalize_text("") == ""
    assert normalize_text(None) == ""
    assert normalize_text("   \n\t ") == ""


# ------------------------------------------------------------ html


def test_html_to_text_strips_scripts_and_styles():
    text = html_to_text(SAMPLE_HTML)
    assert "junk" not in text
    assert "hidden" not in text
    assert "backend engineer" in text
    assert "We are hiring a backend engineer." in text


def test_html_to_text_empty():
    assert html_to_text("") == ""
    assert html_to_text(None) == ""


def test_extract_meta_collects_name_and_property():
    meta = extract_meta(SAMPLE_HTML)
    assert meta["description"] == "Build the future of data."
    assert meta["og:title"] == "Senior Backend Engineer"
    assert meta["og:url"] == "https://acme.com/careers/42"


def test_extract_meta_empty():
    assert extract_meta(None) == {}


def test_page_title():
    assert page_title(SAMPLE_HTML) == "Senior Backend Engineer at Acme"


def test_canonical_url_resolves_relative():
    assert canonical_url(SAMPLE_HTML, "https://acme.com/careers/42") == (
        "https://acme.com/careers/42"
    )
    assert canonical_url("<html></html>") is None


# ------------------------------------------------------------ json-ld


def test_extract_jsonld_collects_objects():
    objects = extract_jsonld(SAMPLE_HTML)
    types = {obj.get("@type") for obj in objects}
    assert "JobPosting" in types
    assert "Organization" in types  # flattened from @graph
    assert "BreadcrumbList" in types


def test_extract_jsonld_skips_malformed_and_missing():
    assert extract_jsonld("<script type='application/ld+json'>nope</script>") == []
    assert extract_jsonld("<html></html>") == []
    assert extract_jsonld(None) == []


def test_extract_jsonld_list_shaped_blocks():
    html = (
        '<script type="application/ld+json">'
        '[{"@type": "A"}, {"@type": "B"}, "scalar"]'
        "</script>"
    )
    assert {obj["@type"] for obj in extract_jsonld(html)} == {"A", "B"}


# ------------------------------------------------------------ pdf


def _make_pdf(text: str) -> bytes:
    """Build a minimal one-page PDF containing ``text`` (ASCII only)."""
    stream = b"BT /F1 24 Tf 72 720 Td (" + text.encode("ascii") + b") Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)


def test_pdf_to_text_extracts_text(tmp_path):
    pdf = tmp_path / "job.pdf"
    pdf.write_bytes(_make_pdf("Senior Backend Engineer at Acme"))
    assert pdf_to_text(pdf) == "Senior Backend Engineer at Acme"


def test_pdf_to_text_missing_file_raises(tmp_path):
    with pytest.raises(ParseError, match="cannot read PDF"):
        pdf_to_text(tmp_path / "missing.pdf")


def test_pdf_to_text_corrupt_file_raises(tmp_path):
    pdf = tmp_path / "bad.pdf"
    pdf.write_bytes(b"this is not a pdf")
    with pytest.raises(ParseError):
        pdf_to_text(pdf)
