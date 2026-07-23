import os
import time
from datetime import datetime, timezone, timedelta
import pytest
from src.cache.cache_manager import CacheManager
from src.cache.fingerprint import normalize_text, compute_llm_fingerprint, compute_http_fingerprint

def test_fingerprint_normalization():
    # Test HTML stripping and unicode normalization
    text1 = "<p>Hello <b>World</b></p>"
    text2 = "Hello World"
    assert normalize_text(text1) == normalize_text(text2)
    
    # Test whitespace collapsing
    text3 = "Hello     World\n  Foo"
    text4 = "Hello World Foo"
    assert normalize_text(text3) == normalize_text(text4)
    
    fp1 = compute_llm_fingerprint("prov", "job1", "  Dev  ", "comp", "  <div>Python   </div>", "m1", "p1", "c1", "pi1", "s1", "r1")
    fp2 = compute_llm_fingerprint("prov", "job1", "dev", "comp", "python", "m1", "p1", "c1", "pi1", "s1", "r1")
    
    assert fp1 == fp2

def test_cache_hits_misses(tmp_path):
    manager = CacheManager(db_path=str(tmp_path / "test_cache.db"))
    
    # Initially miss
    res1 = manager.llm.get("fp_1")
    assert res1 is None
    
    # Set value
    manager.llm.set("fp_1", "prov", "job_1", "raw", "parsed", "m1", 100.0, 10)
    
    # Now hit
    res2 = manager.llm.get("fp_1")
    assert res2 is not None
    assert res2["raw_response"] == "raw"
    assert res2["parsed_response"] == "parsed"

def test_http_cache_ttl(tmp_path, monkeypatch):
    manager = CacheManager(db_path=str(tmp_path / "test_ttl.db"))
    
    fp_http = compute_http_fingerprint("https://example.com", "etag1", "lastmod1", {})
    
    # Set with an expiration 1 second in the past
    expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    
    manager.http.set(
        fingerprint=fp_http,
        url="https://example.com",
        method="GET",
        status_code=200,
        headers_json="{}",
        content="Hello",
        expires_at=expires_at
    )
    
    # It should be expired
    assert manager.http.get(fp_http) is None
    
    # Set with an expiration in the future
    expires_at_future = datetime.now(timezone.utc) + timedelta(seconds=10)
    manager.http.set(
        fingerprint=fp_http,
        url="https://example.com",
        method="GET",
        status_code=200,
        headers_json="{}",
        content="Hello",
        expires_at=expires_at_future
    )
    
    # It should be a hit
    assert manager.http.get(fp_http) is not None
