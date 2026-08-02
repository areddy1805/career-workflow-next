"""Unit tests for CP-3-01: fingerprinting + canonical labels (06 §4)."""

from src.copilot.answerbank.canonical import CANONICAL_SLOTS, canonical_label
from src.copilot.answerbank.fingerprint import (
    Question,
    fingerprint,
    normalize_label,
    normalized_options_keys,
)

# ------------------------------------------------------- normalization


def test_normalize_label_lowercases_strips_punctuation_collapses():
    assert normalize_label("  How  many YEARS of RAG?!  ") == "how many years of rag"
    assert normalize_label("Email Address:") == "email address"


def test_normalized_options_keys():
    assert normalized_options_keys([]) == ""
    assert normalized_options_keys(["Yes", "No"]) == "yes|no"
    assert normalized_options_keys(["Python / RAG", " MLOps "]) == (
        "python rag|mlops"
    )


# ----------------------------------------------------------- fingerprint


def test_fingerprint_is_stable_and_16_hex():
    question = Question(label="How many years of RAG?")
    first = fingerprint(question)
    assert fingerprint(question) == first
    assert len(first) == 16
    int(first, 16)  # hex


def test_fingerprint_normalizes_variant_phrasings():
    a = fingerprint(Question(label="How many years of RAG?"))
    b = fingerprint(Question(label="how many years of rag ?"))
    assert a == b


def test_fingerprint_sensitive_to_options():
    base = Question(label="Willing to relocate?", options=[], kind="select")
    with_options = Question(
        label="Willing to relocate?", options=["Yes", "No"], kind="select"
    )
    assert fingerprint(base) != fingerprint(with_options)


def test_fingerprint_sensitive_to_kind():
    a = fingerprint(Question(label="Years of Python?", kind="years"))
    b = fingerprint(Question(label="Years of Python?", kind="text"))
    assert a != b


def test_fingerprint_sensitive_to_label():
    assert fingerprint(Question(label="Name")) != fingerprint(Question(label="Email"))


def test_fingerprint_question_from_dict():
    q = Question.from_dict(
        {"label": "Name?", "options": [], "kind": "text", "extra": "ignored"}
    )
    assert q == Question(label="Name?")


# ------------------------------------------------- canonical: synonyms


def test_canonical_maps_variant_phrasings_to_same_slot():
    pairs = {
        "experience.rag_years": [
            "How many years of RAG?",
            "How many years of RAG do you have?",
            "RAG experience in years",
            "Years of RAG experience:",
        ],
        "experience.python_years": [
            "How many years of Python?",
            "Python experience (years)",
        ],
        "identity.email": [
            "Email Address",
            "What is your email address?",
            "Enter your e-mail address",
        ],
        "identity.phone": [
            "Phone number",
            "Mobile number",
            "Contact number",
        ],
        "profile.experience_years": [
            "Years of experience",
            "Total work experience",
            "How many years of experience do you have?",
        ],
        "profile.notice_period": [
            "Notice period",
            "What is your notice period?",
            "How much notice do you need?",
        ],
        "summary.job_change_reason": [
            "Reason for leaving your current role",
            "Why are you looking for a change?",
            "Job change reason",
        ],
        "capability.ollama": [
            "Have you used Ollama?",
            "Do you have experience with Ollama?",
        ],
        "preference.remote": [
            "Are you open to remote work?",
            "Remote work preference",
        ],
    }
    for slot, phrasings in pairs.items():
        for phrasing in phrasings:
            assert canonical_label(phrasing) == slot, (
                f"{phrasing!r} should map to {slot}"
            )


def test_canonical_first_match_wins_most_specific():
    # "city" must not shadow longer identity.location phrasing
    assert canonical_label("Which city do you live in?") == "identity.city"
    assert canonical_label("Are you willing to relocate?") == "profile.location"


def test_canonical_unknown_returns_none():
    for text in [
        "Describe your approach to debugging distributed systems",
        "Do you hold any certifications?",
        "",
        "   ",
    ]:
        assert canonical_label(text) is None


def test_canonical_slots_are_valid_and_nonempty():
    for slot, patterns in CANONICAL_SLOTS:
        assert slot and patterns
        assert "." in slot
        assert all(p.strip() for p in patterns)


def test_canonical_is_case_and_punctuation_insensitive():
    assert canonical_label("EMAIL ADDRESS!") == "identity.email"
    assert canonical_label("years of RAG") == "experience.rag_years"
