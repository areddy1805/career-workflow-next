from enum import Enum


class RoutingStrategy(str, Enum):
    NATIVE_APPLY = "Native Apply"
    EXTERNAL_ATS = "External ATS"
    GENERIC_CAREER_SITE = "Generic Career Site"
    MANUAL_REVIEW = "Manual Review"
    UNSUPPORTED = "Unsupported"


class ATSType(str, Enum):
    GREENHOUSE = "Greenhouse"
    LEVER = "Lever"
    WORKDAY = "Workday"
    ASHBY = "Ashby"
    SMARTRECRUITERS = "SmartRecruiters"
    ORACLE = "Oracle Recruiting"
    SAP = "SAP SuccessFactors"
    UNKNOWN = "Unknown"
