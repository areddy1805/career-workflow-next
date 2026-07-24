import json
import logging
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticsConfig:
    enabled: bool = True
    watchdog_seconds: int = 60
    thread_dump: bool = True
    progress_interval: int = 10


@dataclass
class WorkerState:
    worker_id: int
    task_id: str
    start_time: float
    current_phase: str = "started"
    timings: Dict[str, float] = field(default_factory=dict)
    
    def elapsed(self) -> float:
        return time.time() - self.start_time


class ExecutionMonitor:
    def __init__(self, name: str, total_tasks: int, run_dir: Path, config: Optional[DiagnosticsConfig] = None):
        self.name = name
        self.total_tasks = total_tasks
        self.run_dir = run_dir
        self.config = config or DiagnosticsConfig()
        
        self.submitted = 0
        self.running = 0
        self.completed = 0
        self.failed = 0
        
        self.lock = threading.Lock()
        self.active_workers: Dict[int, WorkerState] = {}
        
        self.durations: list[float] = []
        self.start_time = time.time()
        self.last_progress_time = self.start_time
        
        self.monitor_running = False
        self.monitor_thread: Optional[threading.Thread] = None

    def start(self):
        if not self.config.enabled:
            return
            
        self.diagnostics_dir = self.run_dir / "diagnostics"
        self.diagnostics_dir.mkdir(parents=True, exist_ok=True)
        
        self.monitor_running = True
        self.monitor_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        self.monitor_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)

    def task_started(self, task_id: str):
        thread_id = threading.get_ident()
        with self.lock:
            self.submitted += 1
            self.running += 1
            self.active_workers[thread_id] = WorkerState(
                worker_id=thread_id,
                task_id=task_id,
                start_time=time.time()
            )

    def task_phase(self, phase: str):
        thread_id = threading.get_ident()
        with self.lock:
            if thread_id in self.active_workers:
                worker = self.active_workers[thread_id]
                now = time.time()
                # Record timing of the previous phase
                worker.timings[worker.current_phase] = now - worker.start_time
                worker.current_phase = phase

    def task_completed(self, success: bool = True):
        thread_id = threading.get_ident()
        now = time.time()
        with self.lock:
            if thread_id in self.active_workers:
                worker = self.active_workers.pop(thread_id)
                duration = now - worker.start_time
                self.durations.append(duration)
                
            self.running -= 1
            if success:
                self.completed += 1
            else:
                self.failed += 1
            
            self.last_progress_time = now

    def _watchdog_loop(self):
        last_heartbeat = time.time()
        
        while self.monitor_running:
            try:
                time.sleep(1)
                now = time.time()
                
                with self.lock:
                    elapsed_since_progress = now - self.last_progress_time
                    elapsed_since_heartbeat = now - last_heartbeat
                    
                    # Check for stall
                    if elapsed_since_progress > self.config.watchdog_seconds:
                        if self.running > 0:
                            self._handle_stall(elapsed_since_progress)
                            # Reset progress time to avoid dumping every second
                            self.last_progress_time = now
                    
                    # Heartbeat
                    if elapsed_since_heartbeat >= self.config.progress_interval:
                        self._print_heartbeat()
                        last_heartbeat = now
            except Exception as e:
                import sys, traceback
                print(f"[WATCHDOG ERROR] {e}", file=sys.stderr)
                traceback.print_exc()
                try:
                    with open(self.diagnostics_dir / "watchdog_error.txt", "a") as f:
                        f.write(traceback.format_exc() + "\n")
                except:
                    pass
                time.sleep(5)

    def _print_heartbeat(self):
        avg = sum(self.durations) / len(self.durations) if self.durations else 0.0
        remaining = self.total_tasks - self.completed - self.failed
        
        oldest = 0.0
        if self.active_workers:
            oldest = max(w.elapsed() for w in self.active_workers.values())
            
        msg = (
            f"[{self.name.upper()}] "
            f"Completed: {self.completed}/{self.total_tasks} | "
            f"Remaining: {remaining} | "
            f"Workers: {self.running} | "
            f"Oldest: {oldest:.1f}s | "
            f"Avg: {avg:.2f}s"
        )
        logger.info(msg)
        import sys
        print(msg, file=sys.stderr)
        sys.stderr.flush()

    def _handle_stall(self, elapsed: float):
        import sys
        msg = f"============================\n{self.name.upper()} WATCHDOG\n============================"
        logger.error(msg)
        print(msg, file=sys.stderr)
        
        total_elapsed = time.time() - self.start_time
        remaining = self.total_tasks - self.completed - self.failed
        avg = sum(self.durations) / len(self.durations) if self.durations else 0.0
        slowest = max(self.durations) if self.durations else 0.0
        
        logger.error(f"Elapsed: {total_elapsed:.1f}s")
        logger.error(f"Progress: {self.completed} / {self.total_tasks}")
        logger.error(f"Running: {self.running} workers")
        logger.error(f"Remaining: {remaining}")
        logger.error(f"Average fetch: {avg:.2f} sec")
        logger.error(f"Slowest fetch: {slowest:.2f} sec\n")
        
        # Prepare snapshot data
        snapshot: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "elapsed_seconds": total_elapsed,
                "completed": self.completed,
                "total": self.total_tasks,
                "running": self.running,
                "remaining": remaining,
                "average_duration": avg,
                "slowest_duration": slowest
            },
            "workers": []
        }
        
        thread_dump_lines = ["============================\n", f"{self.name.upper()} THREAD DUMP\n", "============================\n"]
        
        frames = sys._current_frames()
        for thread_id, worker in self.active_workers.items():
            duration = worker.elapsed()
            logger.error(f"Worker {thread_id}")
            logger.error(f"Task ID: {worker.task_id}")
            logger.error(f"Status: Running for {duration:.1f} sec")
            logger.error(f"Phase: {worker.current_phase}")
            
            frame = frames.get(thread_id)
            if frame:
                # Extract the top of the stack
                tb = traceback.extract_stack(frame)
                if tb:
                    current_func = tb[-1].name
                    logger.error(f"Current Function: {current_func}\n")
                
                thread_dump_lines.append(f"\n--- Thread {thread_id} (Task: {worker.task_id}, Running: {duration:.1f}s) ---\n")
                thread_dump_lines.extend(traceback.format_stack(frame))
            else:
                logger.error("Current Function: Unknown (No frame)\n")
                
            snapshot["workers"].append({
                "thread_id": thread_id,
                "task_id": worker.task_id,
                "elapsed_seconds": duration,
                "phase": worker.current_phase,
                "timings": worker.timings
            })
            
        if self.config.thread_dump:
            dump_file = self.diagnostics_dir / "thread_dump.txt"
            with open(dump_file, "a") as f:
                f.write(f"\n\nTimestamp: {datetime.now(timezone.utc).isoformat()}\n")
                f.write("".join(thread_dump_lines))
                
        snapshot_file = self.diagnostics_dir / f"{self.name}_snapshot.json"
        with open(snapshot_file, "w") as f:
            json.dump(snapshot, f, indent=2)
            
        logger.error(f"Diagnostics written to {self.diagnostics_dir}")
