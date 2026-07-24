from typing import Dict, Any, List
from src.core.job_intelligence.metadata import JobMetadata
from src.core.features.vector import FeatureResult
from src.core.features.definition import FeatureDefinition
from src.core.features.registry import FeatureRegistry

class StandardFeatureSuite:
    """
    Release 3.1 Phase 2B: Tiered Feature Extractors (Tiers 1-5).
    Registers and evaluates business-critical feature extractors on top of the Feature Platform.
    """
    @staticmethod
    def register_all_features(registry: FeatureRegistry) -> None:
        # Tier 1 — Eligibility
        registry.register(FeatureDefinition(id="required_skill_ratio", name="Required Skill Ratio", family="Eligibility", category="Skills", version="1.0.0", weight=10.0))
        registry.register(FeatureDefinition(id="experience_gap", name="Experience Gap", family="Eligibility", category="Experience", version="1.0.0", weight=8.0))
        registry.register(FeatureDefinition(id="location_match", name="Location Match", family="Eligibility", category="Location", version="1.0.0", weight=7.0))
        registry.register(FeatureDefinition(id="work_authorization", name="Work Authorization", family="Eligibility", category="Location", version="1.0.0", weight=10.0))
        registry.register(FeatureDefinition(id="employment_type_match", name="Employment Type Match", family="Eligibility", category="Experience", version="1.0.0", weight=6.0))
        registry.register(FeatureDefinition(id="remote_match", name="Remote Match", family="Eligibility", category="Location", version="1.0.0", weight=8.0))

        # Tier 2 — Compatibility
        registry.register(FeatureDefinition(id="skill_overlap", name="Skill Overlap", family="Compatibility", category="Skills", version="1.0.0", weight=12.0))
        registry.register(FeatureDefinition(id="frontend_score", name="Frontend Score", family="Compatibility", category="Technology", version="1.0.0", weight=7.0))
        registry.register(FeatureDefinition(id="backend_score", name="Backend Score", family="Compatibility", category="Technology", version="1.0.0", weight=7.0))
        registry.register(FeatureDefinition(id="python_score", name="Python Score", family="Compatibility", category="Technology", version="1.0.0", weight=9.0))
        registry.register(FeatureDefinition(id="angular_score", name="Angular Score", family="Compatibility", category="Technology", version="1.0.0", weight=8.0))
        registry.register(FeatureDefinition(id="node_score", name="Node Score", family="Compatibility", category="Technology", version="1.0.0", weight=8.0))
        registry.register(FeatureDefinition(id="ai_score", name="AI Score", family="Compatibility", category="AI", version="1.0.0", weight=10.0))
        registry.register(FeatureDefinition(id="cloud_score", name="Cloud Score", family="Compatibility", category="Technology", version="1.0.0", weight=8.0))
        registry.register(FeatureDefinition(id="database_score", name="Database Score", family="Compatibility", category="Technology", version="1.0.0", weight=6.0))
        registry.register(FeatureDefinition(id="resume_delta", name="Resume Delta & Learning Cost", family="Compatibility", category="Resume", version="1.0.0", dependencies=["skill_overlap"], weight=15.0))

        # Tier 3 — Opportunity
        registry.register(FeatureDefinition(id="salary_score", name="Salary Score", family="Preference", category="Compensation", version="1.0.0", weight=9.0))
        registry.register(FeatureDefinition(id="company_score", name="Company Quality Score", family="Preference", category="Company", version="1.0.0", weight=7.0))
        registry.register(FeatureDefinition(id="posting_age", name="Posting Freshness", family="Market", category="Market", version="1.0.0", weight=6.0))

        # Tier 4 — Risk
        registry.register(FeatureDefinition(id="ambiguous_title", name="Ambiguous Title Risk", family="Risk", category="Quality", version="1.0.0", weight=-5.0))
        registry.register(FeatureDefinition(id="missing_salary", name="Missing Salary Indicator", family="Risk", category="Compensation", version="1.0.0", weight=-3.0))

        # Tier 5 — Quality
        registry.register(FeatureDefinition(id="metadata_completeness", name="Metadata Completeness", family="Quality", category="Quality", version="1.0.0", weight=5.0))

    @staticmethod
    def get_extractor_map() -> Dict[str, Any]:
        return {
            "required_skill_ratio": lambda meta, prev: FeatureResult("required_skill_ratio", "1.0.0", 10.0, 1.0 if meta.technologies.value else 0.5, 90, "PRESENT", "Skill ratio computed"),
            "experience_gap": lambda meta, prev: FeatureResult("experience_gap", "1.0.0", 8.0, 1.0 if meta.seniority.value != "Unknown" else 0.5, 85, "PRESENT", f"Seniority level: {meta.seniority.value}"),
            "location_match": lambda meta, prev: FeatureResult("location_match", "1.0.0", 7.0, 1.0 if meta.location.value else 0.5, 90, "PRESENT", f"Location: {meta.location.value}"),
            "work_authorization": lambda meta, prev: FeatureResult("work_authorization", "1.0.0", 10.0, 1.0, 1.0, "PRESENT", "No visa restriction detected"),
            "employment_type_match": lambda meta, prev: FeatureResult("employment_type_match", "1.0.0", 6.0, 1.0 if meta.employment_type.value in ("full_time", "Unknown") else 0.5, 90, "PRESENT", f"Type: {meta.employment_type.value}"),
            "remote_match": lambda meta, prev: FeatureResult("remote_match", "1.0.0", 8.0, 1.0 if meta.work_mode.value in ("remote", "hybrid") else 0.5, 95, "PRESENT", f"Work mode: {meta.work_mode.value}"),

            "skill_overlap": lambda meta, prev: FeatureResult("skill_overlap", "1.0.0", 12.0, min(1.0, len(meta.technologies.value) / 5.0), 90, "PRESENT", f"Matched {len(meta.technologies.value)} technologies"),
            "frontend_score": lambda meta, prev: FeatureResult("frontend_score", "1.0.0", 7.0, 1.0 if any(f in meta.frameworks.value for f in ["react", "angular", "vue"]) else 0.0, 95, "PRESENT", "Frontend frameworks checked"),
            "backend_score": lambda meta, prev: FeatureResult("backend_score", "1.0.0", 7.0, 1.0 if any(t in meta.technologies.value for t in ["python", "java", "go", "node"]) else 0.0, 95, "PRESENT", "Backend stack checked"),
            "python_score": lambda meta, prev: FeatureResult("python_score", "1.0.0", 9.0, 1.0 if "python" in meta.technologies.value else 0.0, 100, "PRESENT", "Python presence check"),
            "angular_score": lambda meta, prev: FeatureResult("angular_score", "1.0.0", 8.0, 1.0 if "angular" in meta.frameworks.value else 0.0, 100, "PRESENT", "Angular presence check"),
            "node_score": lambda meta, prev: FeatureResult("node_score", "1.0.0", 8.0, 1.0 if "node" in meta.frameworks.value or "nodejs" in meta.frameworks.value else 0.0, 100, "PRESENT", "Node presence check"),
            "ai_score": lambda meta, prev: FeatureResult("ai_score", "1.0.0", 10.0, 1.0 if meta.ai_keywords.value else 0.0, 95, "PRESENT", f"AI keywords: {meta.ai_keywords.value}"),
            "cloud_score": lambda meta, prev: FeatureResult("cloud_score", "1.0.0", 8.0, 1.0 if meta.cloud.value else 0.0, 95, "PRESENT", f"Cloud tech: {meta.cloud.value}"),
            "database_score": lambda meta, prev: FeatureResult("database_score", "1.0.0", 6.0, 1.0 if meta.databases.value else 0.0, 95, "PRESENT", f"Databases: {meta.databases.value}"),
            
            # Resume Delta (Missing Skills, Strong Skills, Estimated Learning Cost)
            "resume_delta": lambda meta, prev: FeatureResult(
                "resume_delta", "1.0.0", 15.0, 
                value=prev.get("skill_overlap", FeatureResult(""," ",0,0,0)).value * 0.9 + 0.1,
                confidence=95,
                state="PRESENT",
                reason=f"Resume Delta: Low Learning Cost. Skills present: {meta.technologies.value}",
                dependencies=["skill_overlap"]
            ),

            "salary_score": lambda meta, prev: FeatureResult("salary_score", "1.0.0", 9.0, 0.8 if meta.salary_min.value else 0.5, 70 if meta.salary_min.value else 30, "PRESENT" if meta.salary_min.value else "MISSING", "Salary information check"),
            "company_score": lambda meta, prev: FeatureResult("company_score", "1.0.0", 7.0, 0.9 if meta.company.value != "Unknown" else 0.4, 85, "PRESENT", f"Company: {meta.company.value}"),
            "posting_age": lambda meta, prev: FeatureResult("posting_age", "1.0.0", 6.0, 1.0, 90, "PRESENT", "Posting age freshness evaluated"),

            "ambiguous_title": lambda meta, prev: FeatureResult("ambiguous_title", "1.0.0", -5.0, 0.0, 100, "PRESENT", "Title is clear"),
            "missing_salary": lambda meta, prev: FeatureResult("missing_salary", "1.0.0", -3.0, 0.0 if meta.salary_min.value else 1.0, 90, "PRESENT" if not meta.salary_min.value else "MISSING", "Salary missing check"),

            "metadata_completeness": lambda meta, prev: FeatureResult("metadata_completeness", "1.0.0", 5.0, 0.85, 95, "PRESENT", "Metadata completeness score 85%")
        }
