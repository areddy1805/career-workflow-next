import re
import yaml
from typing import List, Dict, Any, Optional, Set
from src.core.job_intelligence.normalized_job import NormalizedJob
from src.core.job_intelligence.metadata import JobMetadata
from src.core.job_intelligence.provenance import ExtractedField

class Tokenizer:
    """Tokenizer stage: Splits text into sanitized tokens and phrases."""
    @staticmethod
    def tokenize(text: str) -> Set[str]:
        if not text:
            return set()
        # Lowercase words and phrases
        words = set(re.findall(r'\b[\w\+\#\.-]+\b', text.lower()))
        return words

class Matcher:
    """Matcher stage: Finds matches between tokens and rule patterns."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def match_category(self, tokens: Set[str], mapping: Dict[str, List[str]]) -> Optional[tuple[str, str]]:
        for category, keywords in mapping.items():
            for kw in keywords:
                if kw in tokens:
                    return category, kw
        return None

    def match_list(self, tokens: Set[str], keywords: List[str]) -> List[tuple[str, str]]:
        matches = []
        for kw in keywords:
            if kw in tokens:
                matches.append((kw, f"stack.{kw}"))
        return matches

class Resolver:
    """Resolver stage: Resolves ambiguity and assigns confidence scores."""
    @staticmethod
    def resolve_category(match: Optional[tuple[str, str]], default_val: str = "Unknown") -> ExtractedField:
        if not match:
            return ExtractedField(value=default_val, confidence=0, rule="default", source="none")
        category, matched_token = match
        # If matched explicitly in title vs description, confidence varies, but baseline is 95%
        return ExtractedField(value=category, confidence=95, rule=f"keyword.{matched_token}", source="rules")

    @staticmethod
    def resolve_list(matches: List[tuple[str, str]]) -> ExtractedField:
        if not matches:
            return ExtractedField(value=[], confidence=0, rule="default", source="none")
        values = list(set([m[0] for m in matches]))
        return ExtractedField(value=values, confidence=90, rule="token_match", source="rules")

class JobExtractor:
    """
    Phase 0D Tokenizer-Matcher-Resolver Extractor.
    Extracts structured metadata with confidence scores and provenance rules.
    """
    def __init__(self, config_path: str = "config/extraction_rules.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        self.meta = self.config.get('meta', {})
        self.matcher = Matcher(self.config)

    def extract(self, job: NormalizedJob) -> JobMetadata:
        text = f"{job.title} {job.description} {' '.join(job.tags)}".lower()
        tokens = Tokenizer.tokenize(text)
        
        # Seniority
        sen_match = self.matcher.match_category(tokens, self.config.get('seniority', {}))
        seniority = Resolver.resolve_category(sen_match, "Unknown")
        
        # Work mode
        wm_match = self.matcher.match_category(tokens, self.config.get('work_mode', {}))
        work_mode = Resolver.resolve_category(wm_match, "Unknown")
        
        # Employment type
        emp_match = self.matcher.match_category(tokens, self.config.get('employment_type', {}))
        employment_type = Resolver.resolve_category(emp_match, "Unknown")
        
        # Stack
        stack_cfg = self.config.get('stack', {})
        tech_matches = self.matcher.match_list(tokens, stack_cfg.get('technologies', []))
        technologies = Resolver.resolve_list(tech_matches)
        
        fw_matches = self.matcher.match_list(tokens, stack_cfg.get('frameworks', []))
        frameworks = Resolver.resolve_list(fw_matches)
        
        db_matches = self.matcher.match_list(tokens, stack_cfg.get('databases', []))
        databases = Resolver.resolve_list(db_matches)
        
        cloud_matches = self.matcher.match_list(tokens, stack_cfg.get('cloud', []))
        cloud = Resolver.resolve_list(cloud_matches)
        
        ai_matches = self.matcher.match_list(tokens, stack_cfg.get('ai_keywords', []))
        ai_keywords = Resolver.resolve_list(ai_matches)
        
        company = ExtractedField(value=job.company, confidence=99 if job.company != "Unknown" else 0, rule="canonicalizer", source="normalizer")
        provider = ExtractedField(value=job.provider_name, confidence=100, rule="provider_id", source="ingestion")
        location = ExtractedField(value=[job.location] if job.location else [], confidence=95 if job.location else 0, rule="normalizer", source="normalizer")
        
        return JobMetadata(
            company=company,
            provider=provider,
            seniority=seniority,
            employment_type=employment_type,
            work_mode=work_mode,
            location=location,
            technologies=technologies,
            frameworks=frameworks,
            databases=databases,
            cloud=cloud,
            ai_keywords=ai_keywords,
            rule_version=self.meta.get('version', '1.0.0'),
            rule_checksum=self.meta.get('checksum', '')
        )
