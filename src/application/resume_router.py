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

    def load_resumes(self) -> Dict[str, str]:
        config_path = os.environ.get("RESUMES_CONFIG", "config/resumes.yaml")
        if not os.path.exists(config_path):
            return {
                "AI": "docs/resume/Applied_AI.pdf",
                "FDE": "docs/resume/Forward_Deployed.pdf"
            }
        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)
                return {
                    "AI": data.get("AI", {}).get("path", "docs/resume/Applied_AI.pdf"),
                    "FDE": data.get("FDE", {}).get("path", "docs/resume/Forward_Deployed.pdf")
                }
        except Exception:
            return {
                "AI": "docs/resume/Applied_AI.pdf",
                "FDE": "docs/resume/Forward_Deployed.pdf"
            }

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
