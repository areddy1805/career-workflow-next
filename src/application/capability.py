from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCapabilities:
    """Describes what a provider is capable of doing."""

    native_apply: bool
    returns_external_url: bool
    requires_authentication: bool
    supports_resume_upload: bool
    supports_questionnaires: bool
