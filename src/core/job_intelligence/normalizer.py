import re
import html
import unicodedata
from typing import Dict, Any
from src.models.models import Job
from src.core.job_intelligence.normalized_job import NormalizedJob

class JobNormalizer:
    """
    Phase 0C Compiler-Grade Normalizer.
    Normalizes HTML entities, Unicode, whitespace, company names, titles, and salary representations.
    Returns an immutable NormalizedJob instance.
    """

    def __init__(self):
        self.company_canonical_map = {
            r'\btcs\b|\btata consultancy services ltd\b': 'Tata Consultancy Services',
            r'\binfosys ltd\b|\binfy\b': 'Infosys',
            r'\bwipro ltd\b': 'Wipro',
            r'\baccenture solutions\b': 'Accenture',
            r'\bmsft\b': 'Microsoft',
            r'\bamzn\b': 'Amazon',
            r'\bgoog\b|\bgoogle llc\b': 'Google'
        }

        self.title_canonical_map = {
            r'\bsse\b|\bsr\.? software eng(ineer)?\b': 'Senior Software Engineer',
            r'\bse\b|\bsoftware eng(ineer)?\b': 'Software Engineer',
            r'\bfe\b|\bfrontend eng(ineer)?\b': 'Frontend Engineer',
            r'\bbe\b|\bbackend eng(ineer)?\b': 'Backend Engineer',
            r'\bdevops eng(ineer)?\b': 'DevOps Engineer',
            r'\bsde\s?1\b|\bsde-1\b': 'Software Development Engineer I',
            r'\bsde\s?2\b|\bsde-2\b': 'Software Development Engineer II',
            r'\bsde\s?3\b|\bsde-3\b': 'Software Development Engineer III',
        }

        self.aliases = {
            r'\bnode\.js\b': 'nodejs',
            r'\breact\.js\b': 'reactjs',
            r'\bvue\.js\b': 'vuejs',
            r'\bfront-end\b': 'frontend',
            r'\bback-end\b': 'backend',
            r'\bfull-stack\b': 'fullstack'
        }

    def decode_html_and_unicode(self, text: str) -> str:
        if not text:
            return ""
        # HTML unescape
        text = html.unescape(text)
        # Unicode normalization (NFKD)
        text = unicodedata.normalize('NFKD', text)
        return text

    def normalize_whitespace(self, text: str) -> str:
        if not text:
            return ""
        clean_html = re.sub(r'<.*?>', ' ', text)
        return re.sub(r'\s+', ' ', clean_html).strip()

    def canonicalize_company(self, company: str) -> str:
        if not company:
            return "Unknown"
        text = self.decode_html_and_unicode(company)
        for pattern, canonical in self.company_canonical_map.items():
            if re.search(pattern, text, flags=re.IGNORECASE):
                return canonical
        return self.normalize_whitespace(text).title()

    def canonicalize_title(self, title: str) -> str:
        if not title:
            return ""
        text = self.decode_html_and_unicode(title)
        for pattern, canonical in self.title_canonical_map.items():
            if re.search(pattern, text, flags=re.IGNORECASE):
                return canonical
        return self.normalize_whitespace(text).title()

    def apply_aliases(self, text: str) -> str:
        if not text:
            return ""
        for pattern, replacement in self.aliases.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    def normalize_salary(self, salary: str) -> str:
        if not salary:
            return ""
        salary = salary.lower()
        salary = re.sub(r'\b(\d+)\s*[kK]\b', r'\g<1>000', salary)
        salary = re.sub(r',', '', salary)
        return salary.strip()

    def normalize_location(self, location: str) -> str:
        if not location:
            return ""
        location = location.lower()
        location = re.sub(r'\b(bengaluru|blr)\b', 'bangalore', location)
        location = re.sub(r'\b(ncr)\b', 'delhi', location)
        return self.normalize_whitespace(location).title()

    def normalize_job(self, job: Job) -> NormalizedJob:
        raw_title = job.title or ""
        raw_company = job.company or ""
        raw_desc = job.description or ""
        raw_salary = job.salary or ""
        raw_loc = job.location or ""

        title = self.canonicalize_title(raw_title)
        company = self.canonicalize_company(raw_company)
        
        desc = self.decode_html_and_unicode(raw_desc)
        desc = self.normalize_whitespace(desc)
        desc = self.apply_aliases(desc)

        salary_norm = self.normalize_salary(raw_salary)
        location_norm = self.normalize_location(raw_loc)

        normalized_tags = [self.apply_aliases(self.normalize_whitespace(self.decode_html_and_unicode(str(t)))) for t in job.tags]

        return NormalizedJob(
            raw_job_id=job.job_id,
            title=title,
            company=company,
            location=location_norm,
            salary_raw=raw_salary,
            salary_normalized=salary_norm,
            description=desc,
            tags=normalized_tags,
            provider_name=getattr(job, 'provider_name', "Unknown"),
            posted_date=job.posted_date or ""
        )
