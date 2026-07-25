# Learning Platform

The Learning Platform (`src/core/learning/`) provides advanced analytical and ranking features that go beyond the basic rules engine.

## Core Features

- **Cost Engine (`cost_engine.py`)**: Computes real-time inference costs by analyzing token usage metrics (prompt vs completion) against provider-specific pricing tables (e.g., DeepSeek vs OMLX).
- **ML Ranker (`ml_ranker.py`)**: Experimental framework for advanced job ranking based on candidate preference history.
- **Ledger Integrations (`ledger.py`)**: Utilities for the Learning Platform to extract historical performance data from the Decision Ledger to train and adjust scoring thresholds over time.
