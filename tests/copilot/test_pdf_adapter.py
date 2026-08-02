"""Integration tests for CP-1-09: PDF adapter (inline-built PDF fixtures)."""

from pathlib import Path

import pytest

from src.copilot.constants import ApplicationStrategy, OpportunitySource
from src.copilot.ingestion import IngestionPayload, IngestionRegistry, run_ingestion
from src.copilot.ingestion.adapters.pdf import PdfAdapter
from src.copilot.ingestion.models import ParseError, UnresolvableError


def _make_pdf(lines: list[str]) -> bytes:
    """Build a minimal one-page PDF with one text run per line (ASCII only)."""
    parts = [b"BT /F1 12 Tf"]
    y = 720
    for line in lines:
        parts.append(f"72 {y} Td ({line}) Tj".encode())
        y -= 20
    parts.append(b"ET")
    stream = b" ".join(parts)
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


TEXT_PDF = [
    "Job Title: Staff Data Engineer",
    "Company: Nova Labs",
    "Location: Remote (US)",
    "Salary: $150k - $180k",
    "Employment Type: Full-time",
    "Required Skills: Python, SQL, AWS",
    "",
    "We are building the realtime analytics platform at Nova Labs.",
]


@pytest.fixture
def adapter():
    return PdfAdapter()


def pdf_payload(path: str, key: str = "path") -> IngestionPayload:
    return IngestionPayload(
        kind=OpportunitySource.PDF.value, data={key: path}
    )


def write_pdf(tmp_path, lines: list[str]) -> Path:
    pdf = tmp_path / "job.pdf"
    pdf.write_bytes(_make_pdf(lines))
    return pdf


def _registry(adapter):
    reg = IngestionRegistry()
    reg.register(adapter)
    return reg


# ---------------------------------------------------------------- supports


def test_supports_matches_pdf_payload(adapter):
    assert adapter.supports(pdf_payload("/tmp/job.pdf")) is True
    assert adapter.supports(pdf_payload("/tmp/job.pdf", key="ref")) is True
    other = IngestionPayload(kind="pasted_text", data={"path": "/tmp/job.pdf"})
    assert adapter.supports(other) is False
    assert adapter.supports(IngestionPayload(kind="pdf")) is False
    assert adapter.supports(IngestionPayload(kind="pdf", data={"url": "/x"})) is False


# --------------------------------------------------------- text PDF


def test_text_pdf_structures_like_pasted_text(tmp_path, adapter):
    pdf = write_pdf(tmp_path, TEXT_PDF)
    parsed = run_ingestion(
        pdf_payload(str(pdf)), registry=_registry(adapter)
    )
    data = parsed.data
    assert data["source"] == OpportunitySource.PDF.value
    assert data["title"] == "Staff Data Engineer"
    assert data["company"] == "Nova Labs"
    assert data["application_strategy"] == ApplicationStrategy.MANUAL.value
    assert data["work_mode"] == "remote"
    assert data["country"] == "US"
    assert data["comp_min"] == 150000.0
    assert data["comp_max"] == 180000.0
    assert data["currency"] == "USD"
    assert data["employment_type"] == "full_time"
    assert data["required_skills"] == ["Python", "SQL", "AWS"]
    assert data["raw_ref"] == str(pdf)
    assert "realtime analytics platform" in data["description_text"]
    all_parser = [
        sources == ["parser"] for sources in parsed.provenance.values()
    ]
    assert all(all_parser)


def test_ref_payload_sets_raw_ref(tmp_path, adapter):
    pdf = write_pdf(tmp_path, TEXT_PDF)
    parsed = run_ingestion(
        pdf_payload(str(pdf), key="ref"), registry=_registry(adapter)
    )
    assert parsed.data["raw_ref"] == str(pdf)


# --------------------------------------------------------- scanned PDF


def test_scanned_pdf_returns_guidance_partial(tmp_path, adapter):
    pdf = write_pdf(tmp_path, [])  # blank page → no extractable text
    parsed = run_ingestion(
        pdf_payload(str(pdf)), registry=_registry(adapter)
    )
    assert parsed.meta["guidance"] == "scanned_pdf"
    assert parsed.meta["needs_manual_verify"] is True
    assert parsed.data["title"] == ""
    assert parsed.data["company"] == ""
    assert parsed.data["source"] == OpportunitySource.PDF.value


# ------------------------------------------------------------ failures


def test_missing_file_raises_parse_error(tmp_path, adapter):
    with pytest.raises(ParseError, match="cannot read PDF"):
        run_ingestion(
            pdf_payload(str(tmp_path / "missing.pdf")),
            registry=_registry(adapter),
        )


def test_text_without_identity_raises_unresolvable(tmp_path, adapter):
    pdf = write_pdf(
        tmp_path,
        ["Some notes about hiring plans.", "Nothing job-identifiable here."],
    )
    with pytest.raises(UnresolvableError, match="no title or company"):
        run_ingestion(
            pdf_payload(str(pdf)), registry=_registry(adapter)
        )
