# Inference Platform

The Inference Platform manages LLM evaluation, fallbacks, and token budgeting.

## Provider Architecture (`src/inference/`)

Career Workflow is built around an `OpenAICompatibleProvider` abstraction that seamlessly routes requests to multiple vendors:

1. **DeepSeek (Primary)**
   - Used for the heavy lifting of candidate-aware job scoring.
   - Exceptionally cost-effective for high-volume context analysis.

2. **OMLX (Local Fallback)**
   - Used as a fallback when remote APIs rate limit or fail.
   - Powered by local `qwen3.5-4b` models.

3. **OpenRouter / OpenAI**
   - Can be substituted natively via `ProviderManager`.

## Inference Routing & Telemetry

The `InferenceRouter` tracks metrics and dynamically handles failovers. 
The system tracks detailed telemetry, allowing the `Pipeline Intelligence` subsystem to visualize token usage and API costs in real time.
