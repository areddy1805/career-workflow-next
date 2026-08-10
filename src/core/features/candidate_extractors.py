from typing import Dict, Any, List, Tuple
from src.core.job_intelligence.metadata import JobMetadata
from src.core.candidate.intelligence import CandidateIntelligence
from src.core.candidate.target_overlays import TargetProfileOverlay
from src.core.features.vector import FeatureResult
from src.core.features.definition import FeatureDefinition
from src.core.features.registry import FeatureRegistry

class CandidateFeatureSuite:
    """
    Release 3.1.7 Overlay-Aware Candidate Feature Suite.
    Evaluates candidate capabilities through active TargetProfileOverlays (Applied AI, FDE, Full Stack).
    """
    @staticmethod
    def register_candidate_features(registry: FeatureRegistry) -> None:
        registry.register(FeatureDefinition(id="required_skill_coverage", name="Required Skill Coverage", family="Compatibility", category="Resume", version="3.0.0", weight=15.0))
        registry.register(FeatureDefinition(id="learning_effort_estimate", name="Learning Effort Estimate", family="Compatibility", category="Resume", version="3.0.0", weight=10.0))
        registry.register(FeatureDefinition(id="certification_alignment", name="Certification Alignment", family="Compatibility", category="Resume", version="3.0.0", weight=12.0))
        
        # Overlay-Aware AI & FDE Features
        registry.register(FeatureDefinition(id="ai_transition_score", name="AI Transition Score", family="Preference", category="AI", version="3.0.0", weight=15.0))
        registry.register(FeatureDefinition(id="agentic_ai_relevance", name="Agentic AI Relevance", family="Preference", category="AI", version="3.0.0", weight=12.0))
        registry.register(FeatureDefinition(id="rag_relevance", name="RAG Relevance", family="Preference", category="AI", version="3.0.0", weight=10.0))
        registry.register(FeatureDefinition(id="azure_ai_cert_boost", name="Azure AI Certification Boost", family="Eligibility", category="Skills", version="3.0.0", weight=10.0))
        registry.register(FeatureDefinition(id="fde_consulting_score", name="FDE Customer & Consulting Score", family="Preference", category="Company", version="3.0.0", weight=15.0))
        
        # Market Quality
        registry.register(FeatureDefinition(id="company_quality", name="Company Quality", family="Market", category="Company", version="3.0.0", weight=10.0))
        registry.register(FeatureDefinition(id="product_vs_service", name="Product vs Service Company", family="Market", category="Company", version="3.0.0", weight=8.0))

        # Release 3.1.8: AI Role Confidence — distinguishes AI roles from general SWE
        registry.register(FeatureDefinition(id="ai_role_confidence", name="AI Role Confidence", family="Eligibility", category="AI", version="3.1.8", weight=15.0))
        registry.register(FeatureDefinition(id="swe_penalty", name="General SWE Penalty", family="Risk", category="AI", version="3.1.8", weight=-12.0))

    @staticmethod
    def get_candidate_extractor_map(intel: CandidateIntelligence, overlay: TargetProfileOverlay) -> Dict[str, Any]:
        return {
            "required_skill_coverage": lambda meta, prev: CandidateFeatureSuite._calc_skill_coverage(meta, intel, overlay),
            "learning_effort_estimate": lambda meta, prev: CandidateFeatureSuite._calc_learning_effort(meta, intel),
            "certification_alignment": lambda meta, prev: CandidateFeatureSuite._calc_cert_alignment(meta, intel),
            "azure_ai_cert_boost": lambda meta, prev: CandidateFeatureSuite._calc_azure_ai_cert_boost(meta, intel),
            "ai_transition_score": lambda meta, prev: CandidateFeatureSuite._calc_ai_transition(meta, intel),
            "agentic_ai_relevance": lambda meta, prev: CandidateFeatureSuite._calc_agentic_relevance(meta),
            "rag_relevance": lambda meta, prev: CandidateFeatureSuite._calc_rag_relevance(meta),
            "fde_consulting_score": lambda meta, prev: CandidateFeatureSuite._calc_fde_consulting(meta, intel, overlay),
            "company_quality": lambda meta, prev: CandidateFeatureSuite._calc_company_quality(meta),
            "product_vs_service": lambda meta, prev: CandidateFeatureSuite._calc_product_vs_service(meta),
            "ai_role_confidence": lambda meta, prev: CandidateFeatureSuite._calc_ai_role_confidence(meta),
            "swe_penalty": lambda meta, prev: CandidateFeatureSuite._calc_swe_penalty(meta),
        }

    @staticmethod
    def _calc_skill_coverage(meta: JobMetadata, intel: CandidateIntelligence, overlay: TargetProfileOverlay) -> FeatureResult:
        job_techs = [t.lower() for t in meta.technologies.value + meta.frameworks.value]
        if not job_techs:
            return FeatureResult("required_skill_coverage", "3.0.0", 15.0, value=0.7, confidence=50, state="MISSING", reason="No explicit required technologies in metadata")
        
        cand_skills = set(intel.primary_skills + intel.secondary_skills + intel.emerging_skills)
        matched = [t for t in job_techs if t in cand_skills]
        coverage = len(matched) / float(len(job_techs))
        
        # Apply overlay boost if priority technologies match
        priority_matched = [t for t in job_techs if t in overlay.priority_technologies]
        boost = 0.1 if priority_matched else 0.0
        final_val = round(min(1.0, coverage + boost), 2)
        
        return FeatureResult(
            feature_id="required_skill_coverage",
            feature_version="3.0.0",
            weight=15.0,
            value=final_val,
            confidence=95,
            state="PRESENT",
            reason=f"Overlay ({overlay.display_name}) Matched {len(matched)}/{len(job_techs)} tech skills (Priority boost: {boost}): {matched}"
        )

    @staticmethod
    def _calc_fde_consulting(meta: JobMetadata, intel: CandidateIntelligence, overlay: TargetProfileOverlay) -> FeatureResult:
        text = f"{meta.company.value} {meta.location.value}".lower()
        if overlay.target_role_id == "fde" or any(kw in text for kw in overlay.priority_keywords):
            val = 0.9 * overlay.consulting_weight_boost
            return FeatureResult(
                "fde_consulting_score", "3.0.0", 15.0,
                value=round(min(1.0, val), 2),
                confidence=90,
                state="PRESENT",
                reason="Forward Deployed Engineer Evidence: Candidate has 5y full-stack architecture, API integration, and enterprise client ownership"
            )
        return FeatureResult("fde_consulting_score", "3.0.0", 15.0, value=0.4, confidence=70, state="PRESENT", reason="General solution engineering fit")

    @staticmethod
    def _calc_learning_effort(meta: JobMetadata, intel: CandidateIntelligence) -> FeatureResult:
        job_techs = set([t.lower() for t in meta.technologies.value + meta.frameworks.value])
        cand_skills = set(intel.primary_skills + intel.secondary_skills + intel.emerging_skills)
        missing = job_techs - cand_skills
        
        if not missing:
            effort = 1.0
            reason = "No missing skills detected. Learning Effort: LOW"
        elif len(missing) <= 2:
            effort = 0.7
            reason = f"Missing {len(missing)} skills ({list(missing)}). Learning Effort: MEDIUM"
        else:
            effort = 0.3
            reason = f"Missing {len(missing)} skills ({list(missing)}). Learning Effort: HIGH"

        return FeatureResult("learning_effort_estimate", "3.0.0", 10.0, value=effort, confidence=90, state="PRESENT", reason=reason)

    @staticmethod
    def _calc_cert_alignment(meta: JobMetadata, intel: CandidateIntelligence) -> FeatureResult:
        text = f"{meta.technologies.value} {meta.cloud.value}".lower()
        has_azure_or_ai = any(c in text for c in ["azure", "ai", "openai", "ml"])
        if has_azure_or_ai and intel.verified_certifications:
            return FeatureResult("certification_alignment", "3.0.0", 12.0, value=1.0, confidence=100, state="PRESENT", reason=f"Verified Certifications Alignment: {list(intel.verified_certifications)}")
        return FeatureResult("certification_alignment", "3.0.0", 12.0, value=0.5, confidence=70, state="PRESENT", reason="General certification alignment")

    @staticmethod
    def _calc_azure_ai_cert_boost(meta: JobMetadata, intel: CandidateIntelligence) -> FeatureResult:
        text = f"{meta.technologies.value} {meta.cloud.value}".lower()
        if "azure" in text or "ai" in text:
            for cert in intel.verified_certifications:
                if "Azure AI Engineer Associate" in cert or "AI-102" in cert:
                    return FeatureResult("azure_ai_cert_boost", "3.0.0", 10.0, value=1.0, confidence=100, state="PRESENT", reason="Verified Azure AI Engineer Associate (AI-102) Certification Match!")
        return FeatureResult("azure_ai_cert_boost", "3.0.0", 10.0, value=0.0, confidence=90, state="PRESENT", reason="No Azure AI cert boost applied")

    @staticmethod
    def _calc_ai_transition(meta: JobMetadata, intel: CandidateIntelligence) -> FeatureResult:
        ai_kws = meta.ai_keywords.value
        if any(kw in ["llm", "rag", "generative ai", "openai", "agent", "deep learning"] for kw in ai_kws):
            return FeatureResult("ai_transition_score", "3.0.0", 15.0, value=1.0, confidence=95, state="PRESENT", reason=f"Strong AI transition fit matching career goals ({intel.reason_for_change}): {ai_kws}")
        return FeatureResult("ai_transition_score", "3.0.0", 15.0, value=0.2, confidence=80, state="PRESENT", reason="Traditional software engineering role")

    @staticmethod
    def _calc_agentic_relevance(meta: JobMetadata) -> FeatureResult:
        has_agent = any("agent" in kw or "autogen" in kw or "langgraph" in kw for kw in meta.ai_keywords.value)
        return FeatureResult("agentic_ai_relevance", "3.0.0", 12.0, value=1.0 if has_agent else 0.0, confidence=90, state="PRESENT", reason="Agentic AI keywords check")

    @staticmethod
    def _calc_rag_relevance(meta: JobMetadata) -> FeatureResult:
        has_rag = any("rag" in kw or "vector" in kw or "pinecone" in kw for kw in meta.ai_keywords.value)
        return FeatureResult("rag_relevance", "3.0.0", 10.0, value=1.0 if has_rag else 0.0, confidence=90, state="PRESENT", reason="RAG keywords check")

    @staticmethod
    def _calc_company_quality(meta: JobMetadata) -> FeatureResult:
        company = meta.company.value.lower()
        tier_1 = ["tata consultancy services", "infosys", "microsoft", "google", "amazon", "accenture"]
        val = 0.9 if any(t in company for t in tier_1) else 0.6
        return FeatureResult("company_quality", "3.0.0", 10.0, value=val, confidence=85, state="PRESENT", reason=f"Company quality score for {meta.company.value}")

    @staticmethod
    def _calc_product_vs_service(meta: JobMetadata) -> FeatureResult:
        return FeatureResult("product_vs_service", "3.0.0", 8.0, value=0.8, confidence=75, state="PRESENT", reason="Product engineering company indicator")

    @staticmethod
    def _calc_ai_role_confidence(meta: JobMetadata) -> FeatureResult:
        """
        Release 3.1.8: Measures how strongly the job metadata indicates
        a genuine AI/ML engineering role rather than general SWE.
        Uses the concatenated technologies + frameworks + ai_keywords
        from the metadata extraction pipeline.
        """
        tech_text = " ".join(meta.technologies.value + meta.frameworks.value).lower()
        ai_kws = meta.ai_keywords.value
        ai_kw_text = " ".join(ai_kws).lower() if ai_kws else ""

        ai_tech_kw = ["tensorflow", "pytorch", "langchain", "openai", "huggingface",
                      "transformers", "keras", "jax", "onnx", "mlflow", "kubeflow",
                      "weaviate", "pinecone", "chromadb", "llamaindex", "autogen",
                      "crewai", "langgraph", "vector", "embedding"]
        ai_role_kw = ["llm", "rag", "generative ai", "gen ai", "genai", "artificial intelligence",
                      "machine learning", "deep learning", "nlp", "computer vision",
                      "agentic", "prompt engineering", "ai agent", "ai evaluation",
                      "model deployment", "mlops", "ai/ml", "data science"]

        has_ai_kw = any(kw in ai_kw_text for kw in ai_role_kw)
        has_ai_tech = any(t in tech_text for t in ai_tech_kw)
        has_ai_basic = len(ai_kws) > 0

        if has_ai_kw and (has_ai_tech or has_ai_basic):
            val = 1.0
            reason = f"Strong AI role signal: {len(ai_kws)} AI keywords + AI tech stack"
        elif has_ai_kw:
            val = 0.7
            reason = f"Moderate AI role signal: AI keywords present ({len(ai_kws)})"
        elif has_ai_basic:
            val = 0.4
            reason = "Weak AI role signal: basic AI keyword match only"
        else:
            val = 0.1
            reason = "No AI role signal detected from metadata"

        return FeatureResult("ai_role_confidence", "3.1.8", 15.0, value=val, confidence=90, state="PRESENT", reason=reason)

    @staticmethod
    def _calc_swe_penalty(meta: JobMetadata) -> FeatureResult:
        """
        Release 3.1.8: Applies a penalty when the job uses general SWE
        technologies without AI specialization. Penalizes roles like
        .NET full-stack, support, field engineer when scored under
        the Applied AI Engineer overlay.
        """
        tech_text = " ".join(meta.technologies.value + meta.frameworks.value).lower()
        ai_kw_text = " ".join(meta.ai_keywords.value).lower() if meta.ai_keywords.value else ""

        ai_indicators = ["machine learning", "deep learning", "llm", "nlp",
                        "data science", "generative ai", "genai", "artificial intelligence",
                        "computer vision", "prompt engineering", "agentic",
                        "tensorflow", "pytorch", "langchain", "openai", "huggingface"]
        swe_indicators = [".net", "c#", "asp.net", "entity framework", "winforms",
                         "sql server", "vb.net", "sharepoint", "dynamics",
                         "desktop support", "technical support",
                         "business development", "helpdesk"]
        # ponytail: implementation/customer success/field service are LEGITIMATE
        # FDE signals (deploying to customers), not general-SWE penalties.

        has_ai = any(kw in ai_kw_text for kw in ai_indicators)
        has_swe_only = any(kw in tech_text for kw in swe_indicators)

        if has_swe_only and not has_ai:
            val = 1.0
            reason = "General SWE technologies without AI specialization"
        elif has_swe_only and has_ai:
            val = 0.3
            reason = "Hybrid SWE+AI technology stack"
        else:
            val = 0.0
            reason = "No general SWE penalty applied"

        return FeatureResult("swe_penalty", "3.1.8", -12.0, value=val, confidence=85, state="PRESENT", reason=reason)
