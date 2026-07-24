import re
import yaml
from typing import List, Dict, Any, Optional, Set, Tuple
from src.core.job_intelligence.normalized_job import NormalizedJob
from src.core.job_intelligence.metadata import JobMetadata
from src.core.job_intelligence.provenance import ExtractedField

class Tokenizer:
    @staticmethod
    def tokenize(text: str) -> List[Tuple[str, int, int]]:
        """Returns list of (token, start_char, end_char)."""
        if not text:
            return []
        matches = []
        for m in re.finditer(r'\b[\w\+\#\.-]+\b', text.lower()):
            matches.append((m.group(0), m.start(), m.end()))
        return matches

class Matcher:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def match_category(self, tokens: List[Tuple[str, int, int]], mapping: Dict[str, List[str]]) -> Optional[Tuple[str, str, Tuple[int, int]]]:
        for category, keywords in mapping.items():
            for kw in keywords:
                for token, start, end in tokens:
                    if kw == token:
                        return category, kw, (start, end)
        return None

    def match_list(self, tokens: List[Tuple[str, int, int]], keywords: List[str]) -> List[Tuple[str, str, Tuple[int, int]]]:
        matches = []
        for kw in keywords:
            for token, start, end in tokens:
                if kw == token:
                    matches.append((kw, f"stack.{kw}", (start, end)))
        return matches

class Resolver:
    @staticmethod
    def resolve_category(match: Optional[Tuple[str, str, Tuple[int, int]]], rule_ver: str, default_val: str = "Unknown") -> ExtractedField:
        if not match:
            return ExtractedField(value=default_val, normalized_value=default_val, rule_id="default", rule_version=rule_ver, source_span=(0, 0), confidence=0)
        category, matched_token, span = match
        return ExtractedField(value=category, normalized_value=category.lower(), rule_id=f"keyword.{matched_token}", rule_version=rule_ver, source_span=span, confidence=95)

    @staticmethod
    def resolve_list(matches: List[Tuple[str, str, Tuple[int, int]]], rule_ver: str) -> ExtractedField:
        if not matches:
            return ExtractedField(value=[], normalized_value=[], rule_id="default", rule_version=rule_ver, source_span=(0, 0), confidence=0)
        values = list(set([m[0] for m in matches]))
        min_start = min([m[2][0] for m in matches])
        max_end = max([m[2][1] for m in matches])
        return ExtractedField(value=values, normalized_value=[v.lower() for v in values], rule_id="token_match", rule_version=rule_ver, source_span=(min_start, max_end), confidence=90)

class JobExtractor:
    def __init__(self, config_path: str = "config/extraction_rules.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        self.meta = self.config.get('meta', {})
        self.rule_version = self.meta.get('version', '1.2.0')
        self.matcher = Matcher(self.config)

    def extract(self, job: NormalizedJob) -> JobMetadata:
        text = f"{job.title} {job.description} {' '.join(job.tags)}".lower()
        tokens = Tokenizer.tokenize(text)
        
        sen_match = self.matcher.match_category(tokens, self.config.get('seniority', {}))
        seniority = Resolver.resolve_category(sen_match, self.rule_version, "Unknown")
        
        wm_match = self.matcher.match_category(tokens, self.config.get('work_mode', {}))
        work_mode = Resolver.resolve_category(wm_match, self.rule_version, "Unknown")
        
        emp_match = self.matcher.match_category(tokens, self.config.get('employment_type', {}))
        employment_type = Resolver.resolve_category(emp_match, self.rule_version, "Unknown")
        
        stack_cfg = self.config.get('stack', {})
        tech_matches = self.matcher.match_list(tokens, stack_cfg.get('technologies', []))
        technologies = Resolver.resolve_list(tech_matches, self.rule_version)
        
        fw_matches = self.matcher.match_list(tokens, stack_cfg.get('frameworks', []))
        frameworks = Resolver.resolve_list(fw_matches, self.rule_version)
        
        db_matches = self.matcher.match_list(tokens, stack_cfg.get('databases', []))
        databases = Resolver.resolve_list(db_matches, self.rule_version)
        
        cloud_matches = self.matcher.match_list(tokens, stack_cfg.get('cloud', []))
        cloud = Resolver.resolve_list(cloud_matches, self.rule_version)
        
        ai_matches = self.matcher.match_list(tokens, stack_cfg.get('ai_keywords', []))
        ai_keywords = Resolver.resolve_list(ai_matches, self.rule_version)
        
        company = ExtractedField(value=job.company, normalized_value=job.company.lower(), rule_id="canonicalizer", rule_version=self.rule_version, source_span=(0, len(job.company)), confidence=99 if job.company != "Unknown" else 0)
        provider = ExtractedField(value=job.provider_name, normalized_value=job.provider_name.lower(), rule_id="provider_id", rule_version=self.rule_version, source_span=(0, len(job.provider_name)), confidence=100)
        location = ExtractedField(value=[job.location] if job.location else [], normalized_value=[job.location.lower()] if job.location else [], rule_id="normalizer", rule_version=self.rule_version, source_span=(0, len(job.location)), confidence=95 if job.location else 0)
        
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
            rule_version=self.rule_version,
            rule_checksum=self.meta.get('checksum', '')
        )
