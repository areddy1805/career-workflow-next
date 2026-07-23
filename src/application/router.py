from src.models.models import Job
from src.application.models import RoutingStrategy, ATSType
from src.application.capability import ProviderCapabilities
from src.application.result import RoutingResult
from src.application.detector import ATSDetector


class ApplicationRouter:
    """Routes a job to the appropriate application strategy."""

    @staticmethod
    def route(
        job: Job, capabilities: ProviderCapabilities, external_url: str = None
    ) -> RoutingResult:
        """
        Determine the routing strategy for the given job.

        Args:
            job: The job to route.
            capabilities: The capabilities of the provider that acquired the job.
            external_url: Optional external URL if known prior to routing.
                          If provided, takes precedence for detection.
        """
        # If the provider can apply natively and we don't have an explicit external URL to use instead.
        if capabilities.native_apply and not external_url:
            return RoutingResult(
                strategy=RoutingStrategy.NATIVE_APPLY,
                reasoning="Provider supports native application and no external override was provided.",
            )

        url_to_check = external_url or getattr(job, "apply_url", None)

        if not url_to_check:
            return RoutingResult(
                strategy=RoutingStrategy.MANUAL_REVIEW,
                reasoning="Job requires external apply but no URL is available.",
            )

        ats_type = ATSDetector.detect_from_url(url_to_check)

        if ats_type != ATSType.UNKNOWN:
            return RoutingResult(
                strategy=RoutingStrategy.EXTERNAL_ATS,
                ats_type=ats_type,
                url=url_to_check,
                reasoning=f"Detected supported ATS: {ats_type.value}",
            )

        # If it's unknown, we could check for generic career sites.
        # For phase 1, we classify standard company pages as Generic Career Site
        # if they have "careers" or "jobs" in the URL, else Manual Review.
        url_lower = url_to_check.lower()
        if "careers" in url_lower or "jobs" in url_lower:
            return RoutingResult(
                strategy=RoutingStrategy.GENERIC_CAREER_SITE,
                ats_type=ATSType.UNKNOWN,
                url=url_to_check,
                reasoning="URL appears to be a generic career site.",
            )

        return RoutingResult(
            strategy=RoutingStrategy.MANUAL_REVIEW,
            ats_type=ATSType.UNKNOWN,
            url=url_to_check,
            reasoning="Unknown destination, requires manual review.",
        )
