import sys
import os
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

class TeeLogger:
    """Tees output to both the original stream and a file."""
    def __init__(self, original_stream, log_file):
        self.original_stream = original_stream
        self.log_file = log_file

    def write(self, message):
        self.original_stream.write(message)
        self.log_file.write(message)
        self.original_stream.flush()
        self.log_file.flush()

    def flush(self):
        self.original_stream.flush()
        self.log_file.flush()

class ExecutionCapture:
    """
    Execution Replay Logger.
    
    Generates a shared Run ID and prepares the `artifacts/runs/<run_id>` directory.
    Captures stdout, stderr, environment, git commit, and command details to ensure
    the run can be perfectly replayed and inspected later.
    """
    def __init__(self, command_name: str, args: Dict[str, Any]):
        self.command_name = command_name
        self.args = args
        self.start_time = datetime.now(timezone.utc)
        self.run_id = self.start_time.strftime("%Y%m%dT%H%M%S%fZ")
        
        self.run_dir = Path("artifacts/runs") / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file_path = self.run_dir / "pipeline.log"
        self.log_file = open(self.log_file_path, "a", encoding="utf-8")
        
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
        self.exit_code = 0
        self.original_cw_run_id = os.environ.get("CW_RUN_ID")
        
        self._write_command()
        self._write_environment()
        self._write_git()

    def _write_command(self):
        with open(self.run_dir / "command.txt", "w", encoding="utf-8") as f:
            f.write(f"Command: {self.command_name}\n")
            f.write("Arguments:\n")
            for k, v in self.args.items():
                f.write(f"  {k}: {v}\n")
            f.write(f"Raw sys.argv: {' '.join(sys.argv)}\n")

    def _write_environment(self):
        with open(self.run_dir / "environment.txt", "w", encoding="utf-8") as f:
            f.write(f"Python Version: {sys.version}\n")
            f.write(f"Platform: {sys.platform}\n")
            f.write(f"CWD: {os.getcwd()}\n")
            f.write(f"VIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV', 'None')}\n")
            f.write("\nEnvironment Variables (Redacted):\n")
            for k, v in sorted(os.environ.items()):
                if any(sec in k.upper() for sec in ["SECRET", "KEY", "PASSWORD", "TOKEN", "CREDENTIAL"]):
                    f.write(f"{k}=***REDACTED***\n")
                else:
                    f.write(f"{k}={v}\n")

    def _write_git(self):
        with open(self.run_dir / "git.txt", "w", encoding="utf-8") as f:
            try:
                branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
                commit = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
                status = subprocess.check_output(["git", "status", "--porcelain"], stderr=subprocess.DEVNULL, text=True)
                
                f.write(f"Branch: {branch}\n")
                f.write(f"Commit: {commit}\n")
                f.write(f"Dirty: {'Yes' if status else 'No'}\n")
                if status:
                    f.write("\nStatus:\n" + status)
            except Exception as e:
                f.write(f"Git info capture failed: {e}\n")

    def _write_metadata(self):
        end_time = datetime.now(timezone.utc)
        duration = (end_time - self.start_time).total_seconds()
        
        manifest = {
            "run_id": self.run_id,
            "timestamp": self.start_time.isoformat(),
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration": duration,
            "command": self.command_name,
            "resolved_arguments": self.args,
            "execution_mode": "live" if self.args.get("live") else "dry",
            "acquisition_mode": self.args.get("acquisition_mode", "N/A"),
            "provider": self.args.get("provider", "N/A"),
            "exit_code": self.exit_code
        }
        
        with open(self.run_dir / "execution_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def _write_version_info(self):
        import hashlib
        
        def _hash_file(path: str) -> str | None:
            p = Path(path)
            if p.exists() and p.is_file():
                return hashlib.md5(p.read_bytes()).hexdigest()
            return None
            
        version_data = {
            "config_hashes": {
                "candidate_profile": _hash_file("config/candidate_profile.py"),
                "search_strategy": _hash_file("config/search_strategy.yaml"),
            },
            "code_hashes": {
                "pipeline.py": _hash_file("src/orchestration/pipeline.py"),
                "runner.py": _hash_file("control_center/runner.py")
            }
        }
        
        with open(self.run_dir / "version.json", "w", encoding="utf-8") as f:
            json.dump(version_data, f, indent=2)

    def __enter__(self):
        os.environ["CW_RUN_ID"] = self.run_id
        sys.stdout = TeeLogger(self.original_stdout, self.log_file)
        sys.stderr = TeeLogger(self.original_stderr, self.log_file)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.exit_code = 1
            if not isinstance(exc_val, SystemExit):
                import traceback
                traceback.print_exception(exc_type, exc_val, exc_tb)
            elif hasattr(exc_val, "code") and exc_val.code is not None:
                if isinstance(exc_val.code, int):
                    self.exit_code = exc_val.code
                else:
                    self.exit_code = 1
            
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        self.log_file.close()
        
        if self.original_cw_run_id is not None:
            os.environ["CW_RUN_ID"] = self.original_cw_run_id
        else:
            os.environ.pop("CW_RUN_ID", None)
            
        self._write_metadata()
        self._write_version_info()
        
        return False
