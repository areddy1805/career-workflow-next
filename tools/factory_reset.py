#!/usr/bin/env python3
"""
Factory Reset Utility for Career Workflow.

This script acts as the single source of truth for resetting the project's
runtime state. It safely removes generated artifacts, caches, ledgers,
and runtime diagnostics while strictly preserving source code, configuration,
and repository assets.
"""

import os
import shutil
import glob
import argparse
import sys
from pathlib import Path

# Always resolve paths relative to the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# -------------------------------------------------------------------------
# Targets
# -------------------------------------------------------------------------

DIRECTORIES_TO_CLEAR = [
    "artifacts/runs",
    "logs",
    "scheduler_logs",
    "data/responses",
    "data/ui_runtime",
    "data/cache",
]

# We use explicit globs/paths for files in data/ to avoid accidentally
# deleting anything unexpected.
FILES_TO_DELETE = [
    # SQLite Ledgers & Queues
    "data/application_ledger.db*",
    "data/workflow_queue.db*",
    "data/manual_jobs.db*",
    
    # Caches
    "data/job_search_cache.json",
    "data/score_cache.json",
    
    # Runtime & Diagnostics
    "data/manual_action_queue.json",
    "data/search_challenge_state.json",
    "data/provider_health_history.json",
    "data/questionnaire_telemetry.csv",
    
    # Legacy State Files (may exist from older versions)
    "data/runtime_state.json",
    "data/scheduler_state.json",
    "data/pipeline_state.json",
    "data/heartbeat.json",
    "data/raw_jobs.csv",
    "data/scored_jobs.csv",
    "data/applied_jobs.csv",
]

# Directories that must exist for the application to start properly
REQUIRED_DIRECTORIES = [
    "artifacts/runs",
    "logs",
    "data/responses",
    "data/ui_runtime",
    "data/cache",
]

# Specifically called out as preserved for the summary report
PRESERVED_PATHS = [
    "config/",
    "config/candidate_profile.py",
    "config/search_strategy.yaml",
]

def clear_directory(dir_path: Path) -> int:
    """Removes all contents of a directory but keeps the directory itself."""
    deleted_count = 0
    if not dir_path.exists():
        return deleted_count

    for item in dir_path.iterdir():
        if item.name == ".gitkeep":
            continue
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            deleted_count += 1
        except Exception as e:
            print(f"Warning: Failed to delete {item}: {e}")
            
    return deleted_count

def main():
    parser = argparse.ArgumentParser(description="Factory Reset Utility for Career Workflow.")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation and execute immediately")
    args = parser.parse_args()

    if not args.yes:
        print("⚠️  WARNING\n")
        print("This operation will permanently delete all generated runtime state, caches,")
        print("application history, logs, runtime artifacts, and other local runtime data.\n")
        print("Source code and configuration will NOT be modified.\n")
        print("To continue, type:\n")
        print("YES\n")
        print("or press Ctrl+C to abort.")
        
        try:
            response = input("> ")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(0)

        if response != "YES":
            print("Aborted. Factory reset canceled.")
            sys.exit(0)

    print("\nExecuting Factory Reset...\n")
    
    deleted_items = []
    
    # 1. Clear contents of specific directories
    for dir_rel in DIRECTORIES_TO_CLEAR:
        dir_path = PROJECT_ROOT / dir_rel
        if dir_path.exists() and dir_path.is_dir():
            count = clear_directory(dir_path)
            if count > 0:
                deleted_items.append(f"{dir_rel}/* ({count} items)")
                
    # 2. Delete specific files and globs
    for file_pattern in FILES_TO_DELETE:
        pattern_path = str(PROJECT_ROOT / file_pattern)
        for filepath in glob.glob(pattern_path):
            path_obj = Path(filepath)
            if path_obj.exists() and path_obj.is_file():
                try:
                    path_obj.unlink()
                    deleted_items.append(path_obj.name)
                except Exception as e:
                    print(f"Warning: Failed to delete {path_obj.name}: {e}")

    # 3. Print Deleted Summary
    print("Deleted:")
    if deleted_items:
        for item in deleted_items:
            print(f"✓ {item}")
    else:
        print("- No runtime files found to delete.")
        
    print("\nPreserved:")
    for item in PRESERVED_PATHS:
        print(f"✓ {item}")
        
    # 4. Recreate Required Directories
    created_items = []
    for dir_rel in REQUIRED_DIRECTORIES:
        dir_path = PROJECT_ROOT / dir_rel
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                created_items.append(f"{dir_rel}/")
            except Exception as e:
                print(f"Warning: Failed to create directory {dir_rel}: {e}")
                
    if created_items:
        print("\nCreated:")
        for item in created_items:
            print(f"✓ {item}")

    print("\nFactory reset complete.")

if __name__ == "__main__":
    main()
