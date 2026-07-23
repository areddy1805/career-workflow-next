from typing import Any
from src.models.models import Job


class ApplicationEngine:
    """Interface for all application engines."""

    def supports(self, job: Job) -> bool:
        """Return True if this engine can process the given job."""
        raise NotImplementedError

    def prepare(self, job: Job) -> None:
        """Perform any preparation steps before applying."""
        raise NotImplementedError

    def apply(self, job: Job) -> Any:
        """Execute the application process for the given job."""
        raise NotImplementedError

    def verify(self, job: Job) -> bool:
        """Verify if the application was successfully submitted."""
        raise NotImplementedError

    def cleanup(self) -> None:
        """Clean up any resources used during the application process."""
        raise NotImplementedError
