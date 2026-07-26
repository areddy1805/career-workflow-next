import sys
import os
import json

# Add project root to sys.path
sys.path.insert(0, os.path.abspath("."))

from src.acquisition.providers.hiringcafe_provider import HiringCafeProvider, HiringCafeConfig
from src.acquisition.base_provider import ProviderRunMetrics

def run_live_validation():
    config = HiringCafeConfig(
        enabled=True,
        max_pages=2,
        verification_mode=True
    )
    
    provider = HiringCafeProvider(config)
    
    queries = [
        {"keyword":"software engineer"},
        {"keyword":"ai engineer"},
        {"keyword":"python"},
        {"keyword":"software engineer", "matched_technology":"Python"},
        {"keyword":"software engineer", "remote": "yes"},  # using raw keys
    ]
    
    for q in queries:
        print(f"\n--- Testing Query: {q} ---")
        jobs = provider.fetch_jobs([q])
        print(f"Acquired {len(jobs)} jobs for query {q}")
        
    print("\nHealth Summary:")
    print(json.dumps(provider.health_summary(), indent=2))

if __name__ == "__main__":
    run_live_validation()
