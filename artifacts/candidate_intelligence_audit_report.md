# Candidate Intelligence Audit & Scoring Integration Report

## 1. Repository Audit Report
| File / Asset | Information Contained | Authoritative | Status | Current Consumers | Recommended Action |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `config/candidate_profile.py` | CTC, Notice period, Experience breakdown (Angular 5y, Node 3y, Python 3y, GenAI 3y, RAG 3y, Azure 3y), Locations | YES | Authoritative Baseline | `pipeline.py`, `legacy_apply_agent.py`, `test_apply_questionnaire.py` | Retain as primary dict source; load into `CandidateIntelligence`. |
| `config/candidate_evidence.py` | Factual grounding for certifications (Azure AI Engineer Associate AI-102), GenAI capabilities, safe questionnaire answers | YES | Authoritative Evidence | `apply_questionnaire.py`, `hybrid_resolver.py` | Retain as capability & cert evidence store; load into `CandidateIntelligence`. |
| `config/search_strategy.yaml` | Search queries, target job titles (AI Engineer, GenAI Engineer, LLM Engineer), target frameworks (LangChain, OpenAI, Azure OpenAI) | YES | Authoritative Strategy | `SearchPlanner`, `JobSpy` | Feed target role families and framework preferences into `CandidateIntelligence`. |
| `config/user_profile.yaml` | Target CTC (3,000,000 INR), preferred locations (Pune, Remote), active profiles (ai, fde) | YES | Authoritative Overrides | Ingestion scripts | Consolidate preferences into `CandidateIntelligence`. |
| `src/core/candidate/profile.py` | Intermediate `CandidateProfile` dataclass | NO | Obsolete | Feature extractors (Release 3.1.5) | Replace with `CandidateIntelligence`. |

---

## 2. Candidate Intelligence Inventory
- **Resume & Capabilities**:
  - Primary: `python` (3y), `angular` (5y), `typescript` (5y), `node` (3y), `azure` (3y), `fastapi` (2y), `docker` (4y).
  - Secondary: `sql` (1y), `aws` (1y), `kubernetes`, `postgresql`, `ci_cd`.
  - Emerging/AI: `genai` (3y), `llm` (3y), `rag` (3y), `agentic_ai` (3y), `vector_db` (3y), `langchain` (2y), `langgraph` (2y), `mcp` (1y).
- **Verified Certifications**:
  - `Microsoft Certified: Azure AI Engineer Associate (AI-102)`
- **Career Strategy**:
  - Target Roles: AI Engineer, GenAI Engineer, LLM Engineer, Applied AI Engineer, Forward Deployed Engineer.
  - Objective: Transition to production GenAI, RAG, and Agentic AI engineering.
- **Preferences & Compensation**:
  - Current CTC: 16 LPA | Target CTC: 26-30 LPA (~$120,000 USD)
  - Notice Period: 30 days
  - Locations: Pune (Current/Preferred), Remote, Hybrid, Bengaluru, Hyderabad, Mumbai, Chennai.
  - Work Modes: FTE, Remote, Hybrid, 1-year contract acceptable.
- **Avoid & Deal Breakers**:
  - Avoid: `dotnet_only`, `java_only`, `legacy_php`, `c_embedded`.
  - Deal Breakers: Onsite outside preferred city, night shift.

---

## 3. Duplicate & Obsolete Information Report
- **Duplication**: Location preferences existed in `candidate_profile.py`, `user_profile.yaml`, and `search_strategy.yaml`. Consolidated into `CandidateIntelligence.preferred_locations`.
- **Obsolete**: `src/core/candidate/profile.py` had hardcoded fallback tuples. Upgraded to `CandidateIntelligence.from_repository_sources()`.

---

## 4. Gap Analysis
| Candidate Attribute | Previously Used by Scorer? | Currently Used by Candidate Intelligence Scorer? | Impact |
| :--- | :--- | :--- | :--- |
| **Azure AI Engineer Associate (AI-102)** | ✗ No | **✓ YES** (`azure_ai_cert_boost` +10.0 pts) | Directly boosts Azure AI Engineer jobs |
| **3y GenAI & RAG Experience** | ✗ Partial (keyword only) | **✓ YES** (`ai_transition_score` 15.0 wt) | Prioritizes LLM/RAG roles matching transition goals |
| **LangChain & LangGraph Experience** | ✗ No | **✓ YES** (`agentic_ai_relevance` 12.0 wt) | Accurately scores Agentic AI engineering roles |
| **Angular 5y & Node 3y Deep Stack** | ✗ No | **✓ YES** (`required_skill_coverage` 15.0 wt) | High confidence for full-stack engineering roles |
| **Target CTC (26 LPA / $120k)** | ✗ No | **✓ YES** (`salary_score` 9.0 wt) | Penalizes low-ball offers (<16 LPA) |

---

## 5. Candidate Intelligence Consolidation
All candidate data sources are now unified into a single canonical model:
`config/candidate_profile.py` + `config/candidate_evidence.py` + `config/user_profile.yaml`
⬇
`CandidateIntelligence.from_repository_sources()` (`src/core/candidate/intelligence.py`)
⬇
`DeterministicPipelineRunner` & Scorer

---

## 6. Enhanced Feature Integration
- **`azure_ai_cert_boost`**: Checks `verified_certifications` for AI-102 certification when evaluating Azure/AI roles (+10 points boost).
- **`required_skill_coverage`**: Evaluates primary, secondary, and emerging candidate skills against job requirements.
- **`ai_transition_score`**: Measures alignment between the job's AI keywords and candidate's 3-year GenAI/RAG experience.

---

## 7. Updated Feature Weighting
Hierarchical Family Weighting enforced in `HierarchicalScoringEngine`:
- **Eligibility**: 40% (Notice period, Location match, Certification alignment, Work authorization)
- **Compatibility**: 25% (Skill coverage, Tech stack fit, Learning effort estimate)
- **Preference**: 20% (AI transition score, Agentic AI relevance, Salary match)
- **Market Quality**: 10% (Company quality, Product vs Service)
- **Risk**: 5% (Missing salary, Ambiguous title)

---

## 8. Updated Explainability
Every job score emits a transparent explainability artifact:
- `Candidate Intelligence Hash`: 16-character SHA-256 fingerprint of canonical candidate state.
- `Score Bucket`: Exceptional / Strong / Good / Borderline / Reject.
- `Resume Delta`: Strong Matches, Transferable Skills, Missing Skills, Learning Cost (`LOW`/`MEDIUM`/`HIGH`), Recommendation.

---

## 9. Benchmark Comparison
- **Test Suite Execution**: 7 test suites passed in **0.20 seconds**.
- **LLM Call Reduction**: Maintained **86.2% reduction** (1,088 jobs -> 150 LLM candidates).
- **Score Calibration**: Spreads scores naturally across the 5 distribution buckets.

---

## 10. Final Architecture Summary
`ProviderJob -> NormalizedJob -> JobMetadata -> CandidateIntelligence (Canonical) -> FeatureVector -> CandidateScore -> DecisionRecord`
