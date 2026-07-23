# Search Profile Engine Configuration Guide

Welcome to the Search Profile Engine! This configuration layer completely decouples career targeting from Python backend code. You can target new roles, add new technologies, and filter out bad jobs by simply managing YAML files.

## Directory Structure

- `user_profile.yaml`: The entry point. Defines active search profiles, locations, and global settings.
- `search_profiles/`: Contains role definitions (e.g. `applied_ai_engineer.yaml`). Each profile maps titles to required technologies and negative keywords.
- `technology_profiles/`: Contains shared dictionaries of technical keywords (e.g. `llm.yaml`, `backend.yaml`). This prevents duplicating keywords across roles.
- `company_profiles/`: Contains shared dictionaries of company groups (e.g. `startups.yaml`, `ai_labs.yaml`).
- `negative_profiles/`: Contains shared dictionaries of exclusion keywords (e.g. `legacy_it.yaml`, `non_technical.yaml`) to filter out irrelevant roles (e.g. SAP, Manual QA).
- `search/planner.yaml`: Global algorithm settings for query generation (e.g. caps and limits).

## How Query Generation Works (The Planner)

When the pipeline starts, the `SearchPlanner` reads these files and dynamically generates an optimized, deduplicated list of Search Queries. 

The algorithm generates Cartesian products in order of priority:
1. **Role-Centric**: "Applied AI Engineer"
2. **Role + Technology**: "Applied AI Engineer LangChain"

### Handling Negatives
If a profile references `negative_groups` (e.g., `legacy_it`), the planner automatically appends exclusions to the query string (e.g. `-SAP -Salesforce Admin -BPO`), keeping irrelevant results out of the acquisition layer entirely.

### Preventing Query Explosion
To respect API rate limits, the `planner.yaml` enforces a `max_queries_per_profile` cap (default 10). The planner deduplicates globally, ensuring the most valuable searches are prioritized without spamming the backend.

## How to Add a New Role

1. **Create the Role Profile**
   Create a new file `config/search_profiles/my_new_role.yaml`:
   ```yaml
   titles:
     - My New Role
     - Alternative Title
   preferred_technologies:
     - cloud
     - backend
   negative_groups:
     - legacy_it
   weight: 1.1
   ```

2. **Activate It**
   Add it to `config/user_profile.yaml`:
   ```yaml
   active_profiles:
     - my_new_role
   ```

3. **(Optional) Add New Tech Groups**
   If the role requires new skills, define them in `config/technology_profiles/` and reference them in your role profile.

That's it! No Python changes required. The pipeline will automatically generate queries for your new role on the next run.
