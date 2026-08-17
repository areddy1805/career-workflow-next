import os
import yaml
from enum import Enum
from typing import Dict, Any

class ResumeType(Enum):
    AI = "AI"
    FDE = "FDE"

class ResumeRouter:
    def __init__(self):
        self.ai_roles = [
            "Applied AI Engineer", "AI Engineer", "GenAI Engineer", "LLM Engineer",
            "RAG Engineer", "AI Platform Engineer", "AI Infrastructure Engineer",
            "ML Platform Engineer", "Agentic AI Engineer", "AI Solutions Architect",
            "AI Developer", "AI Software Engineer"
        ]
        self.fde_roles = [
            "Forward Deployed Engineer", "Solutions Engineer", "Solutions Consultant",
            "Technical Consultant", "AI Consultant", "Customer Engineer",
            "Implementation Engineer", "Implementation Consultant", "Integration Engineer",
            "Sales Engineer", "Field Engineer", "Technical Solutions Engineer"
        ]
        
        self.ai_keywords = ["ai", "machine learning", "llm", "genai", "rag", "agentic", "model", "python", "backend"]
        self.fde_keywords = ["customer", "client", "implementation", "solution", "consultant", "delivery", "integration", "full stack"]

    def route_from_family(
        self,
        family: str,
        ai_depth: int = 0,
    ) -> Dict[str, Any]:
        """Route the resume from the deterministic ranker's analysis.

        AI_FDE is an AI role first (ai_depth >= 3 + strong FDE evidence) —
        it gets the AI resume.  FDE gets the customer-deployment resume.
        AI_ADJACENT/GENERIC with no AI depth fall back to the keyword
        heuristic so adjacent roles still route sensibly.
        """
        resumes = self.load_resumes()

        if family == "AI_FDE" or family == "AI_ENGINEERING":
            return {
                "resume_type": ResumeType.AI.value,
                "resume_reason": (
                    f"Deterministic ranker family {family} (ai_depth={ai_depth}) "
                    "→ AI resume"
                ),
                "resume_score_ai": 100 if family == "AI_FDE" else 90,
                "resume_score_fde": 60 if family == "AI_FDE" else 10,
                "resume_path": resumes.get(ResumeType.AI.value),
            }

        if family == "FDE":
            return {
                "resume_type": ResumeType.FDE.value,
                "resume_reason": (
                    f"Deterministic ranker family {family} "
                    "→ FDE resume"
                ),
                "resume_score_ai": 10,
                "resume_score_fde": 100,
                "resume_path": resumes.get(ResumeType.FDE.value),
            }

        # AI_ADJACENT / GENERIC / NON_TARGET — fall back to keyword scoring.
        return self.route(
            {
                "title": "",
                "description": "",
                "required_skills": [],
                "preferred_skills": [],
            }
        )

    def load_resumes(self) -> Dict[str, str]:
        # Authoritative artifact (CP-0-03): the only real resume on disk.
        # Fallbacks must never point at files that do not exist.
        _REAL = "docs/resume/Abhilash_Reddy_ResumeU.pdf"
        config_path = os.environ.get("RESUMES_CONFIG", "config/resumes.yaml")
        if not os.path.exists(config_path):
            return {"AI": _REAL, "FDE": _REAL}
        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)
                return {
                    "AI": data.get("AI", {}).get("path", _REAL),
                    "FDE": data.get("FDE", {}).get("path", _REAL),
                }
        except Exception:
            return {"AI": _REAL, "FDE": _REAL}

    def _score_text(self, text: str, keywords: list[str]) -> int:
        if not text:
            return 0
        text_lower = text.lower()
        return sum(5 for kw in keywords if kw in text_lower)

    def route(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determines the appropriate resume type for a given job using a weighted score.
        """
        title = job.get("title", "").lower()
        description = job.get("description", "").lower()
        
        ai_score = 0
        fde_score = 0
        
        # 1. Base check on title against role families (High Weight)
        for role in self.ai_roles:
            if role.lower() in title:
                ai_score += 50
        for role in self.fde_roles:
            if role.lower() in title:
                fde_score += 50
                
        # 2. Title keywords
        ai_score += self._score_text(title, self.ai_keywords)
        fde_score += self._score_text(title, self.fde_keywords)
        
        # 3. Job Description keywords
        ai_score += self._score_text(description, self.ai_keywords)
        fde_score += self._score_text(description, self.fde_keywords)
        
        # 4. Required / Preferred Skills if available
        skills = " ".join(job.get("required_skills", []) + job.get("preferred_skills", []))
        ai_score += self._score_text(skills, self.ai_keywords)
        fde_score += self._score_text(skills, self.fde_keywords)
        
        if ai_score >= fde_score:
            selected = ResumeType.AI
            reason = f"AI score ({ai_score}) exceeded or equalled FDE score ({fde_score})."
        else:
            selected = ResumeType.FDE
            reason = f"FDE score ({fde_score}) exceeded AI score ({ai_score})."
            
        resumes = self.load_resumes()
        
        return {
            "resume_type": selected.value,
            "resume_reason": reason,
            "resume_score_ai": ai_score,
            "resume_score_fde": fde_score,
            "resume_path": resumes.get(selected.value)
        }
