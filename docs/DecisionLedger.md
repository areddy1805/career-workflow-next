# Decision Ledger

The Decision Ledger (`data/application_ledger.db`) is the authoritative state layer and single source of truth for Career Workflow. 

## Design

Built on **SQLite (WAL Mode)**, the ledger records every:
- Job discovery source
- Classification result
- LLM fit score
- Application execution attempt
- Lifecycle status transition

## Traceability

No job changes state without an explicit transaction in the ledger. 

This strict accounting ensures that the system never enters an infinite loop, never duplicates an application, and provides a perfect paper trail for every decision made by the AI.

The `Pipeline Explorer` and `Audit System` directly query this ledger to generate execution manifests and diagnostic reports.
