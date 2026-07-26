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
    def resolve(job: Any, provider: Any, meta: dict | None = None) -> ApplicationResolution:
        """Produce an ``ApplicationResolution`` for *job* given *provider*.

        The *provider* is expected to have an ``application_capabilities``
        property returning an ``ApplicationCapabilities`` instance.

        If the provider is ``None``, lacks the property, or has
        ``ApplicationMode.NONE``, the resolution is ``NONE`` (unsupported).

        *meta* is an optional dict with additional job metadata (e.g.
        ``is_external_apply`` from detail enrichment).
        """
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

        if caps.mode == ApplicationMode.AUTO:
            # Even AUTO providers can have external-apply jobs (e.g. Naukri
            # jobs that redirect to a company career page).  Check for an
            # external URL or the ``is_external_apply`` flag.
            apply_url = getattr(job, "apply_url", None) or getattr(
                job, "apply_link", None
            )
            is_external_flag = getattr(job, "is_external_apply", None)
            if is_external_flag is None and meta is not None:
                is_external_flag = meta.get("is_external_apply")
            if isinstance(is_external_flag, dict):
                is_external_flag = is_external_flag.get("is_external_apply")
            if apply_url or is_external_flag:
                return ApplicationResolution(
                    provider_id=provider_id,
                    mode=ApplicationMode.EXTERNAL,
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

        if caps.mode == ApplicationMode.EXTERNAL:
            apply_url = getattr(job, "apply_url", None) or getattr(
                job, "apply_link", None
            )
            if apply_url:
                return ApplicationResolution(
                    provider_id=provider_id,
                    mode=ApplicationMode.EXTERNAL,
                    reasoning="Provider supports external apply via URL.",
                    apply_url=str(apply_url),
                )
            return ApplicationResolution(
                provider_id=provider_id,
                mode=ApplicationMode.EXTERNAL,
                reasoning="Provider supports external apply but no URL is available.",
            )

        # NONE — fallthrough
        return ApplicationResolution(
            provider_id=provider_id,
            mode=ApplicationMode.NONE,
            reasoning="Provider does not support any application mode.",
        )
