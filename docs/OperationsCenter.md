# Operations Center

The Career Workflow Operations Center is a 16-surface React application that provides a unified control plane for pipeline execution, ledger inspection, and system audits.

## Architecture

- **Backend**: FastAPI (`api/`) serving clean, decoupled REST endpoints.
- **Frontend**: React 19, TypeScript, Vite, TailwindCSS, and shadcn/ui (`frontend/`).
- **State**: Zustand & React Query.

## Key Surfaces

- **/dashboard**: High-level execution metrics and active pipeline state.
- **/pipeline**: Launch and control active executions.
- **/ledger**: Deep dive into the SQLite decision ledger.
- **/intelligence**: Funnel conversion charts, LLM token costs, and response velocity.
- **/explorer**: Interactive decision trees for specific pipeline runs.
- **/audit**: Automated diagnostic reports on system health and AI integration.
- **/system**: Pre-flight system checks and database lock states.
