from src.application.models import ATSType
import urllib.parse


class ATSDetector:
    """Detects the Application Tracking System (ATS) from a given URL."""

    @staticmethod
    def detect_from_url(url: str) -> ATSType:
        """Analyze the URL and return the detected ATS type."""
        if not url:
            return ATSType.UNKNOWN

        try:
            parsed = urllib.parse.urlparse(url)
            netloc = parsed.netloc.lower()
            path = parsed.path.lower()
        except Exception:
            return ATSType.UNKNOWN

        if "greenhouse.io" in netloc:
            return ATSType.GREENHOUSE
        if "jobs.lever.co" in netloc or "lever.co" in netloc:
            return ATSType.LEVER
        if "myworkdayjobs.com" in netloc:
            return ATSType.WORKDAY
        if "jobs.ashbyhq.com" in netloc:
            return ATSType.ASHBY
        if "smartrecruiters.com" in netloc:
            return ATSType.SMARTRECRUITERS
        if "oraclecloud.com" in netloc and "careers" in path:
            return ATSType.ORACLE
        if (
            "sapsf.com" in netloc
            or "successfactors.com" in netloc
            or "sapsf.eu" in netloc
        ):
            return ATSType.SAP

        return ATSType.UNKNOWN
