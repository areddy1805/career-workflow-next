"""Typed form field model (CP-5-02).

Implements 04_BROWSER_ASSISTANT.md §4: from the DOM + accessibility tree of
the controlled page, structural heuristics (aria/label-for/wrapped-label,
placeholder, name/id) produce typed fields:

    TypedField {field_id, kind: text|number|date|select|radio|checkbox|
                textarea|upload|email|phone|url, label, name, options[],
                required, page, confidence}

and the accumulating :class:`FormModel` (02_ARCHITECTURE.md §7.6:

    FormModel {fields: TypedField[], pages: int, ats_type, auto_fillable})

Multi-page forms accumulate: extract each page's fields with its page index,
then ``FormModel.add_page`` merges (deduping by ``field_id``). A CAPTCHA
detected on the page sets ``auto_fillable = False`` (04 §3/§9 — never attempt
CAPTCHA; guidance mode instead). ATS adapters (CP-5-06) are optimizations
only; this generic extractor is the never-blocking fallback (ADR-005).

Extraction is pure DOM reading — no clicks, no fills (read-only-until-submit,
04 §10.1).
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from playwright.sync_api import Page

from src.copilot.constants import AtsType

# Frozen field kinds (04 §4).
_IGNORED_INPUT_TYPES = {"hidden", "submit", "button", "reset", "image"}

_INPUT_TYPE_TO_KIND: dict[str, "FieldKind"] = {}


class FieldKind(StrEnum):
    """Frozen TypedField.kind vocabulary (04 §4)."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    TEXTAREA = "textarea"
    UPLOAD = "upload"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"


_INPUT_TYPE_TO_KIND.update(
    {
        "text": FieldKind.TEXT,
        "number": FieldKind.NUMBER,
        "date": FieldKind.DATE,
        "email": FieldKind.EMAIL,
        "tel": FieldKind.PHONE,
        "url": FieldKind.URL,
        "checkbox": FieldKind.CHECKBOX,
        "radio": FieldKind.RADIO,
        "file": FieldKind.UPLOAD,
        "password": FieldKind.TEXT,  # kind is about shape, sensitivity is §10
    }
)

# Label-association quality -> extraction confidence (04 §4 "confidence").
CONF_LABEL = 1.0  # label[for] or wrapped label
CONF_ARIA_LABELLEDBY = 0.95
CONF_ARIA_LABEL = 0.9
CONF_PLACEHOLDER = 0.8
CONF_NAME_OR_ID = 0.7
CONF_NONE = 0.5

# Hostname markers for the ATS hint (03_OPPORTUNITY_MODEL.md §2 AtsType).
_ATS_HOST_MARKERS: list[tuple[str, str]] = [
    ("greenhouse.io", AtsType.GREENHOUSE.value),
    ("lever.co", AtsType.LEVER.value),
    ("ashbyhq.com", AtsType.ASHBY.value),
    ("workday", AtsType.WORKDAY.value),
    ("rippling", AtsType.RIPPLING.value),
]

_CAPTCHA_MARKERS = ("recaptcha", "hcaptcha", "captcha", "turnstile")


def detect_ats_type(url: str) -> str:
    """Best-effort ATS hint from the page URL (``AtsType.GENERIC`` default).

    The adapters (CP-5-06) refine this; extraction never depends on it.
    """
    host = url.lower()
    for marker, ats in _ATS_HOST_MARKERS:
        if marker in host:
            return ats
    return AtsType.GENERIC.value


@dataclass(frozen=True)
class FieldOption:
    """One select/radio option: the submit value + the human label."""

    value: str
    label: str

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "label": self.label}


@dataclass(frozen=True)
class TypedField:
    """One typed form field (frozen shape 04 §4)."""

    field_id: str
    kind: FieldKind
    label: str
    name: str
    options: tuple[FieldOption, ...]
    required: bool
    page: int
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "kind": self.kind.value,
            "label": self.label,
            "name": self.name,
            "options": [o.to_dict() for o in self.options],
            "required": self.required,
            "page": self.page,
            "confidence": self.confidence,
        }


