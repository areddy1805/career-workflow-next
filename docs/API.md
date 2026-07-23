# Control Plane API Specification

The **FastAPI Control Plane** (`api/main.py`, `api/routes.py`) provides REST endpoints for the React Operations Console, pipeline control, queue management, metrics inspection, and runtime diagnostics.

All routes are mounted under the `/api` prefix.

---

## Endpoint Summary Table

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/dashboard` | Aggregated dashboard summary metrics, lifecycle states, latest run, system health, and provider status. |
| `GET` | `/api/jobs` | Complete list of applications from ledger enriched with cache metadata and canonical URLs. |
| `GET` | `/api/jobs/{job_id}` | Detailed overview and timeline events for a specific job application. |
| `GET` | `/api/runs` | List of pipeline execution run history (up to 100 runs). |
| `GET` | `/api/runs/{run_id}` | Detailed summary record for a single execution run. |
| `GET` | `/api/runtime` | Live system runtime state (scheduler, pipeline process, UI status, and latest run metrics). |
| `GET` | `/api/settings` | Safe runtime environment configuration parameters. |
| `GET` | `/api/artifacts` | List of available execution run artifact directories and states. |
| `GET` | `/api/pipeline/state` | Current running status and active process logs of the background pipeline worker. |
| `POST` | `/api/pipeline/launch` | Triggers a new pipeline execution run (dry run or live mode). |
| `GET` | `/api/queues/manual-review` | Pending items requiring human manual review. |
| `GET` | `/api/queues/external-apply` | Jobs requiring external web browser application execution. |
| `GET` | `/api/queues/other-action` | Uncategorized or custom workflow action queue items. |
| `POST` | `/api/queues/{job_id}/transition` | Transitions a job workflow status (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `SKIPPED`, `DISMISSED`). |
| `POST` | `/api/queues/{job_id}/move` | Moves a job between workflow source queues (`manual_review`, `external_apply`). |
| `POST` | `/api/queues/manual` | Adds a user-created manual job entry directly into the workflow queue. |
| `GET` | `/api/search-intelligence` | Active search profiles, location targets, and generated query matrices. |
| `GET` | `/api/runs/{run_id}/artifacts` | List of artifact JSON/text filenames for a specific run. |
| `GET` | `/api/runs/{run_id}/artifacts/{file_name}` | Content of a specific run artifact file. |

---

## Selected Endpoint Contracts

### 1. Dashboard (`GET /api/dashboard`)

#### Response Example:
```json
{
  "summary": {
    "total_applications": 142,
    "applied_count": 88,
    "rejected_count": 34,
    "pending_count": 20
  },
  "lifecycle": [
    { "status": "APPLIED", "count": 88 },
    { "status": "REJECTED", "count": 34 }
  ],
  "latest_run": {
    "run_id": "20260719T080000Z",
    "status": "COMPLETED",
    "started_at": "2026-07-19T08:00:00Z"
  },
  "system_health": {
    "disk_space": "ok",
    "scheduler": "active"
  },
  "upcoming_executions": [],
  "top_companies": ["Acme Corp", "Tech Solutions"],
  "provider_health": {
    "naukri": "healthy",
    "jobspy": "healthy"
  }
}
```

### 2. Launch Pipeline (`POST /api/pipeline/launch`)

#### Request Body (`PipelineLaunchRequest`):
```json
{
  "live": false,
  "max_applications": 10,
  "canary": false,
  "force_live": false
}
```

#### Response Example:
```json
{
  "status": "Pipeline launched"
}
```

### 3. Add Manual Job (`POST /api/queues/manual`)

#### Request Body (`ManualJobRequest`):
```json
{
  "title": "Senior AI Engineer",
  "company": "Anthropic",
  "location": "Remote",
  "source": "LinkedIn Direct",
  "source_url": "https://www.linkedin.com/jobs/view/123456",
  "priority": "HIGH",
  "notes": "Referred by team member"
}
```

#### Response Example:
```json
{
  "status": "Job added"
}
```
