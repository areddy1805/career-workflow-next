import os
import time
from pathlib import Path

from rich.console import Console, RenderableType
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich import box
from rich.align import Align

from src.runtime.models import RunViewModel


class OperatorConsole:
    def __init__(self, refresh_rate: float = 1.0):
        self.refresh_rate = refresh_rate
        import sys
        self.console = Console(file=sys.__stdout__)
        self.current_json_path = Path(os.getenv("RUNTIME_DIR", "data/ui_runtime")) / "current.json"
        self.log_path: Path | None = None
        
        # We will build layout dynamically per frame based on console dimensions
        self.layout = Layout(name="root")

    def _read_current_vm(self) -> RunViewModel:
        try:
            if self.current_json_path.exists():
                return RunViewModel.model_validate_json(
                    self.current_json_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return RunViewModel()

    def _create_panel(self, renderable: RenderableType, title: str = "") -> Panel:
        """Create a premium, minimalist panel with zero fluff."""
        return Panel(
            renderable,
            title=f"[bold bright_black]{title}[/]" if title else None,
            title_align="left",
            box=box.SIMPLE,
            border_style="bright_black",
            padding=(0, 1)
        )

    def render_header(self, model: RunViewModel) -> RenderableType:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right")

        # Title Row
        title_row = Text(model.header.title, style="bold white")
        title_row.append(f" v{model.version}", style="dim")
        
        # Status Pill
        status = model.header.run_status.upper()
        if status in ("RUNNING", "COMPLETED"):
            status_pill = Text(f" {status} ", style="bold black on bright_green")
        elif status == "FAILED":
            status_pill = Text(f" {status} ", style="bold white on bright_red")
        else:
            status_pill = Text(f" {status} ", style="bold black on bright_yellow")

        # Details Row (Adaptive to width)
        details = Text()
        w = self.console.width
        
        details.append(f"Profile: ", style="dim")
        details.append(f"{model.header.profile}", style="cyan")
        if w > 80:
            details.append(f"  Provider: ", style="dim")
            details.append(f"{model.header.provider}", style="cyan")
        details.append(f"  Mode: ", style="dim")
        details.append(f"{model.header.mode}", style="cyan")
        if w > 100:
            details.append(f"  Run ID: ", style="dim")
            details.append(f"{model.header.run_id}", style="bright_black")

        # Time
        time_text = Text()
        if model.progress.elapsed_seconds > 0:
            time_text.append(f"{int(model.progress.elapsed_seconds)}s elapsed", style="white")
        if model.progress.eta_seconds and model.progress.eta_seconds > 0:
            time_text.append(f" | {int(model.progress.eta_seconds)}s ETA", style="dim")

        grid.add_row(title_row, status_pill)
        grid.add_row(details, time_text)

        return Panel(grid, box=box.SIMPLE, border_style="bright_black", padding=(0, 1))

    def render_pipeline(self, model: RunViewModel) -> RenderableType:
        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)

        stages = ["Initialize", "Acquire", "Normalize", "Classify", "Rank", "Select", "Apply", "Complete"]
        w = self.console.width
        if w < 100:
            # Compress stages for smaller terminals
            stages = ["Init", "Acquire", "Norm", "Classify", "Rank", "Select", "Apply", "Done"]

        current_idx = -1
        # Map current stage back to compressed name for index finding
        long_to_short = {
            "initialize": 0, "acquire": 1, "normalize": 2, "classify": 3,
            "rank": 4, "select": 5, "apply": 6, "complete": 7,
            "done": 7, "init": 0, "norm": 2
        }
        c_stage_lower = model.progress.current_stage.lower()
        if c_stage_lower in long_to_short:
            current_idx = long_to_short[c_stage_lower]
            
        if current_idx == -1 and model.progress.current_stage == "Unknown":
            current_idx = 0

        stage_text = Text()
        for i, s in enumerate(stages):
            if i < current_idx:
                stage_text.append(f"✓ {s} ", style="green")
            elif i == current_idx:
                stage_text.append(f"○ {s} ", style="bold bright_white")
            else:
                stage_text.append(f"· {s} ", style="dim")
                
            if i < len(stages) - 1:
                stage_text.append("❯ ", style="bright_black")

        stats = Text()
        stats.append("Acq: ", style="dim").append(f"{model.progress.jobs_acquired} ", style="bold white")
        stats.append("Cls: ", style="dim").append(f"{model.progress.jobs_classified} ", style="bold white")
        stats.append("App: ", style="dim").append(f"{model.progress.jobs_applied} ", style="bold white")
        
        if w > 80:
            stats.append(f"  {model.progress.completed_stages}/{max(1, model.progress.total_stages)} stages", style="dim")

        grid.add_row(stage_text)
        grid.add_row("")
        grid.add_row(stats)

        return self._create_panel(grid, "PIPELINE PROGRESS")

    def render_metrics(self, model: RunViewModel) -> RenderableType:
        w = self.console.width
        cols = 4 if w >= 120 else 2 if w >= 80 else 1
        
        grid = Table.grid(expand=True, padding=(0, 4))
        for _ in range(cols): 
            grid.add_column(ratio=1)

        def _stat_row(label: str, val: str, val_style: str = "bold white") -> RenderableType:
            t = Table.grid(expand=True)
            t.add_column(style="bright_black")
            t.add_column(justify="right", style=val_style)
            t.add_row(label, val)
            return t

        outcomes = Table.grid(expand=True)
        outcomes.add_column()
        d = model.decision_summary
        outcomes.add_row(Text("Outcomes", style="bold bright_black"))
        outcomes.add_row(_stat_row("Found", str(d.jobs_found)))
        outcomes.add_row(_stat_row("Qualified", str(d.qualified)))
        outcomes.add_row(_stat_row("Selected", str(d.llm_reviewed)))
        outcomes.add_row(_stat_row("Applied", str(d.submitted), "bold bright_green"))
        outcomes.add_row(_stat_row("Rejected", str(d.rejected), "dim"))

        inference = Table.grid(expand=True)
        inference.add_column()
        i = model.inference
        inference.add_row(Text("Inference", style="bold bright_black"))
        inference.add_row(_stat_row("Requests", str(i.requests)))
        inference.add_row(_stat_row("Tokens", f"{i.tokens:,}", "cyan"))
        inference.add_row(_stat_row("Latency", f"{i.average_latency:.2f}s"))
        inference.add_row(_stat_row("Cost", f"${i.cost:.4f}", "yellow"))
        inference.add_row(_stat_row("Fallbacks", str(i.fallbacks), "red" if i.fallbacks > 0 else "dim"))

        efficiency = Table.grid(expand=True)
        efficiency.add_column()
        e = model.efficiency
        efficiency.add_row(Text("Efficiency", style="bold bright_black"))
        efficiency.add_row(_stat_row("Avoidance", f"{e.llm_avoidance_rate:.1%}", "bold bright_green"))
        efficiency.add_row(_stat_row("Cache Hits", str(e.cache_hits)))
        efficiency.add_row(_stat_row("Sem. Reuse", str(e.semantic_reuse)))
        efficiency.add_row(_stat_row("Det. Rej.", str(e.deterministic_rejections)))

        health = Table.grid(expand=True)
        health.add_column()
        health.add_row(Text("System Health", style="bold bright_black"))
        
        def dot(s: str) -> str:
            sl = s.lower()
            if sl in ("healthy", "success", "connected", "wal", "writable", "available", "ok"):
                return "[bright_green]●[/]"
            elif sl == "unknown":
                return "[bright_black]●[/]"
            return "[bright_red]●[/]"

        for p, h in model.health.providers.items():
            health.add_row(_stat_row(p.capitalize(), dot(h.status), ""))
        health.add_row(_stat_row("SQLite", dot(model.health.sqlite.status), ""))
        health.add_row(_stat_row("Browser", dot(model.health.browser.status), ""))
        health.add_row(_stat_row("Artifacts", dot(model.health.artifacts.status), ""))

        if cols == 4:
            grid.add_row(outcomes, inference, efficiency, health)
        elif cols == 2:
            grid.add_row(outcomes, inference)
            grid.add_row(Text(""), Text("")) # Spacer
            grid.add_row(efficiency, health)
        else:
            grid.add_row(outcomes)
            grid.add_row(inference)
            grid.add_row(efficiency)
            grid.add_row(health)

        return self._create_panel(grid, "")

    def render_activity(self, model: RunViewModel) -> RenderableType:
        t = Table.grid(expand=True)
        t.add_column(justify="center")
        
        if not model.timeline:
            t.add_row(Text("Waiting for activity...", style="dim italic"))
        else:
            latest = model.timeline[-1]
            t.add_row(Text(latest.message, style="bold cyan"))
            
        return self._create_panel(t, "CURRENT ACTIVITY")

    def render_timeline(self, model: RunViewModel) -> RenderableType:
        t = Table.grid(expand=True, padding=(0, 1))
        t.add_column(style="bright_black", width=10) # Time
        t.add_column(style="bright_black", width=2)  # Separator
        t.add_column(ratio=1)                        # Message
        t.add_column(justify="right", width=8)       # Status
        
        # Determine how many events fit
        h = self.console.height
        max_events = 6 if h > 35 else 3 if h > 25 else 1
        
        events = model.timeline[-max_events:]
        for ev in events:
            time_str = ev.timestamp.split("T")[-1][:8] if "T" in ev.timestamp else ev.timestamp
            
            color = "white"
            status_text = "OK"
            if ev.level == "success": 
                color = "green"
                status_text = "OK"
            elif ev.level == "error": 
                color = "red"
                status_text = "ERR"
            elif ev.level == "warning":
                color = "yellow"
                status_text = "WARN"
                
            msg = ev.message
            stage = ""
            if msg.startswith("[") and "]" in msg:
                idx = msg.find("]")
                stage = f"[{msg[1:idx]}]"
                msg = msg[idx+1:].strip()

            content = Text()
            if stage:
                content.append(f"{stage} ", style="cyan")
            content.append(msg, style=color)
            
            t.add_row(
                time_str,
                "│",
                content,
                Text(status_text, style=color)
            )
            
        return self._create_panel(t, "TIMELINE")

    def render_logs(self, model: RunViewModel) -> RenderableType:
        text = Text()
        
        # Adapt line count to screen height
        h = self.console.height
        lines_to_show = 10 if h > 40 else 5 if h > 30 else 3
        
        if self.log_path and self.log_path.exists():
            try:
                with open(self.log_path, 'rb') as f:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(size - 4096, 0), 0)
                    lines = f.read().decode('utf-8', errors='replace').splitlines()
                    
                for line in lines[-lines_to_show:]:
                    parts = line.split(" ", 2)
                    if len(parts) >= 3 and ":" in parts[0] and parts[1] in ("INFO", "ERROR", "WARN", "DEBUG"):
                        ts = parts[0]
                        lvl = parts[1]
                        msg = parts[2]
                        style = "bright_black"
                        lvl_style = "white"
                        if "ERROR" in lvl: lvl_style = "bold red"
                        elif "WARN" in lvl: lvl_style = "bold yellow"
                        elif "INFO" in lvl: lvl_style = "cyan"
                        
                        text.append(f"{ts} ", style="bright_black")
                        text.append(f"{lvl:<5} ", style=lvl_style)
                        text.append(f"{msg}\n", style=style if "DEBUG" in lvl else "white")
                    else:
                        style = "bright_black"
                        if "ERROR" in line: style = "red"
                        elif "WARN" in line: style = "yellow"
                        text.append(line + "\n", style=style)
            except Exception:
                text.append("Log read error\n", style="dim")
        else:
            text.append("Waiting for logs...\n", style="dim")
            
        return self._create_panel(text, "SYSTEM LOGS")

    def _update_layout(self):
        model = self._read_current_vm()
        h = self.console.height
        
        # Rebuild layout based on available height (Responsive Design for Terminal)
        self.layout = Layout(name="root")
        
        if h > 30:
            # Full Layout
            self.layout.split_column(
                Layout(name="header", size=4),
                Layout(name="pipeline", size=6),
                Layout(name="metrics", size=8),
                Layout(name="activity", size=4),
                Layout(name="timeline", size=8),
                Layout(name="logs", ratio=1, minimum_size=3)
            )
            self.layout["timeline"].update(self.render_timeline(model))
            self.layout["logs"].update(self.render_logs(model))
        elif h > 20:
            # Hide logs, compress timeline
            self.layout.split_column(
                Layout(name="header", size=4),
                Layout(name="pipeline", size=6),
                Layout(name="metrics", size=8),
                Layout(name="activity", size=4),
                Layout(name="timeline", ratio=1, minimum_size=4)
            )
            self.layout["timeline"].update(self.render_timeline(model))
        else:
            # Ultra compact: Hide timeline, logs, and activity
            self.layout.split_column(
                Layout(name="header", size=4),
                Layout(name="pipeline", size=6),
                Layout(name="metrics", ratio=1, minimum_size=6)
            )
            
        self.layout["header"].update(self.render_header(model))
        self.layout["pipeline"].update(self.render_pipeline(model))
        self.layout["metrics"].update(self.render_metrics(model))
        
        if h > 20:
            self.layout["activity"].update(self.render_activity(model))
            
        return self.layout

    def start(self, done_event=None):
        with Live(self.layout, console=self.console, refresh_per_second=1/self.refresh_rate, screen=True) as live:
            try:
                while True:
                    live.update(self._update_layout())
                    time.sleep(self.refresh_rate)
                    if done_event and done_event.is_set():
                        time.sleep(1)
                        break
                    model = self._read_current_vm()
                    if model.progress.status in ("SUCCESS", "FAILED", "PARTIAL"):
                        time.sleep(2)
                        break
            except KeyboardInterrupt:
                pass
