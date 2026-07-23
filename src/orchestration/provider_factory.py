import os
from colorama import Fore, Style
from src.client.naukri_client import NaukriLoginClient
from src.client.job_client import NaukriJobClient
from src.acquisition.providers.jobspy_provider import JobSpyProvider, JobSpyConfig
from src.acquisition.config import load_acquisition_config


def initialize_providers(provider_mode: str = "all") -> dict:
    """
    Initializes and returns a dictionary of active JobProviders based on configuration
    and the requested provider_mode.
    """
    acq_config = load_acquisition_config()
    jobspy_raw = acq_config.get("providers", {}).get("jobspy", {})
    naukri_raw = acq_config.get("providers", {}).get("naukri", {})

    naukri_enabled = naukri_raw.get("enabled", True)
    jobspy_enabled = jobspy_raw.get("enabled", False)

    run_naukri = (provider_mode == "naukri") or (
        provider_mode == "all" and naukri_enabled
    )
    run_jobspy = (provider_mode == "jobspy") or (
        provider_mode == "all" and jobspy_enabled
    )

    providers = {}

    print("\n" + "=" * 58)
    print("ACQUISITION PROVIDER MODE")
    print("=" * 58)
    print(f"\nMode        : {provider_mode}\n")
    print(f"Naukri      : {'Enabled' if run_naukri else 'Disabled'}\n")
    print(f"JobSpy      : {'Enabled' if run_jobspy else 'Disabled'}\n")
    print("=" * 58 + "\n")

    if run_naukri:
        username = os.environ.get("NAUKRI_USERNAME", "")
        password = os.environ.get("NAUKRI_PASSWORD", "")
        try:
            login_client = NaukriLoginClient(username, password)
            login_client.login()
            jc = NaukriJobClient(login_client)
            providers["naukri"] = jc
        except Exception as exc:
            print(
                f"{Fore.RED}Failed to initialize Naukri client: {exc}{Style.RESET_ALL}"
            )

    if run_jobspy:
        try:
            jobspy_cfg = JobSpyConfig.from_dict(jobspy_raw)
            jobspy_cfg.enabled = True
            providers["jobspy"] = JobSpyProvider(jobspy_cfg)
        except Exception as exc:
            print(
                f"\n  {Fore.YELLOW}"
                f"JobSpy config parse error: {exc}"
                f"{Style.RESET_ALL}"
            )

    return providers
