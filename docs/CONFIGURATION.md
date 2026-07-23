# Configuration & Environment Reference Guide

This guide details all configuration options for **Career Workflow**, including environment variables, YAML profiles, and Python candidate evidence modules.

---

## 1. Environment Variables (`.env`)

Configuration settings loaded via `python-dotenv` at runtime.

| Variable Name | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `OMLX_BASE_URL` | String | **Required** | `http://127.0.0.1:8000/v1` | Base URL of local OpenAI-compatible LLM server (oMLX/vLLM/Ollama). |
| `OMLX_MODEL` | String | **Required** | `qwen3.5-4b` | Model name identifier used for AI fit scoring and questionnaire resolution. |
| `OMLX_API_KEY` | String | Optional | None | Optional API key for authenticating with local or remote LLM server. |
| `PORT` | Integer | Optional | `8000` | Port for FastAPI Control Plane backend. |
| `SELECTION_BUDGET` | Integer | Recommended | `10` | Maximum number of top-scored jobs selected for application per pipeline run. |
| `DEFAULT_MIN_SCORE` | Float | Recommended | `65.0` | Minimum AI fit score threshold (0.0 to 100.0) required for job selection. |
| `NAUKRI_USERNAME` | String | Optional | None | Naukri account login email/username for authenticated API client. |
| `NAUKRI_PASSWORD` | String | Optional | None | Naukri account login password. |
| `JOBSPY_PROXIES` | String | Optional | `""` | Comma-separated residential proxy URL string for JobSpy multi-site scraping. |

---

## 2. YAML Configuration Files (`config/`)

### 2.1 `config/user_profile.yaml`
Defines candidate target profiles, preferred locations, work modes, and target salary.

```yaml
active_profiles:
  - applied_ai_engineer
  - genai_engineer
  - llm_engineer
preferred_locations:
  - Pune
remote: true
salary_target: 3000000
work_modes:
  - Office
  - Hybrid
  - Remote
```

### 2.2 `config/search_strategy.yaml`
Controls acquisition provider priority, JobSpy scraping sites, rate limits, and budget allocations.

```yaml
strategy:
  spray_and_pray: true
  summary_fetch_budget: 500
  detail_fetch_budget: 500
  application_budget: 500
  rank_before_fetch: true

acquisition:
  provider_priority:
    - naukri
    - indeed
    - linkedin
    - google
  providers:
    naukri:
      enabled: true
    jobspy:
      enabled: true
      sites:
        - google
        - indeed
        - linkedin
      results_wanted: 20
      hours_old: 72
      cooldown_seconds: 2
```

---

## 3. Python Evidence & Profile Modules (`config/`)

### 3.1 `config/candidate_evidence.py`
Provides ground-truth candidate background information (years of experience, tech stack proficiency, notice period, location preference, education) used by the hybrid questionnaire resolution engine to auto-fill job application forms accurately.

### 3.2 `config/candidate_profile.py`
Defines candidate technical taxonomy, role titles, and technology keyword mappings for classification heuristic scoring.
