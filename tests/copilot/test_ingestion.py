"""Unit tests for CP-1-01: ingestion interface, registry, pipeline, errors."""

from dataclasses import FrozenInstanceError

import pytest

from src.copilot.exceptions import CopilotError
from src.copilot.ingestion import (
    IngestionAdapter,
    IngestionPayload,
    IngestionRegistry,
    ParsedOpportunity,
    RawSourceContent,
    run_ingestion,
)
from src.copilot.ingestion import registry as registry_module
from src.copilot.ingestion.models import (
    Attachment,
    FetchTimeoutError,
    IngestionError,
    ParseError,
    UnresolvableError,
    UnsupportedSourceError,
)


class SimAdapter(IngestionAdapter):
    """Deterministic fake adapter: happy-path normalization for kind='sim'."""

    source_id = "sim"

    def supports(self, payload):
        return isinstance(payload, IngestionPayload) and payload.kind == "sim"

    def fetch(self, payload):
        return RawSourceContent(
            source=self.source_id, raw_text="Senior Engineer at Acme"
        )

    def parse(self, content):
        return ParsedOpportunity(
            source=self.source_id,
            data={"title": "Senior Engineer", "company": "Acme"},
            provenance={"title": ["parser"], "company": ["parser"]},
        )


class FailingAdapter(IngestionAdapter):
    """Fake adapter whose fetch/parse behavior is switched per test."""

    source_id = "fail"
    mode = "ok"

    def supports(self, payload):
        return isinstance(payload, IngestionPayload) and payload.kind == "fail"

    def fetch(self, payload):
        if self.mode == "timeout":
            raise TimeoutError("socket timed out")
        if self.mode == "bad_content":
            return "not raw content"
        return RawSourceContent(source=self.source_id, raw_text="")

    def parse(self, content):
        if self.mode == "parse":
            raise ParseError("cannot parse")
        if self.mode == "unresolvable":
            raise UnresolvableError("no signal in content")
        if self.mode == "bad_result":
            return {"title": "not a ParsedOpportunity"}
        return ParsedOpportunity(source=self.source_id, data={}, provenance={})


class OtherAdapter(IngestionAdapter):
    """Second fake adapter for multi-adapter dispatch tests."""

    source_id = "other"

    def supports(self, payload):
        return isinstance(payload, IngestionPayload) and payload.kind == "other"

    def fetch(self, payload):
        return RawSourceContent(source=self.source_id, raw_text="x")

    def parse(self, content):
        return ParsedOpportunity(source=self.source_id, data={}, provenance={})


@pytest.fixture
def registry():
    return IngestionRegistry()


def sim_payload(**overrides):
    fields = {"kind": "sim", "data": {"url": "https://example.com/job"}, "meta": {}}
    fields.update(overrides)
    return IngestionPayload(**fields)


# ---------------------------------------------------------------- registry


def test_register_and_adapter_for_dispatches(registry):
    registry.register(SimAdapter())
    registry.register(OtherAdapter())
    assert registry.adapter_for(sim_payload()) is registry.adapter_for(sim_payload())
    assert registry.adapter_for(sim_payload()).source_id == "sim"
    assert (
        registry.adapter_for(IngestionPayload(kind="other")).source_id == "other"
    )


def test_adapter_for_first_registered_wins(registry):
    class SimAlias(SimAdapter):
        """Different source_id that still supports kind='sim' payloads."""

        source_id = "sim_alias"

    first, second = SimAdapter(), SimAlias()
    registry.register(first)
    registry.register(second)
    assert registry.adapter_for(sim_payload()) is first


def test_adapter_for_no_match_raises_unsupported(registry):
    registry.register(SimAdapter())
    with pytest.raises(UnsupportedSourceError) as exc:
        registry.adapter_for(IngestionPayload(kind="nope"))
    assert "sim" in str(exc.value)


def test_adapter_for_empty_registry_raises_unsupported(registry):
    with pytest.raises(UnsupportedSourceError):
        registry.adapter_for(sim_payload())


def test_register_duplicate_source_id_raises(registry):
    registry.register(SimAdapter())

    class Imposter(SimAdapter):
        pass

    # a different object claiming the same source_id must be rejected
    with pytest.raises(ValueError, match="sim"):
        registry.register(Imposter())


def test_register_same_object_is_idempotent(registry):
    adapter = SimAdapter()
    registry.register(adapter)
    registry.register(adapter)  # no raise
    assert registry.adapter_for(sim_payload()) is adapter


