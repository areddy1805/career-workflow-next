import hashlib
import json
from typing import Any

def dict_hash(dictionary: dict[str, Any]) -> str:
    """SHA256 hash of a dictionary."""
    dhash = hashlib.sha256()
    encoded = json.dumps(dictionary, sort_keys=True, separators=(',', ':')).encode('utf-8')
    dhash.update(encoded)
    return dhash.hexdigest()

import re
import unicodedata

def normalize_text(text: str) -> str:
    """Normalizes text by stripping HTML, collapsing whitespace, unicodedata, and lowercasing."""
    if not text:
        return ""
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Unicode normalize
    text = unicodedata.normalize('NFKD', text)
    # Lowercase
    text = text.lower()
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def compute_llm_fingerprint(
    provider: str,
    job_id: str,
    title: str,
    company: str,
    normalized_description: str,
    model_name: str,
    prompt_version: str,
    classifier_version: str,
    pipeline_version: str,
    search_strategy_version: str,
    ranking_version: str,
) -> str:
    parts = [
        provider,
        job_id,
        normalize_text(title),
        normalize_text(company),
        normalize_text(normalized_description),
        model_name,
        prompt_version,
        classifier_version,
        pipeline_version,
        search_strategy_version,
        ranking_version,
    ]
    return hashlib.sha256("||".join(str(p) for p in parts).encode('utf-8')).hexdigest()

def compute_embedding_fingerprint(
    embedding_model: str,
    normalized_text: str,
) -> str:
    parts = [
        embedding_model,
        normalize_text(normalized_text)
    ]
    return hashlib.sha256("||".join(str(p) for p in parts).encode('utf-8')).hexdigest()

def compute_detail_fetch_fingerprint(
    provider: str,
    job_id: str,
    description_hash_or_etag: str,
) -> str:
    parts = [
        provider,
        job_id,
        description_hash_or_etag
    ]
    return hashlib.sha256("||".join(str(p) for p in parts).encode('utf-8')).hexdigest()

def compute_http_fingerprint(
    url: str,
    etag: str,
    last_modified: str,
    request_params: dict[str, Any],
) -> str:
    params_str = dict_hash(request_params) if request_params else ""
    parts = [
        url,
        etag,
        last_modified,
        params_str
    ]
    return hashlib.sha256("||".join(str(p) for p in parts).encode('utf-8')).hexdigest()
