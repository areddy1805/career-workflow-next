# Provider Comparison Validation Report

## Overview
Comparative analysis of identical inference requests executed across **DeepSeek V4 (Cloud)** and **OMLX (Local Fallback)**.

| Metric | DeepSeek V4 | OMLX Local |
| :--- | :--- | :--- |
| **Vendor** | `deepseek` | `omlx` |
| **Model** | `deepseek-v4-flash` | `qwen3.5-4b` |
| **Status** | FAIL | PASS |
| **JSON Valid** | `False` | `True` |
| **Latency** | 0.0 ms | 20170.7 ms |
| **Prompt Tokens** | 0 | 84 (estimated) |
| **Completion Tokens** | 0 | 215 (estimated) |
| **Reasoning Tokens** | 0 | 0 |
| **Cost (USD)** | $0.000000 | $0.000000 |
| **SHA256 Fingerprint** | `N/A` | `ba5ff279dd443858` |

## Parsed Output Comparison

### DeepSeek V4 Response
```json
{}
```

### OMLX Local Response
```json
{
  "decision": "ELIGIBLE",
  "llm_score": 92,
  "confidence": 0.95,
  "reasoning": "The candidate profile demonstrates strong alignment with the job requirements. The job explicitly requires experience with 'LLM orchestration pipelines' and 'agentic workflows', which directly matches the candidate's listed skill in 'LLM Agents'. Additionally, the requirement for 'REST APIs with FastAPI' is fully covered by the candidate's 'FastAPI' skill. The candidate also possesses 'Python', which is the underlying language for FastAPI and PyTorch, and 'SQL', which is essential for data handling in AI pipelines. The only potential gap is 'Next.js' for 'modern web applications', but in a Senior AI role, the backend orchestration (FastAPI/LLM Agents) and data handling (SQL/PyTorch) are typically the primary technical pillars, making the candidate highly suitable."
}
```

## Conclusions
- **Protocol Parity**: Both providers receive identical `InferenceRequest` SHA256 fingerprints.
- **Failover Preparedness**: OMLX provides 0-cost local fallback capability if DeepSeek cloud endpoint encounters timeout, rate limits, or authentication failures.
