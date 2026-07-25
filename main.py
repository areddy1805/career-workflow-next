#!/usr/bin/env python3
"""
Career Workflow - Root Entrypoint

This script simply delegates to the main CLI application.
"""
import sys
import subprocess
from pathlib import Path

if __name__ == "__main__":
    repo_root = Path(__file__).parent
    cli_main = repo_root / "src" / "cli" / "main.py"
    
    if not cli_main.exists():
        print(f"Error: Could not find CLI entrypoint at {cli_main}")
        sys.exit(1)
        
    cmd = [sys.executable, str(cli_main)] + sys.argv[1:]
    
    try:
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        sys.exit(130)
