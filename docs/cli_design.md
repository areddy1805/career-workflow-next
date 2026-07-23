# Unified Operations CLI Design

## 1. Current Entry Points & Service Layer Integration
The CLI will NOT directly execute or duplicate pipeline logic. It will act as the canonical operational control plane, communicating directly with the project's existing service layer (`control_center` modules).

Existing entry points to be unified:
- `run_pipeline.py` & `run_scheduler.py` -> Managed via Runner Service (`control_center.runner`).
- `application_report.py` & `monitor_applications.py` -> Managed via UI/CLI shared analytics services.
- `tools/factory_reset.py` -> Managed via runtime reset services.
- `tools/validate_jobspy.py` & `src/cache/cli.py` -> Managed via diagnostics and cache services.

## 2. Existing CLI Arguments
Here is the comprehensive list of existing arguments discovered across all entry points:

### Pipeline / Runner
- `--live`: Enable live application submission. (Default: False / dry-run)
- `--test`: Run in test mode (fast, deterministic, minimal acquisition).
- `--max-applications` (int): Optional attempt cap.
- `--acquisition-mode` (choices: `full`, `incremental`, Default: `full`)
- `--confirm-live` (str): Confirmation string (must be `APPLY_LIVE`).
- `--canary`: Force a live run to at most one application.
- `--force-live`: Bypass search challenge cooldowns and force a live acquisition.
- `--provider` (choices: `all`, `naukri`, `jobspy`, Default: `all`)

### Scheduler
- `--run-now`, `--interactive`, `--session-hours` (float), `--incremental` (int), `--force-live`

### Cache / JobSpy Validation
- `cache [stats|clear|vacuum|verify]`
- `validate jobspy` with keyword, location, site, results, country.

## 3. Existing Providers & Runtime Modes
The pipeline currently supports:
- Providers: `all`, `naukri`, `jobspy`. (Future providers not included yet).
- Modes: `dry`, `live`, `test`, `full`, `incremental`, `canary`, `scheduler`, `interactive`.

## 4. CLI Architecture (Backend Services)
The CLI (`cw`) and the React UI will act as two frontends over the same backend services.
- **Runner Service**: `cw run` and `cw schedule` will invoke `control_center.runner` to manage pipeline executions.
- **Run Inspector**: `cw inspect` will use `control_center.run_inspector`.
- **Diagnostics**: `cw doctor` will use `control_center.diagnostics`.
- **Artifact System**: The CLI will use the existing `artifacts/runs/` system. It will not create a parallel logging hierarchy.

## 5. Execution Replay Logging & Run IDs
Logging will be treated as an "Execution Replay". We should be able to answer what happened without rerunning anything.
- **Shared Run ID**: The Runner Service will generate a single Run ID. This ID will be passed to the pipeline so that logs, artifacts, diagnostics, and analytics all refer to the exact same execution.
- **Execution Log Capture**: Within `artifacts/runs/<run_id>/`, we will store `pipeline.log`, `metadata.json`, `command.txt`, `environment.txt`, and `git.txt`.
- **Reproducibility**: The logs will capture the exact command run, git commit, config state, provider, acquisition mode, terminal output, and generated artifacts.

## 6. cw inspect
`cw inspect` will be the most-used command for understanding "What happened?". It will provide a rich summary:
- Run ID, Duration, Provider, Acquisition Mode
- Jobs Acquired
- Impossible Filter Stats
- Evidence Confidence
- Inference Cache Hits & Calls
- Applications Submitted, Policy Rejects
- Failures & Warnings
- Artifacts generated, Log paths, Git Commit

## 7. cw doctor
`cw doctor` will dynamically discover capabilities instead of hardcoding checks. E.g., it will inspect the active config to determine which inference backend is in use, rather than assuming OMLX forever.

## 8. Migration Plan
1. **Runner Update**: Update `control_center.runner` and pipeline startup to accept and use an externally provided Run ID (e.g., via `CW_RUN_ID` environment variable).
2. **CLI Implementation**: Build `cw` CLI (`src/cli/main.py`) using Typer.
3. **Log Capture**: Implement the Execution Replay logger in the CLI wrapper to capture context before handing off to the Runner Service, saving directly to `artifacts/runs/<run_id>/`.
4. **Inspect & Doctor**: Implement `cw inspect` and `cw doctor` leveraging `control_center` services.