@dataclass
class FormModel:
    """Accumulating form model across pages (02 §7.6 shape)."""

    fields: list[TypedField] = field(default_factory=list)
    pages: int = 0
    ats_type: str = AtsType.GENERIC.value
    auto_fillable: bool = False

    def add_page(self, new_fields: list[TypedField]) -> None:
        """Merge one page's fields, deduping by ``field_id`` (re-scans keep
        the first extraction — recovery, CP-5-05)."""
        seen = {f.field_id for f in self.fields}
        for f in new_fields:
            if f.field_id not in seen:
                seen.add(f.field_id)
                self.fields.append(f)
        self.pages = max([f.page for f in self.fields] + [0]) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "fields": [f.to_dict() for f in self.fields],
            "pages": self.pages,
            "ats_type": self.ats_type,
            "auto_fillable": self.auto_fillable,
        }


def extract_form_model(
    page: Page, *, ats_type: str | None = None, page_index: int = 0
) -> FormModel:
    """Extract the current page's fields and build a fresh FormModel.

    ``ats_type`` overrides URL detection (adapters/API may know better);
    ``page_index`` is the 0-based page number for multi-page forms.
    """
    fields = extract_fields(page, page_index=page_index)
    ats = ats_type or detect_ats_type(page.url)
    return FormModel(
        fields=fields,
        pages=page_index + 1,
        ats_type=ats,
        auto_fillable=bool(fields) and not _has_captcha(page),
    )


def extract_fields(page: Page, page_index: int = 0) -> list[TypedField]:
    """Extract every typed field from the page's DOM (04 §4 heuristics)."""
    id_text = _id_text_map(page)
    labels_by_for = _labels_by_for(page)
    controls = page.locator("input, select, textarea").all()

    radio_groups: dict[str, dict[str, Any]] = {}
    fields: list[TypedField] = []
    seen: set[str] = set()

    for pos, ctrl in enumerate(controls):
        tag = ctrl.evaluate("el => el.tagName.toLowerCase()")
        input_type = ctrl.get_attribute("type") or "text"
        if tag == "input" and input_type in _IGNORED_INPUT_TYPES:
            continue

        if tag == "select":
            kind = FieldKind.SELECT
            options = _select_options(ctrl)
        elif tag == "textarea":
            kind = FieldKind.TEXTAREA
            options = ()
        elif input_type == "radio":
            name = ctrl.get_attribute("name") or ""
            group = radio_groups.setdefault(
                name or f"radio_{pos}", {"name": name, "radios": []}
            )
            group["radios"].append(ctrl)
            continue
        else:
            kind = _INPUT_TYPE_TO_KIND.get(input_type, FieldKind.TEXT)
            options = ()

        label, confidence = _resolve_label(
            ctrl, input_type=input_type, id_text=id_text, labels_by_for=labels_by_for
        )
        name = ctrl.get_attribute("name") or ""
        field_id = _field_id(page_index, kind, ctrl, pos)
        if field_id in seen:
            continue
        seen.add(field_id)
        fields.append(
            TypedField(
                field_id=field_id,
                kind=kind,
                label=label,
                name=name,
                options=options,
                required=_is_required(ctrl),
                page=page_index,
                confidence=confidence,
            )
        )

    # Radio groups: one logical field per shared name (options = the radios).
    for group in radio_groups.values():
        name = group["name"]
        radios: list = group["radios"]
        field_id = f"p{page_index}:{FieldKind.RADIO}:{name or 'anon'}"
        label, confidence = _resolve_radio_group_label(radios, id_text, labels_by_for)
        options = tuple(_radio_option(r, id_text, labels_by_for) for r in radios)
        fields.append(
            TypedField(
                field_id=field_id,
                kind=FieldKind.RADIO,
                label=label,
                name=name,
                options=options,
                required=any(_is_required(r) for r in radios),
                page=page_index,
                confidence=confidence,
            )
        )
    return fields


# -- helpers --------------------------------------------------------------


def _id_text_map(page: Page) -> dict[str, str]:
    """id -> trimmed textContent for label/aria resolution (one DOM pass)."""
    return page.evaluate(
        """() => {
            const m = {};
            for (const el of document.querySelectorAll('[id]')) {
                m[el.id] = (el.textContent || '').trim();
            }
            return m;
        }"""
    )


