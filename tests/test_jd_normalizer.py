"""Regression tests for the JD normalization boundary
(control_center/jd_normalizer.py).

The JobInspector must never render raw HTML, escaped entities, or
serialization artifacts.  Every consumer (UI + CLI) reads the normalized
``jd.description_plain`` — these tests pin the normalization rules for
the real shapes found in stored job data.
"""

import pytest

from control_center.jd_normalizer import normalize_jd_to_text


def test_plain_text_unchanged():
    src = "Engineering Foundation: Roughly 1-3 years of software engineering experience."
    assert normalize_jd_to_text(src) == src


def test_html_becomes_readable_text_with_structure():
    src = (
        "<p><strong>Experience:</strong> 3-5 years</p>"
        "<ul><li>Build APIs</li><li>Work with Angular</li></ul>"
        "<br>Remote friendly"
    )
    out = normalize_jd_to_text(src)
    assert "<" not in out and ">" not in out
    assert "Experience: 3-5 years" in out
    assert "- Build APIs" in out
    assert "- Work with Angular" in out
    assert "Remote friendly" in out


def test_escaped_html_is_decoded():
    src = "&lt;p&gt;Hello&lt;/p&gt;&lt;br&gt;World"
    out = normalize_jd_to_text(src)
    assert "Hello" in out and "World" in out
    assert out.count("Hello") == 1 and "\n" in out
    assert "<" not in out


def test_double_escaped_html_is_decoded():
    src = "&amp;lt;p&amp;gt;Hello&amp;lt;/p&amp;gt;"
    out = normalize_jd_to_text(src)
    assert out == "Hello"


def test_json_encoded_html_is_decoded():
    src = '"<p>Company: Acme</p><p>Build agentic AI systems.</p>"'
    out = normalize_jd_to_text(src)
    assert out == "Company: Acme\nBuild agentic AI systems."
    assert "<" not in out


def test_malformed_html_degrades_safely():
    import re as _re

    src = "<div><p>Unclosed tags everywhere <strong>bold <span> and stray < here"
    out = normalize_jd_to_text(src)
    assert not _re.search(r"<[a-zA-Z/][^>]*>", out)
    assert "Unclosed tags everywhere" in out
    assert "bold" in out


def test_plain_text_with_lt_operator_survives():
    src = "Prefer 5 < 10 years experience; C++ a plus"
    out = normalize_jd_to_text(src)
    assert "5 < 10 years" in out
    assert "C++ a plus" in out


def test_legitimate_innerhtml_technical_term_preserved():
    src = "Nice to have: experience with innerHTML, DOM manipulation and vanilla JS."
    out = normalize_jd_to_text(src)
    assert "innerHTML" in out


def test_serialization_artifact_removed():
    src = 'Description: foo element.innerHTML = "<p>nested</p>"; bar'
    out = normalize_jd_to_text(src)
    assert "innerHTML" not in out
    assert "nested" not in out
    assert "foo" in out and "bar" in out


def test_react_serialization_artifact_removed():
    src = 'dangerouslySetInnerHTML={{__html: "<p>artifact</p>"}} rest'
    out = normalize_jd_to_text(src)
    assert "dangerouslySetInnerHTML" not in out
    assert "artifact" not in out
    assert "rest" in out


def test_script_content_cannot_survive():
    src = (
        "<p>Role summary</p>"
        "<script>document.body.innerHTML = '<img src=x onerror=alert(1)>'</script>"
        "<p onclick=\"alert(1)\">Apply now</p>"
    )
    out = normalize_jd_to_text(src)
    assert "<script" not in out and "</script>" not in out
    assert "alert(" not in out
    assert "onerror" not in out and "onclick" not in out
    assert "Role summary" in out
    assert "Apply now" in out


def test_entities_in_plain_text_decoded():
    src = "R&amp;D, C# &amp; .NET; salary &gt; 1L"
    out = normalize_jd_to_text(src)
    assert "R&D" in out
    assert "&gt;" not in out


def test_no_raw_html_artifacts_anywhere():
    src = "<div><p>&lt;strong&gt;Careers&lt;/strong&gt; page</p><ul><li>x</li></ul></div>"
    out = normalize_jd_to_text(src)
    assert "<" not in out and ">" not in out
    assert "&" not in out.replace("&", "")  # no entities left at all
    assert "Careers" in out
    assert "- x" in out


def test_empty_and_none_inputs():
    assert normalize_jd_to_text(None) == ""
    assert normalize_jd_to_text("") == ""
    assert normalize_jd_to_text("   ") == ""
    assert normalize_jd_to_text(12345) == "12345"
