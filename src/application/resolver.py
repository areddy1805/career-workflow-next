"""
src/application/resolver.py
===========================

One-shot resolution of a job's application path based on provider
capabilities.  The pipeline calls ``ApplicationResolutionService.resolve()``,
gets back an ``ApplicationResolution``, and executes it — no inline
``if provider == ...`` branching.

Design
------
* Stateless — one public factory method.
* Never raises ``AttributeError`` for missing provider methods.
* Unknown or missing providers resolve to ``NONE`` (unsupported).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.application.capability import ApplicationCapabilities, ApplicationMode


@dataclass(frozen=True)
class ApplicationResolution:
    """The result of resolving how a job should be handled.

    Fields
    ------
    provider_id : str
        Which provider acquired this job (e.g. ``"naukri"``, ``"hiringcafe"``).

    mode : ApplicationMode
        The resolved application mode.

    reasoning : str
        Human-readable explanation of why this mode was chosen.

    apply_url : str | None
        External apply URL, if the mode is ``EXTERNAL``.
    """

    provider_id: str
    mode: ApplicationMode
    reasoning: str
    apply_url: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class ApplicationResolutionService:
    """Resolves a job to an ``ApplicationResolution`` using provider capabilities."""

    @staticmethod
    def _value(obj: Any, key: str, default: Any = None) -> Any:
        """Read *key* from *obj* whether it's a dict or an object."""
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    @staticmethod
    def resolve_from_job(job: Any) -> ApplicationResolution:
        """Resolve application mode from a job object alone.
        
        Unlike ``resolve()``, this does not require a provider client object.
        It infers the mode from the job's metadata (provider_id, enrichment
        flags, apply_url).  This is useful in pipeline stages where only the
        job dict/object is available.
        """
        from src.application.detector import ATSDetector
        from src.application.models import ATSType

        def _val(key: str, default: Any = None) -> Any:
            return ApplicationResolutionService._value(job, key, default)

        provider_id = str(_val("provider_id", "unknown")).lower()

        # Determine the base capability from provider_id
        _MANUAL_REVIEW_PROVIDERS = {"hiringcafe", "jobspy", "linkedin", "google", "indeed"}
        _AUTO_PROVIDERS = {"naukri"}

        apply_url = _val("apply_url") or _val("apply_link")
        if apply_url and isinstance(apply_url, str) and not apply_url.strip():
            apply_url = None

        if provider_id in _AUTO_PROVIDERS:
            # Check for is_external_apply flag (Naukri jobs redirecting
            # to company career pages)
            is_external_flag = _val("is_external_apply")
            if isinstance(is_external_flag, dict):
                is_external_flag = is_external_flag.get("is_external_apply")
            if is_external_flag:
                return ApplicationResolution(
                    provider_id=provider_id,
                    mode=ApplicationMode.EXTERNAL_BROWSER,
                    reasoning="Naukri job redirects to external career page.",
                    apply_url=apply_url,
                )
            return ApplicationResolution(
                provider_id=provider_id,
                mode=ApplicationMode.AUTO,
                reasoning="Provider supports native (auto) application.",
            )

        if provider_id in _MANUAL_REVIEW_PROVIDERS:
            # Check URL for ATS detection
            if apply_url:
                ats_type = ATSDetector.detect_from_url(apply_url)
                if ats_type != ATSType.UNKNOWN:
                    return ApplicationResolution(
                        provider_id=provider_id,
                        mode=ApplicationMode.ATS,
                        reasoning=f"Detected supported ATS: {ats_type.value}",
                        apply_url=apply_url,
                    )
            return ApplicationResolution(
                provider_id=provider_id,
                mode=ApplicationMode.MANUAL_REVIEW,
                reasoning="Provider supports manual review.",
                apply_url=apply_url,
            )

        # Unknown provider — use URL-based detection
        if apply_url:
            ats_type = ATSDetector.detect_from_url(apply_url)
            if ats_type != ATSType.UNKNOWN:
                return ApplicationResolution(
                    provider_id=provider_id,
                    mode=ApplicationMode.ATS,
                    reasoning=f"Detected supported ATS: {ats_type.value}",
                    apply_url=apply_url,
                )
            url_lower = apply_url.lower()
            if "careers" in url_lower or "jobs" in url_lower:
                return ApplicationResolution(
                    provider_id=provider_id,
                    mode=ApplicationMode.EXTERNAL_BROWSER,
                    reasoning="URL appears to be a generic career site.",
                    apply_url=apply_url,
                )
            return ApplicationResolution(
                provider_id=provider_id,
                mode=ApplicationMode.MANUAL_REVIEW,
                reasoning="Unknown provider with URL, requires manual review.",
                apply_url=apply_url,
            )

        return ApplicationResolution(
            provider_id=provider_id,
            mode=ApplicationMode.NONE,
            reasoning=f"Unknown provider '{provider_id}' with no apply URL.",
        )
    def resolve(job: Any, provider: Any, meta: dict | None = None) -> ApplicationResolution:
        """Produce an ``ApplicationResolution`` for *job* given *provider*.

        The *provider* is expected to have an ``application_capabilities``
        property returning an ``ApplicationCapabilities`` instance.

        If the provider is ``None``, lacks the property, or has
        ``ApplicationMode.NONE``, the resolution is ``NONE`` (unsupported).

        *meta* is an optional dict with additional job metadata (e.g.
        ``is_external_apply`` from detail enrichment).
        """
        from src.application.router import ApplicationRouter

        provider_id = getattr(job, "provider_id", "unknown")

        if provider is None:
            return ApplicationResolution(
                provider_id=provider_id,
                mode=ApplicationMode.NONE,
                reasoning=f"No provider found for '{provider_id}'.",
            )

        caps: ApplicationCapabilities | None = getattr(
            provider, "application_capabilities", None
        )

        if caps is None or not isinstance(caps, ApplicationCapabilities):
            return ApplicationResolution(
                provider_id=provider_id,
                mode=ApplicationMode.NONE,
                reasoning=(
                    f"Provider '{provider_id}' does not declare "
                    "application capabilities."
                ),
            )

        # ── AUTO ──────────────────────────────────────────────────────
        # Provider-native auto-apply (e.g. Naukri Easy Apply).
        # Some jobs on AUTO providers redirect to an external career page;
        # detect that via is_external_apply and route to EXTERNAL_BROWSER.
        if caps.mode == ApplicationMode.AUTO:
            apply_url = getattr(job, "apply_url", None) or getattr(
                job, "apply_link", None
            )
            is_external_flag = getattr(job, "is_external_apply", None)
            if is_external_flag is None and meta is not None:
                is_external_flag = meta.get("is_external_apply")
            if isinstance(is_external_flag, dict):
                is_external_flag = is_external_flag.get("is_external_apply")
            if is_external_flag:
                return ApplicationResolution(
                    provider_id=provider_id,
                    mode=ApplicationMode.EXTERNAL_BROWSER,
                    reasoning=(
                        "Provider supports native apply but this job "
                        "requires external application via URL."
                    ),
                    apply_url=str(apply_url) if apply_url else None,
                )
            return ApplicationResolution(
                provider_id=provider_id,
                mode=ApplicationMode.AUTO,
                reasoning="Provider supports native (auto) application.",
            )

        # ── MANUAL_REVIEW ────────────────────────────────────────────
        # Jobs from manual-review portals (e.g. HiringCafe, JobSpy,
        # LinkedIn, Google, Indeed).  The pipeline opens the link for
        # the user but does not auto-submit.
        if caps.mode == ApplicationMode.MANUAL_REVIEW:
            apply_url = getattr(job, "apply_url", None) or getattr(
                job, "apply_link", None
            )
            # Use ApplicationRouter to check for ATS or generic career page
            if apply_url:
                from src.application.detector import ATSDetector
                from src.application.models import ATSType
                ats_type = ATSDetector.detect_from_url(apply_url)
                if ats_type != ATSType.UNKNOWN:
                    return ApplicationResolution(
                        provider_id=provider_id,
                        mode=ApplicationMode.ATS,
                        reasoning=f"Detected supported ATS: {ats_type.value}",
                        apply_url=apply_url,
                    )
                url_lower = apply_url.lower()
                if "careers" in url_lower or "jobs" in url_lower:
                    return ApplicationResolution(
                        provider_id=provider_id,
                        mode=ApplicationMode.EXTERNAL_BROWSER,
                        reasoning="URL appears to be a generic career site.",
                        apply_url=apply_url,
                    )
            return ApplicationResolution(
                provider_id=provider_id,
                mode=ApplicationMode.MANUAL_REVIEW,
                reasoning="Provider supports manual review.",
                apply_url=apply_url,
            )

        # ── ATS ──────────────────────────────────────────────────────
        # Provider declares ATS routing directly.
        if caps.mode == ApplicationMode.ATS:
            apply_url = getattr(job, "apply_url", None) or getattr(
                job, "apply_link", None
            )
            return ApplicationResolution(
                provider_id=provider_id,
                mode=ApplicationMode.ATS,
                reasoning="Provider supports ATS routing.",
                apply_url=apply_url,
            )

        # ── EXTERNAL (legacy) → EXTERNAL_BROWSER ─────────────────────
        # Providers that only support external-url apply via browser.
        if caps.mode == ApplicationMode.EXTERNAL:
            apply_url = getattr(job, "apply_url", None) or getattr(
                job, "apply_link", None
            )
            # Check for ATS via URL detection for richer routing
            if apply_url:
                from src.application.detector import ATSDetector
                from src.application.models import ATSType
                ats_type = ATSDetector.detect_from_url(apply_url)
                if ats_type != ATSType.UNKNOWN:
                    return ApplicationResolution(
                        provider_id=provider_id,
                        mode=ApplicationMode.ATS,
                        reasoning=f"Detected supported ATS: {ats_type.value}",
                        apply_url=apply_url,
                    )
            return ApplicationResolution(
                provider_id=provider_id,
                mode=ApplicationMode.EXTERNAL_BROWSER,
                reasoning="Provider supports external apply via browser.",
                apply_url=apply_url,
            )

        # ── NONE — fallthrough ──────────────────────────────────────
        return ApplicationResolution(
            provider_id=provider_id,
            mode=ApplicationMode.NONE,
            reasoning="Provider does not support any application mode.",
        )