def _labels_by_for(page: Page) -> dict[str, str]:
    labels: dict[str, str] = {}
    for lbl in page.locator("label").all():
        for_ = lbl.get_attribute("for")
        if for_:
            labels[for_] = (lbl.inner_text() or "").strip()
    return labels


def _resolve_label(
    ctrl, *, input_type: str, id_text: dict[str, str], labels_by_for: dict[str, str]
) -> tuple[str, float]:
    """04 §4 label resolution order: aria → label(for/wrap) → placeholder → name/id."""
    aria_by = ctrl.get_attribute("aria-labelledby")
    if aria_by:
        for anchor in aria_by.split():
            text = id_text.get(anchor)
            if text:
                return text, CONF_ARIA_LABELLEDBY
    aria_label = ctrl.get_attribute("aria-label")
    if aria_label and aria_label.strip():
        return aria_label.strip(), CONF_ARIA_LABEL
    ctrl_id = ctrl.get_attribute("id")
    if ctrl_id and ctrl_id in labels_by_for:
        return labels_by_for[ctrl_id], CONF_LABEL
    wrapped = ctrl.locator("xpath=ancestor::label[1]")
    if wrapped.count() > 0:
        text = (wrapped.first.inner_text() or "").strip()
        if text:
            return text, CONF_LABEL
    placeholder = ctrl.get_attribute("placeholder")
    if placeholder and placeholder.strip():
        return placeholder.strip(), CONF_PLACEHOLDER
    name = ctrl.get_attribute("name")
    if name and name.strip():
        return _humanize(name), CONF_NAME_OR_ID
    if ctrl_id and ctrl_id.strip():
        return _humanize(ctrl_id), CONF_NAME_OR_ID
    return "", CONF_NONE


def _resolve_radio_group_label(radios, id_text, labels_by_for) -> tuple[str, float]:
    """Group label: fieldset legend → fieldset aria-label → first radio label."""
    legend = radios[0].locator("xpath=ancestor::fieldset[1]/legend[1]")
    if legend.count() > 0:
        text = (legend.first.inner_text() or "").strip()
        if text:
            return text, CONF_LABEL
    fieldset = radios[0].locator("xpath=ancestor::fieldset[1]")
    if fieldset.count() > 0:
        aria = fieldset.first.get_attribute("aria-label")
        if aria and aria.strip():
            return aria.strip(), CONF_ARIA_LABEL
    for radio in radios:
        label, conf = _resolve_label(
            radio, input_type="radio", id_text=id_text, labels_by_for=labels_by_for
        )
        if label:
            return label, conf
    return "", CONF_NONE


def _radio_option(radio, id_text, labels_by_for) -> FieldOption:
    value = radio.get_attribute("value") or ""
    label, _ = _resolve_label(
        radio, input_type="radio", id_text=id_text, labels_by_for=labels_by_for
    )
    return FieldOption(value=value, label=label or value or "on")


def _select_options(ctrl) -> tuple[FieldOption, ...]:
    options: list[FieldOption] = []
    for opt in ctrl.locator("option").all():
        value = opt.get_attribute("value")
        if not value:
            continue  # placeholder options have no submit value
        label = (opt.inner_text() or "").strip()
        options.append(FieldOption(value=value, label=label or value))
    return tuple(options)


def _is_required(ctrl) -> bool:
    return ctrl.get_attribute("required") is not None or (
        ctrl.get_attribute("aria-required") or ""
    ).lower() == "true"


def _field_id(page_index: int, kind: FieldKind, ctrl, pos: int) -> str:
    """Deterministic, re-locatable id: stable across re-extraction."""
    anchor = ctrl.get_attribute("id") or ctrl.get_attribute("name") or f"pos{pos}"
    return f"p{page_index}:{kind.value}:{anchor}"


def _humanize(token: str) -> str:
    return re.sub(r"[_-]+", " ", token).strip()


def _has_captcha(page: Page) -> bool:
    """CAPTCHA markers → never attempt (04 §3/§9); guidance mode instead."""
    if page.locator(".g-recaptcha, .h-captcha, [id*='captcha']").count() > 0:
        return True
    srcs = page.locator("iframe").evaluate_all("els => els.map(e => e.src || '')")
    return any(marker in src.lower() for src in srcs for marker in _CAPTCHA_MARKERS)