def test_module_level_register_and_adapter_for(monkeypatch):
    monkeypatch.setattr(registry_module, "default_registry", IngestionRegistry())
    registry_module.register(SimAdapter())
    adapter = registry_module.adapter_for(sim_payload())
    assert adapter.source_id == "sim"


# ---------------------------------------------------------------- pipeline


def test_run_ingestion_happy_path_simulation():
    reg = IngestionRegistry()
    reg.register(SimAdapter())
    parsed = run_ingestion(sim_payload(), registry=reg)
    assert isinstance(parsed, ParsedOpportunity)
    assert parsed.source == "sim"
    assert parsed.data["title"] == "Senior Engineer"
    assert parsed.provenance["company"] == ["parser"]


def test_run_ingestion_uses_default_registry(monkeypatch):
    monkeypatch.setattr(registry_module, "default_registry", IngestionRegistry())
    registry_module.register(SimAdapter())
    assert run_ingestion(sim_payload()).source == "sim"


def test_run_ingestion_unsupported_raises():
    with pytest.raises(UnsupportedSourceError):
        run_ingestion(sim_payload(), registry=IngestionRegistry())


def test_run_ingestion_timeout_maps_to_typed_error():
    adapter = FailingAdapter()
    adapter.mode = "timeout"
    reg = IngestionRegistry()
    reg.register(adapter)
    with pytest.raises(FetchTimeoutError) as exc:
        run_ingestion(IngestionPayload(kind="fail"), registry=reg)
    assert isinstance(exc.value.__cause__, TimeoutError)


def test_run_ingestion_parse_error_propagates():
    adapter = FailingAdapter()
    adapter.mode = "parse"
    reg = IngestionRegistry()
    reg.register(adapter)
    with pytest.raises(ParseError):
        run_ingestion(IngestionPayload(kind="fail"), registry=reg)


def test_run_ingestion_unresolvable_propagates():
    adapter = FailingAdapter()
    adapter.mode = "unresolvable"
    reg = IngestionRegistry()
    reg.register(adapter)
    with pytest.raises(UnresolvableError):
        run_ingestion(IngestionPayload(kind="fail"), registry=reg)


def test_run_ingestion_rejects_bad_fetch_result():
    adapter = FailingAdapter()
    adapter.mode = "bad_content"
    reg = IngestionRegistry()
    reg.register(adapter)
    with pytest.raises(ParseError):
        run_ingestion(IngestionPayload(kind="fail"), registry=reg)


def test_run_ingestion_rejects_bad_parse_result():
    adapter = FailingAdapter()
    adapter.mode = "bad_result"
    reg = IngestionRegistry()
    reg.register(adapter)
    with pytest.raises(ParseError):
        run_ingestion(IngestionPayload(kind="fail"), registry=reg)


# ---------------------------------------------------------------- models


def test_raw_source_content_defaults():
    content = RawSourceContent(source="pdf", raw_text="job description")
    assert content.raw_html is None
    assert content.attachments == ()
    assert content.url is None
    assert content.meta == {}


def test_raw_source_content_attachments_round_trip():
    content = RawSourceContent(
        source="generic_url",
        raw_text="t",
        attachments=(Attachment(name="resume.pdf", kind="pdf", ref="f1"),),
    )
    assert content.attachments[0].name == "resume.pdf"


def test_ingestion_payload_defaults():
    payload = IngestionPayload(kind="pasted_text")
    assert payload.data is None
    assert payload.meta == {}


def test_models_are_frozen():
    with pytest.raises(FrozenInstanceError):
        ParsedOpportunity(source="sim", data={}, provenance={}).source = "x"
    with pytest.raises(FrozenInstanceError):
        RawSourceContent(source="sim", raw_text="t").raw_text = "y"


# ---------------------------------------------------------------- taxonomy


@pytest.mark.parametrize(
    "error_cls",
    [
        IngestionError,
        UnsupportedSourceError,
        ParseError,
        FetchTimeoutError,
        UnresolvableError,
    ],
)
def test_taxonomy_subclasses_copilot_error(error_cls):
    assert issubclass(error_cls, CopilotError)


@pytest.mark.parametrize(
    "error_cls",
    [UnsupportedSourceError, ParseError, FetchTimeoutError, UnresolvableError],
)
def test_concrete_errors_subclass_ingestion_error(error_cls):
    assert issubclass(error_cls, IngestionError)
