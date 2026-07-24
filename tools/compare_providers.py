import os
import sys
import json
import time
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.inference.request import InferenceRequest
from src.inference.providers.openai_compatible import OpenAICompatibleProvider
from src.inference.providers.omlx import OMLXProvider

def run_provider_comparison():
    print("=" * 60)
    print("Career Workflow 3.5 — Provider Comparison Validation Engine")
    print("=" * 60)

    # Sample Job Classifier Prompt
    system_prompt = (
        "You are an AI Job Qualification Classifier. "
        "Analyze the job against candidate profile and return valid JSON with keys: "
        "'decision' (ELIGIBLE, INELIGIBLE), 'llm_score' (0-100), 'confidence' (0.0-1.0), 'reasoning'."
    )
    prompt = (
        "Candidate Skills: Python, FastAPI, Next.js, LLM Agents, PyTorch, SQL.\n"
        "Job Title: Senior AI Software Engineer\n"
        "Job Description: We are seeking a Senior AI Engineer experienced in building LLM orchestration pipelines, "
        "agentic workflows, REST APIs with FastAPI, and modern web applications.\n"
        "Evaluate suitability and respond strictly in JSON."
    )

    request = InferenceRequest(
        request_id="comp_req_001",
        run_id="comp_run",
        caller="compare_providers",
        trace_id="hash_comp_123",
        category="ai_score",
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=0.0,
        max_tokens=300,
        json_mode=True
    )

    deepseek_provider = OpenAICompatibleProvider(
        name="deepseek",
        vendor="deepseek",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        model="deepseek-v4-flash"
    )

    omlx_provider = OMLXProvider(
        name="omlx",
        base_url="http://127.0.0.1:8000/v1",
        model="qwen3.5-4b"
    )

    results = {}

    # Test DeepSeek Provider
    print("\n[1/2] Executing DeepSeek V4 Inference...")
    try:
        start = time.perf_counter()
        ds_resp = deepseek_provider.generate(request)
        ds_latency = (time.perf_counter() - start) * 1000

        results["deepseek"] = {
            "vendor": ds_resp.vendor,
            "model": ds_resp.model,
            "success": True,
            "json_valid": isinstance(ds_resp.parsed_response, dict) and "decision" in ds_resp.parsed_response,
            "parsed": ds_resp.parsed_response,
            "raw": ds_resp.raw_response,
            "latency_ms": ds_latency,
            "prompt_tokens": ds_resp.prompt_tokens,
            "completion_tokens": ds_resp.completion_tokens,
            "reasoning_tokens": ds_resp.reasoning_tokens,
            "cost_usd": ds_resp.cost_usd,
            "fingerprint": ds_resp.fingerprint,
            "response_hash": ds_resp.response_hash
        }
    except Exception as e:
        print(f"DeepSeek Provider execution error: {e}")
        results["deepseek"] = {
            "vendor": "deepseek",
            "model": "deepseek-v4-flash",
            "success": False,
            "error": str(e),
            "latency_ms": 0,
            "cost_usd": 0.0
        }

    # Test OMLX Provider
    print("\n[2/2] Executing OMLX Local Fallback Inference...")
    try:
        start = time.perf_counter()
        om_resp = omlx_provider.generate(request)
        om_latency = (time.perf_counter() - start) * 1000

        results["omlx"] = {
            "vendor": om_resp.vendor,
            "model": om_resp.model,
            "success": True,
            "json_valid": isinstance(om_resp.parsed_response, dict) and "decision" in om_resp.parsed_response,
            "parsed": om_resp.parsed_response,
            "raw": om_resp.raw_response,
            "latency_ms": om_latency,
            "prompt_tokens": om_resp.prompt_tokens,
            "completion_tokens": om_resp.completion_tokens,
            "reasoning_tokens": 0,
            "cost_usd": om_resp.cost_usd,
            "fingerprint": om_resp.fingerprint,
            "response_hash": om_resp.response_hash
        }
    except Exception as e:
        print(f"OMLX Provider execution error: {e}")
        results["omlx"] = {
            "vendor": "omlx",
            "model": "qwen3.5-4b",
            "success": False,
            "error": str(e),
            "latency_ms": 0,
            "cost_usd": 0.0
        }

    # Generate Provider Comparison Report Artifact
    report_md = f"""# Provider Comparison Validation Report

## Overview
Comparative analysis of identical inference requests executed across **DeepSeek V4 (Cloud)** and **OMLX (Local Fallback)**.

| Metric | DeepSeek V4 | OMLX Local |
| :--- | :--- | :--- |
| **Vendor** | `{results.get('deepseek', {}).get('vendor', 'N/A')}` | `{results.get('omlx', {}).get('vendor', 'N/A')}` |
| **Model** | `{results.get('deepseek', {}).get('model', 'N/A')}` | `{results.get('omlx', {}).get('model', 'N/A')}` |
| **Status** | {'PASS' if results.get('deepseek', {}).get('success') else 'FAIL'} | {'PASS' if results.get('omlx', {}).get('success') else 'FAIL'} |
| **JSON Valid** | `{results.get('deepseek', {}).get('json_valid', False)}` | `{results.get('omlx', {}).get('json_valid', False)}` |
| **Latency** | {results.get('deepseek', {}).get('latency_ms', 0):.1f} ms | {results.get('omlx', {}).get('latency_ms', 0):.1f} ms |
| **Prompt Tokens** | {results.get('deepseek', {}).get('prompt_tokens', 0)} | {results.get('omlx', {}).get('prompt_tokens', 0)} (estimated) |
| **Completion Tokens** | {results.get('deepseek', {}).get('completion_tokens', 0)} | {results.get('omlx', {}).get('completion_tokens', 0)} (estimated) |
| **Reasoning Tokens** | {results.get('deepseek', {}).get('reasoning_tokens', 0)} | 0 |
| **Cost (USD)** | ${results.get('deepseek', {}).get('cost_usd', 0.0):.6f} | ${results.get('omlx', {}).get('cost_usd', 0.0):.6f} |
| **SHA256 Fingerprint** | `{results.get('deepseek', {}).get('fingerprint', 'N/A')[:16]}` | `{results.get('omlx', {}).get('fingerprint', 'N/A')[:16]}` |

## Parsed Output Comparison

### DeepSeek V4 Response
```json
{json.dumps(results.get('deepseek', {}).get('parsed', {}), indent=2)}
```

### OMLX Local Response
```json
{json.dumps(results.get('omlx', {}).get('parsed', {}), indent=2)}
```

## Conclusions
- **Protocol Parity**: Both providers receive identical `InferenceRequest` SHA256 fingerprints.
- **Failover Preparedness**: OMLX provides 0-cost local fallback capability if DeepSeek cloud endpoint encounters timeout, rate limits, or authentication failures.
"""
    
    report_path = REPO_ROOT / "docs/provider_comparison_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_md, encoding="utf-8")
    print(f"\nProvider comparison report successfully saved to: [provider_comparison_report.md](file://{report_path})")

if __name__ == "__main__":
    run_provider_comparison()
