import time
from datetime import datetime
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.live import Live

from src.runtime.models import RunViewModel


class OperatorConsole:
    def __init__(self, state_manager, refresh_rate: float = 0.5):
        self.state_manager = state_manager
        self.refresh_rate = refresh_rate
        import sys
        self.console = Console(file=sys.__stdout__)
        self.layout = self._make_layout()

    def _make_layout(self) -> Layout:
        """Create the dashboard layout."""
        layout = Layout(name="root")
        
        layout.split_column(
            Layout(name="row1", size=6),
            Layout(name="row2", size=11),
            Layout(name="row3", size=10),
            Layout(name="row4", size=8),
            Layout(name="row5", size=10)
        )
        
        layout["row1"].split_row(
            Layout(name="header", ratio=2),
            Layout(name="health", ratio=1)
        )
        layout["row2"].split_row(
            Layout(name="pipeline", ratio=2),
            Layout(name="inference", ratio=1)
        )
        layout["row3"].split_row(
            Layout(name="timeline", ratio=2),
            Layout(name="efficiency", ratio=1)
        )
        layout["row4"].split_row(
            Layout(name="notifications", ratio=2),
            Layout(name="decision", ratio=1)
        )
        layout["row5"].split_row(
            Layout(name="terminal", ratio=2),
            Layout(name="errors", ratio=1)
        )
        return layout

    def render_header(self, model: RunViewModel) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column()
        grid.add_column(justify="right")
        grid.add_row(
            f"[bold blue]{model.header.title}[/bold blue] v{model.version}",
            f"Run ID: [bold]{model.header.run_id}[/bold]"
        )
        grid.add_row(
            f"Profile: [cyan]{model.header.profile}[/cyan]",
            f"Status: [bold green]{model.header.run_status}[/bold green]"
        )
        return Panel(grid, title="Header", border_style="blue")

    def render_health(self, model: RunViewModel) -> Panel:
        table = Table.grid(expand=True)
        table.add_column()
        table.add_column(justify="right")
        
        def render_status(s):
            sl = str(s).lower()
            if sl in ("healthy", "success", "connected", "wal", "writable", "available"):
                return f"🟢 {s.capitalize()}"
            elif sl == "unknown":
                return "⚪ Unknown"
            return f"🔴 {s}"
            
        for provider, health in model.health.providers.items():
            table.add_row(provider.capitalize(), render_status(health.status))
            
        table.add_row("Browser", render_status(model.health.browser.status))
        table.add_row("SQLite", render_status(model.health.sqlite.status))
        table.add_row("Artifacts", render_status(model.health.artifacts.status))
        
        return Panel(table, title="Health", border_style="green")

    def render_pipeline(self, model: RunViewModel) -> Panel:
        table = Table.grid(expand=True)
        table.add_column()
        table.add_column(justify="right")
        
        total = model.progress.total_stages
        completed = model.progress.completed_stages
        percent = int((completed / total * 100)) if total > 0 else 0
        
        # Simple progress bar using characters
        bar_len = 30
        filled = int((percent / 100) * bar_len)
        bar = ("█" * filled) + ("░" * (bar_len - filled))
        
        table.add_row(f"[bold]{model.progress.current_stage}[/bold]", f"{percent}%")
        table.add_row(f"[cyan]{bar}[/cyan]", "")
        
        # Throughput
        table.add_row("Jobs Acquired", str(model.progress.jobs_acquired))
        table.add_row("Jobs Classified", str(model.progress.jobs_classified))
        table.add_row("Jobs Applied", str(model.progress.jobs_applied))
        
        if model.progress.current_stage == "Acquisition" and model.progress.current_operation:
            table.add_row("", "")
            table.add_row("[bold cyan]Current Activity[/bold cyan]", "")
            table.add_row(f"{model.progress.current_operation}", "")
            table.add_row(f"Query: [yellow]{model.progress.active_query}[/yellow]", f"{model.progress.query_index}/{model.progress.total_queries}")
            table.add_row("Page", f"{model.progress.current_page}/{model.progress.total_pages}")
            table.add_row("Acquired", str(model.progress.acquired_count))
        
        return Panel(table, title="Pipeline Progress", border_style="cyan")

    def render_inference(self, model: RunViewModel) -> Panel:
        table = Table.grid(expand=True)
        table.add_column()
        table.add_column(justify="right")
        
        table.add_row("Requests", str(model.inference.requests))
        table.add_row("Tokens", f"{model.inference.tokens:,}")
        table.add_row("Cost", f"${model.inference.cost:.4f}")
        table.add_row("Avg Latency", f"{model.inference.average_latency:.2f}s")
        table.add_row("Fallbacks", str(model.inference.fallbacks))
        
        return Panel(table, title="Inference", border_style="magenta")

    def render_efficiency(self, model: RunViewModel) -> Panel:
        table = Table.grid(expand=True)
        table.add_column()
        table.add_column(justify="right")
        
        table.add_row("Deterministic Rejects", str(model.efficiency.deterministic_rejections))
        table.add_row("Semantic Reuse", str(model.efficiency.semantic_reuse))
        table.add_row("LLM Avoidance", f"{model.efficiency.llm_avoidance_rate:.1f}%")
        
        return Panel(table, title="Efficiency", border_style="yellow")

    def render_decision(self, model: RunViewModel) -> Panel:
        table = Table.grid(expand=True)
        table.add_column()
        table.add_column(justify="right")
        
        d = model.decision_summary
        table.add_row("Jobs Discovered", str(d.jobs_found))
        table.add_row("Already Processed", str(d.already_processed))
        table.add_row("New Candidates", str(d.new_candidates))
        table.add_row("Description Duplicates", str(d.description_duplicates))
        table.add_row("LLM Reviewed", str(d.llm_reviewed))
        table.add_row("Qualified", str(d.qualified))
        table.add_row("Submitted", str(d.submitted))
        
        return Panel(table, title="Outcome Ledger", border_style="cyan")

    def render_timeline(self, model: RunViewModel) -> Panel:
        text = Text()
        # Show last 8 events
        for event in model.timeline[-8:]:
            time_str = event.timestamp.split("T")[-1][:8]
            color = "white"
            if event.level == "success": color = "green"
            elif event.level == "error": color = "red"
            text.append(f"[{time_str}] ", style="dim")
            text.append(f"{event.message}\n", style=color)
            
        return Panel(text, title="Timeline", border_style="white")

    def render_notifications(self, model: RunViewModel) -> Panel:
        text = Text()
        for event in model.notifications[-5:]:
            time_str = event.timestamp.split("T")[-1][:8]
            text.append(f"[{time_str}] ⚠ {event.message}\n", style="yellow")
        return Panel(text, title="Notifications", border_style="yellow")

    def render_errors(self, model: RunViewModel) -> Panel:
        text = Text()
        for event in model.errors[-3:]:
            time_str = event.timestamp.split("T")[-1][:8]
            text.append(f"[{time_str}] {event.message}\n", style="red bold")
        return Panel(text, title="Errors", border_style="red")

    def render_terminal(self, model: RunViewModel) -> Panel:
        text = Text()
        for entry in model.terminal_logs[-8:]:
            color = "white"
            if entry.level == "ERROR": color = "red"
            elif entry.level == "WARNING": color = "yellow"
            elif entry.level == "DEBUG": color = "dim"
            text.append(f"{entry.message}\n", style=color)
        return Panel(text, title="Terminal", border_style="grey50")

    def _update_layout(self):
        model = self.state_manager.get_view_model()
        self.layout["header"].update(self.render_header(model))
        self.layout["health"].update(self.render_health(model))
        self.layout["pipeline"].update(self.render_pipeline(model))
        self.layout["inference"].update(self.render_inference(model))
        self.layout["efficiency"].update(self.render_efficiency(model))
        self.layout["decision"].update(self.render_decision(model))
        self.layout["timeline"].update(self.render_timeline(model))
        self.layout["notifications"].update(self.render_notifications(model))
        self.layout["errors"].update(self.render_errors(model))
        self.layout["terminal"].update(self.render_terminal(model))
        return self.layout

    def start(self):
        with Live(self.layout, console=self.console, refresh_per_second=1/self.refresh_rate, screen=True) as live:
            try:
                while True:
                    live.update(self._update_layout())
                    time.sleep(self.refresh_rate)
                    # Check if pipeline is done
                    model = self.state_manager.get_view_model()
                    if model.progress.status in ("SUCCESS", "FAILED", "PARTIAL"):
                        # Keep screen up a bit, then exit
                        time.sleep(2)
                        break
            except KeyboardInterrupt:
                pass
