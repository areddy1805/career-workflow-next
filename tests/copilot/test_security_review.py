"""CP-9-02: Security review guard tests.

Phase G security checklist (08 CP-9-02 AC):
- **No pipeline DB writes / no static pipeline imports** (ADR-007): the
  copilot package must never import pipeline modules statically — all
  cross-boundary access is via importlib seams or injectable params.
- **No secrets in the copilot surface**: config, code and schemas must not
  carry credentials (secrets live in env only).
- **Pinned dependency** (playwright): the PH5 user mandate — the browser
  toolchain is version-pinned and vendored project-local.
- **PII rules present**: the sensitive-field guard (04 §6/§10.3) exists and
  is wired into the resolver path.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COPILOT_SRC = REPO / "src" / "copilot"

# Repo rule: no static pipeline imports inside src/copilot.
_PIPELINE_IMPORT = re.compile(
    r"^\s*(import|from)\s+(src\.)?(application|orchestration)\b", re.MULTILINE
)

# Anything that looks like a credential in copilot-owned code/config.
_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),  # OpenAI-style keys
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access keys
    re.compile(r"password\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE),
    re.compile(r"secret\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE),
]


def _py_files(root: Path):
    return sorted(p for p in root.rglob("*.py") if "fixtures" not in p.parts)


def test_no_static_pipeline_imports():
    offenders = []
    for path in _py_files(COPILOT_SRC):
        text = path.read_text(encoding="utf-8")
        if _PIPELINE_IMPORT.search(text):
            offenders.append(str(path.relative_to(REPO)))
    assert offenders == [], f"static pipeline imports in copilot: {offenders}"


def test_no_secrets_in_copilot_code_or_config():
    offenders = []
    scan_paths = [COPILOT_SRC, REPO / "config"]
    for root in scan_paths:
        for path in sorted(root.rglob("*")):
            if path.suffix not in {".py", ".yaml", ".yml", ".json", ".env.example"}:
                continue
            if "fixtures" in path.parts or path.name == "schema.sql":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in _SECRET_PATTERNS:
                if pattern.search(text):
                    offenders.append(str(path.relative_to(REPO)))
    assert offenders == [], f"possible secrets found: {offenders}"


def test_playwright_pinned_in_requirements():
    req = (REPO / "requirements.txt").read_text(encoding="utf-8")
    match = re.search(r"^playwright==([\d.]+)$", req, re.MULTILINE)
    assert match, "playwright must be pinned with == (user mandate, c911288)"
    assert match.group(1).count(".") >= 2  # x.y.z exact pin


def test_pii_guard_wired_into_resolver_path():
    """§6/§10.3: the sensitive-field guard exists and the resolver honors it."""
    import src.copilot.browser.resolver as resolver
    import src.copilot.browser.safety as safety

    assert hasattr(safety, "is_sensitive")
    assert hasattr(safety, "sensitive_fields")
    assert "sensitive" in resolver.resolve_field.__code__.co_varnames


def test_flags_production_posture():
    """Production integration (D-031): the flags REQUIRED for the complete
    workflow are ON (browser assistant, outcome capture); the experimental /
    optional ones stay OFF (learning bias = v5.2.0 scope, brief LLM prose =
    optional). Rollback for each is flipping the constant back."""
    import src.copilot.brief.llm as brief_llm
    import src.copilot.browser.controller as controller
    import src.copilot.learning.bias as bias
    import src.copilot.session.outcome as outcome

    assert controller.BROWSER_ENABLED is True
    assert outcome.OUTCOME_CAPTURE_ENABLED is True
    assert bias.LEARNING_BIAS_ENABLED is False
    assert brief_llm.BRIEF_LLM_ENABLED is False
