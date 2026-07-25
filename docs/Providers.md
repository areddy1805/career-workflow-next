# Providers & Job Acquisition

Job Acquisition in Career Workflow is designed as a resilient, multi-provider matrix that degrades safely.

## Supported Providers

- **Naukri**: Native API integration.
- **JobSpy**: Headless scraping framework powering Indeed, LinkedIn, and Google Jobs.

## Challenges & Caching

Instead of blindly retrying failing scraping attempts, the `Acquisition Orchestrator` detects challenges (e.g., CAPTCHAs, rate limits) and transitions the provider into a `Challenge Cooldown` state.

During cooldown, the pipeline intelligently falls back to the **Search Cache**, ensuring the pipeline can still process and score previously acquired jobs without stalling the execution run.
