import sys
import time
from rich.live import Live
from rich.console import Console

# Shim mock
class Shim:
    def write(self, text):
        pass
    def flush(self):
        pass

sys.stdout = Shim()

console = Console(file=sys.__stdout__, force_terminal=True, force_interactive=True)
with Live("Testing Live...", console=console, refresh_per_second=4):
    time.sleep(1)
print("Done", file=sys.__stdout__)
