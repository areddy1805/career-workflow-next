"""Build ai_fde_eval_v1: labeled evaluation dataset + baseline metrics.

Phase B (measurement only — no production changes).

Labels are HUMAN JUDGMENT grounded in the job description evidence and the
candidate profile (config/candidate_profile.py), NOT the current LLM score.
The current score/rank are recorded as observation fields, never as ground truth.

Ground-truth ontology:
  expected_role_family: AI_ENGINEERING | FDE | AI_FDE | AI_ADJACENT | GENERIC_ENGINEERING | NON_TARGET
  expected_ai_depth:    0..4
  expected_fde_band:    NONE | LOW | MEDIUM | HIGH | EXCELLENT
  expected_technical_fit: LOW | MEDIUM | HIGH | EXCELLENT
  expected_trajectory:  LOW | MEDIUM | HIGH | EXCELLENT
  expected_rank_band:   TOP | STRONG | MAYBE | LOW | REJECT

Outputs:
  artifacts/evaluation/ai_fde_eval_v1.json  (machine readable)
  artifacts/evaluation/ai_fde_eval_v1.md    (human auditable)
  prints baseline metrics to stdout
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POOL = ROOT / "artifacts" / "evaluation" / "eval_pool.json"
OUT_JSON = ROOT / "artifacts" / "evaluation" / "ai_fde_eval_v1.json"
OUT_MD = ROOT / "artifacts" / "evaluation" / "ai_fde_eval_v1.md"

# Expected label bands by bucket
AI_DEPTH = {"AI_ENGINEERING": 4, "FDE": 2, "AI_FDE": 4, "AI_ADJACENT": 2, "GENERIC_ENGINEERING": 1, "FALSE_POSITIVE": 1, "NON_TARGET": 0}
FDE_BAND = {"AI_ENGINEERING": "NONE", "FDE": "HIGH", "AI_FDE": "EXCELLENT", "AI_ADJACENT": "LOW", "GENERIC_ENGINEERING": "NONE", "FALSE_POSITIVE": "NONE", "NON_TARGET": "NONE"}
TECH_FIT = {"AI_ENGINEERING": "EXCELLENT", "FDE": "HIGH", "AI_FDE": "EXCELLENT", "AI_ADJACENT": "MEDIUM", "GENERIC_ENGINEERING": "LOW", "FALSE_POSITIVE": "LOW", "NON_TARGET": "NONE"}
TRAJECTORY = {"AI_ENGINEERING": "EXCELLENT", "FDE": "HIGH", "AI_FDE": "EXCELLENT", "AI_ADJACENT": "MEDIUM", "GENERIC_ENGINEERING": "LOW", "FALSE_POSITIVE": "LOW", "NON_TARGET": "LOW"}


# job_id -> (bucket, rationale, optional rank_band_override, optional ai_depth_override)
LABELS: dict[str, tuple] = {
    # ================= 20 EXCELLENT AI ENGINEERING =================
    "101225022689": ("AI_ENGINEERING", "Senior AI Engineer leading GenAI team; LLM/agentic/multimodal systems, OpenAI/Anthropic/Gemini/HF/LangChain. Core AI depth 4."),
    "070826911716": ("AI_ENGINEERING", "Azure AI/Vertex AI enterprise AI, LLMs, RAG, MCP, agent workflows, Python APIs. Hands-on GenAI depth 4."),
    "070826027682": ("AI_ENGINEERING", "ML/GenAI deployment, model serving, REST APIs, batch inference, Azure. AI depth 4."),
    "070826021427": ("AI_ENGINEERING", "TCS GenAI Developer: LLMs, RAG pipelines, Agentic AI architectures, fine-tune NLP models. Depth 4."),
    "070826016191": ("AI_ENGINEERING", "Avisoft AI Engineer building enterprise GenAI solutions. Depth 4."),
    "070826502023": ("AI_ENGINEERING", "AI/ML & Agentic AI Engineer (Innvonix). Depth 4; thin JD but title+skills strong."),
    "080826010441": ("AI_ENGINEERING", "Dynpro Agentic Developer: build & productize agentic AI. Depth 4."),
    "070826930192": ("AI_ENGINEERING", "Infosys Python GenAI Developer: vector DBs (FAISS/Chroma/Pinecone), LangChain. Depth 4."),
    "080826013418": ("AI_ENGINEERING", "AI/ML & GenAI Consultant: GenAI, LLMs, Azure OpenAI/Vertex, prompt eng, embeddings. Depth 4."),
    "070826035265": ("AI_ENGINEERING", "Lead AI Solutions R&D: AWS/GCP, AI/ML certs; research+engineering. Depth 4."),
    "070826034413": ("AI_ENGINEERING", "AI Developer: FastAPI, OpenAI/Gemini/Claude, LangChain, RAG, vector DBs, AI agents. Depth 4."),
    "070826937563": ("AI_ENGINEERING", "Accenture LLM Model Developer: instruction fine-tuning, domain adaptation. Depth 4."),
    "070826909470": ("AI_ENGINEERING", "Alegeus Engineer LLM Ops: AI evaluation frameworks, monitoring, feedback loops. Depth 4 (AI infra/eval)."),
    "120525010837": ("AI_ENGINEERING", "Easemytrip GenAI Engineer: LangChain/LlamaIndex/HF/OpenAI/Anthropic; LLM/NLP backend. Depth 4."),
    "070826930680": ("AI_ENGINEERING", "Optum Senior AIML: 8+ yrs AI/ML, NLP, OpenAI API, HF fine-tuning. Depth 4."),
    "070826930326": ("AI_ENGINEERING", "MongoDB AI Builder Experience: MCP servers, agent skills, polyglot backend. Depth 4."),
    "070826505022": ("AI_ENGINEERING", "UST Lead ML Engineering: Agentic AI, PyTorch, RAG, Gen AI, deploy & build. Depth 4."),
    "080826009555": ("AI_ENGINEERING", "Lead GenAI Engineer AWS: 5-9 yrs GenAI, RAG, LLM. Depth 4."),
    "070826018670": ("AI_ENGINEERING", "Coforge Gen AI Developer: Azure, 4-10 yrs GenAI/LLM. Depth 4."),
    "070826016383": ("AI_ENGINEERING", "Sutherland Applied AI Engineer: develops/deploys/operationalizes AI/ML solutions. Depth 4."),
    # rejected-correctly adversarial AI roles (rejection was dup/walk-in, not quality)
    "070826911605": ("AI_ENGINEERING", "Epam Senior Java Engineer AI-Native: MCP servers, function calling, frontier models. GENUINE AI depth 4; rejected only as DESCRIPTION_DUPLICATE (dup listing) — correct rejection, role is excellent AI.", "REJECT"),
    "070826011331": ("AI_ENGINEERING", "EY Walk-in GenAI Developer: LangChain/LangGraph/AutoGen/Agent SDK/MCP. Genuine depth 4; rejected OBJECTIVELY_INCOMPATIBLE (walk-in venue) — correct per policy, not a quality rejection.", "REJECT"),

    # ================= 20 EXCELLENT FDE =================
    "190726002682": ("FDE", "66degrees Forward Deployed Engineer: client interactions, production adoption, eval-driven roadmap. Textbook FDE."),
    "070826503457": ("FDE", "Botminds Forward Deployed Engineer: deployment at customer sites. Textbook FDE (Chennai)."),
    "090826003001": ("FDE", "Quickhyre Forward Deployed Engineer: AI/LLM model dev + API integration + deploy with teams. FDE+AI."),
    "090826002067": ("FDE", "Invorit Implementation Engineer: understand customer problems on shop floor, solution design, implementation, commissioning, validation. Strong FDE."),
    "070826503593": ("FDE", "Blueoptima Implementation Engineer: client onboarding, data quality, Tier 1 support — customer-facing technical. FDE MEDIUM-HIGH."),
    "070826500452": ("FDE", "SJ Innovation Sr Gen AI & Full Stack Solutions Engineer: React/Node/Mongo + GenAI APIs, client solutions. FDE+AI depth 3."),
    "250626016577": ("FDE", "CL Educate AI Solutions Consultant: customer-focused AI adoption, digital transformation. FDE MEDIUM-HIGH."),
    "070826500386": ("FDE", "Skan Lead AI Solutions Consultant: build/deploy AI solutions, stakeholder collaboration. FDE HIGH."),
    "jobspy_linkedin_li-4443541398": ("FDE", "PTC Forward Deployment Engineer - Automation (Python) & Airflow: forward deployment + automation. FDE HIGH."),
    "hiringcafe_brassring___25397___623208": ("FDE", "Deltek AI Solutions Engineer. FDE HIGH."),
    "hiringcafe_zohorecruit___kanini___2887000032117627": ("FDE", "Kanini Forward Deployed Engineer. FDE HIGH."),
    "hiringcafe_bamboohr___trustana___68": ("FDE", "Trustana Implementation Engineer. FDE HIGH."),
    "hiringcafe_oraclecloud___fa-emad-saasfaprod1.fa.ocs___5321": ("FDE", "Majesco AI Business Solutions Engineer. FDE HIGH."),
    "070826500374": ("FDE", "Yobitel AI Solutions Architect: design AI models, data pipelines, deploy ML. FDE+AI depth 3."),
    "070826910998": ("FDE", "LateShipment Senior SWE Fulfillment & Applied AI: analyze business workflows, automation, stakeholders, U.S. experience — customer/problem-facing applied AI. AI_FDE."),
    "jobspy_linkedin_li-4436172996": ("FDE", "PTC Software Technical Consultant: technical consulting/deployment. FDE MEDIUM."),
    "070826504225": ("FDE", "Cisco Technical Systems Engineer: technical systems engineering. FDE MEDIUM."),
    "100826000022": ("FDE", "Diligentminds Senior Consultant Agentic AI & Web Data Engineer: consulting + engineering. FDE+AI MEDIUM."),
    "070826911154": ("FDE", "Epam Data Technology Consultant (AI Consultant): 18-23yrs, business case, regulated AI. FDE but seniority mismatch (too senior).", "LOW"),
    "070826033882": ("FDE", "Deloitte Data Scientist (AI/ML) Consultant: 4+ yrs building & deploying AI. Consulting-adjacent FDE MEDIUM."),

    # ================= 20 AI-ADJACENT / AI-ENABLED =================
    "080826015330": ("AI_ADJACENT", "Ivorytusk Full Stack (React+Java Spring Boot+AI): AI label in title but JD is full-stack core; AI integration secondary. Depth 2."),
    "070826035400": ("AI_ADJACENT", "Mobilytics Full-Stack Node: builds AI-powered venture intelligence platform; AI-enabled product, backend role. Depth 2."),
    "070826039849": ("AI_ADJACENT", "Kozent Senior Full-Stack: US healthcare transcription AI-adjacent business. Generic full-stack core. Depth 1-2."),
    "080826011936": ("AI_ADJACENT", "Legato Tech Lead AI (Elevance Health): AI leadership but JD thin; likely AI-adjacent platform role. Depth 2."),
    "070826018850": ("AI_ADJACENT", "Itcube AI/ML Developer: build/deploy ML models + AI apps, Python/ML frameworks. Classic ML, not GenAI depth 2-3."),
    "070826930559": ("AI_ADJACENT", "Luxoft ML Engineer: TensorFlow/PyTorch, MLflow, model serving — traditional ML + serving. Depth 3 (ML systems, not GenAI)."),
    "070826500435": ("AI_ADJACENT", "Kooe Data Scientist - Generative AI: title suggests GenAI but DS framing. Depth 2."),
    "070826037807": ("AI_ADJACENT", "Macsof AI ML Engineer: generic AI/ML. Depth 2."),
    "090826002167": ("AI_ADJACENT", "TCS Azure Data Engineer + AI: primarily data pipelines (ADF/Databricks/Fabric), AI secondary. Depth 2."),
    "070826035483": ("AI_ADJACENT", "Photon CDP Engineer: customer data platform engineering — data/engineering, not AI modeling. Depth 1."),
    "070826040047": ("AI_ADJACENT", "Teamplus Data Engineer Cloud & Data Platform: data eng, not AI. Depth 1."),
    "070826039123": ("AI_ADJACENT", "Affine Data Engineer: data solutions, partner with business. Data eng depth 1."),
    "070826911615": ("AI_ADJACENT", "Epam Lead Software Engineer Java with GEN AI: Java lead with GenAI exposure. Depth 2."),
    "070826502330": ("AI_ADJACENT", "Coderound Founding Backend Engineer: startup AI backend; role is backend eng in AI company. Depth 2."),
    "070826911276": ("AI_ADJACENT", "Fan Tv AI Backend Developer: Node/Express/Mongo backend at AI startup. Depth 1."),
    "070826505141": ("AI_ADJACENT", "Bahwan CyberTek AI/ML Engineer: AI/ML engineering, depth varies 2-3. Classic ML probable."),
    "070826930461": ("AI_ADJACENT", "Optum Associate AI/ML Engineer: junior AI/ML. Depth 2."),
    "070826911685": ("AI_ADJACENT", "Kriyalogic Senior AIML Python Engineer: AIML python eng. Depth 2-3."),
    "080826015160": ("AI_ADJACENT", "TCS AI Observability Engineer: supporting production AI apps — AI infra/ops. Depth 3 (AI infra)."),
    "070826937581": ("AI_ADJACENT", "Accenture AI Human Capital Analytics Consultant: analytics consulting w/ AI toolkit. Depth 1-2."),
    "070826910883": ("AI_ADJACENT", "Kennect Data Consultant/Data Engineer: data pipelines + integrations, no AI. Depth 1."),

    # ================= 20 GENERIC FULL-STACK / BACKEND / FRONTEND =================
    "070826040230": ("GENERIC_ENGINEERING", "IPS Fullstack (Java+React): Java/Spring/SQL full-stack; 'AI exposure' mention only. Depth 1. RANKED #1 — contamination."),
    "230426030136": ("GENERIC_ENGINEERING", "Qentelli .Net Fullstack: Playwright/Python automation engineer JD — neither .NET nor AI. Depth 0-1."),
    "080826015370": ("GENERIC_ENGINEERING", "Optum Senior SWE Java/Python/React & cloud: generic polyglot backend/full-stack. Depth 1."),
    "070826909440": ("GENERIC_ENGINEERING", "CGI Python Next JS Developer: consulting full-stack, generic. Depth 1."),
    "070826504113": ("GENERIC_ENGINEERING", "TekWissen Full Stack Engineer: Azure hosting, CI/CD, generic full-stack. Depth 1."),
    "080826013468": ("GENERIC_ENGINEERING", "Cloudxtreme Java Full Stack Developer: generic Java FS. Depth 0-1."),
    "300426012743": ("GENERIC_ENGINEERING", "Cloudxtreme Java Full Stack Developer (dup-ish). Depth 0-1."),
    "070826039812": ("GENERIC_ENGINEERING", "Laravel/PHP Senior Software Developer: full-stack PHP. Depth 0."),
    "070826930353": ("GENERIC_ENGINEERING", "Luxoft Senior Java backend - CLM: enterprise backend. Depth 0-1."),
    "070826040497": ("GENERIC_ENGINEERING", "Infosys Java Full Stack Developer-S: generic FS. Depth 1."),
    "080826015885": ("GENERIC_ENGINEERING", "Infosys Java+Spring Boot+React Developer: generic FS. Depth 0."),
    "080826015892": ("GENERIC_ENGINEERING", "Infosys Java Developer: generic. Depth 0."),
    "090826000089": ("GENERIC_ENGINEERING", "Infosys Java Developer_S: generic. Depth 0."),
    "070826503383": ("GENERIC_ENGINEERING", "Redox Java Developer: generic. Depth 0."),
    "070826502455": ("GENERIC_ENGINEERING", "Happiest Minds Technical Lead ReactJS: frontend lead. Depth 0."),
    "070826503999": ("GENERIC_ENGINEERING", "Casperon Node/Mongo/Express dev: generic backend. Depth 0."),
    "080826011021": ("GENERIC_ENGINEERING", "Shri Bajrang HRMS Full Stack Developer: HRMS app dev. Depth 0."),
    "070826502867": ("GENERIC_ENGINEERING", "Techefficio Full Stack Developer: generic. Depth 0."),
    "070826930423": ("GENERIC_ENGINEERING", "Optum Java Full Stack Angular Kafka: generic enterprise FS. Depth 0."),
    "070826930549": ("GENERIC_ENGINEERING", "Optum Senior Software Engineer: generic enterprise SWE, no AI signals in JD. Depth 0-1."),
    "070826501554": ("GENERIC_ENGINEERING", "Cognite Software Engineer: distributed systems/data eng, no AI. Depth 0-1."),

    # ================= 20 FALSE-POSITIVE AI (AI keywords, not AI engineering) =================
    "070826013198": ("FALSE_POSITIVE", "Ensemble RPA Engineer: RPA ops (secrets, scheduling, logging) with open-source LLM 'exposure' — automation, not AI eng. Depth 1. RANKED #7 — contamination."),
    "070826501524": ("FALSE_POSITIVE", "Aqilea SR RPA Developer: RPA, not AI. Depth 0-1. SELECTED."),
    "070826911100": ("FALSE_POSITIVE", "Epam Lead JS Automation Test Engineer with AI & Agentic Testing: TEST AUTOMATION, not AI engineering. Depth 1."),
    "070826038465": ("FALSE_POSITIVE", "PwC QA Automation Tester - GenAI: Playwright/POM testing with GenAI mentions. Depth 1."),
    "070826937128": ("FALSE_POSITIVE", "Accenture Packaged/SaaS Application Engineer: configure/support SaaS apps, low-code. Not AI. SELECTED #42."),
    "070826039496": ("FALSE_POSITIVE", "LTM SAP Agentic AI Consultant Finance: SAP consulting w/ agentic AI label. Depth 1."),
    "070826504597": ("FALSE_POSITIVE", "Egadgetportal AI Data Specialist: autonomous AI systems for client calls — vague 'data specialist' + AI buzz. Depth 1-2."),
    "070826500238": ("FALSE_POSITIVE", "smartData AI/ML Model Development Expert: recruiting-agency post, vague. Depth 1-2."),
    "070826935222": ("FALSE_POSITIVE", "Purview AI/ML Expert: staffing post w/ GenAI framework keywords, RAG mention but staffing context. Depth 1-2."),
    "050826935206": ("FALSE_POSITIVE", "Infosys Data For AI Testing Lead: testing data for AI — QA/data prep. Depth 1."),
    "070826504114": ("FALSE_POSITIVE", "Baker Hughes DT Senior Specialist Observability & AI Ops: infrastructure observability ops. Depth 1."),
    "070826927116": ("FALSE_POSITIVE", "Hakimo Customer Support Engineer: support role. Depth 0."),
    "080826011426": ("FALSE_POSITIVE", "Fabric Technical Support Engineer (Python|Full Stack): support-first. Depth 0-1."),
    "070826930609": ("FALSE_POSITIVE", "Applied Materials Customer Engineer: field service semiconductor (associate degree, military tech training). NOT FDE. Depth 0."),
    "070826503121": ("FALSE_POSITIVE", "Thoughtsol Presales Engineer Juniper (Networking Solutions): presales networking. Depth 0."),
    "070826030953": ("FALSE_POSITIVE", "Zinnov Walk-in Technical Product Owner (Azure): PO role, rejected correctly (walk-in + non-engineering). Depth 0."),
    "080826009133": ("FALSE_POSITIVE", "Talentrouters ERPNext Developer: ERP config/dev. Depth 0."),
    "070826501726": ("FALSE_POSITIVE", "Yantraadhigam Odoo Technical Consultant: ERP consultant. Depth 0."),
    "080826015804": ("FALSE_POSITIVE", "Infosys IICS Developer: Informatica ETL integration. Depth 0."),
    "070826504455": ("FALSE_POSITIVE", "EY Consultant Tech Consulting: engineering-agnostic consulting JD. Depth 0."),

    # ================= 20 NON-TARGET / IRRELEVANT =================
    "070826930466": ("NON_TARGET", "Uber COE Team Lead: ops team lead, rejected correctly."),
    "090826002731": ("NON_TARGET", "Flipkart Team Lead (wish master support): ops."),
    "080826010638": ("NON_TARGET", "Imarque Team Lead: BPO sales/contact center."),
    "070826500050": ("NON_TARGET", "Paytm Team Leader: communications/ops lead."),
    "070826911704": ("NON_TARGET", "Kriyalogic Team Lead: BPO domestic process."),
    "070826036756": ("NON_TARGET", "Wroots Team Leader BPO Recruitment: recruiting."),
    "070826503958": ("NON_TARGET", "Advertising Company Team Leader: sales."),
    "070826028767": ("NON_TARGET", "SPS Realty Team Lead: realty sales."),
    "070826022541": ("NON_TARGET", "Aye Finance Team Lead: finance ops."),
    "070826014319": ("NON_TARGET", "Bharti AXA Team Lead: insurance field."),
    "070826014142": ("NON_TARGET", "Bharti AXA Team Lead (dup)."),
    "070826027774": ("NON_TARGET", "Expect More BPO Team Lead: insurance/banking ops."),
    "070826911273": ("NON_TARGET", "Fan Tv AI Freelance Video Editor: video editing, not engineering."),
    "070826504482": ("NON_TARGET", "EY Analyst Tax: tax, rejected correctly."),
    "hiringcafe_ashby___bjakcareer___3a04559c-3700-429b-b2d2-1e144dc27611": ("NON_TARGET", "BJAK iOS Developer: mobile, wrong track."),
    "hiringcafe_ashby___bjakcareer___ed731a5c-4614-4c9e-94fb-be8bbfd3ad54": ("NON_TARGET", "BJAK Mobile Engineer: mobile, wrong track."),
    "070826911276": ("NON_TARGET", "Fan Tv AI Backend Developer (Node/Express/Mongo): generic backend at AI company, no AI substance. Depth 1."),
    "080826011021": ("NON_TARGET", "Shri Bajrang HRMS Application Developer: HRMS app dev, non-target."),
    "070826036756": ("NON_TARGET", "Wroots BPO Recruitment Team Leader: recruiting ops."),
    "070826911273": ("NON_TARGET", "Fan Tv AI Freelance Video Editor: video editing, not engineering."),
    "070826504033": ("NON_TARGET", "Fractal Sales Executive: sales, rejected correctly (OBJECTIVELY_INCOMPATIBLE)."),
    "070826500729": ("NON_TARGET", "Twilio Marketing Strategy and Analytics Manager: marketing analytics, rejected correctly."),
    "070826500470": ("NON_TARGET", "Wonderbotz Technical Account Manager (UiPath): account management, not engineering. Rejected NON_SOFTWARE_ROLE."),
}

# Reclassify duplicates cleanly (avoid double-listing):
_OVERRIDES = {}

BUCKET_LABEL = {
    "AI_ENGINEERING": "excellent-ai",
    "FDE": "excellent-fde",
    "AI_FDE": "excellent-ai-fde",
    "AI_ADJACENT": "ai-adjacent",
    "GENERIC_ENGINEERING": "generic-engineering",
    "FALSE_POSITIVE": "false-positive-ai",
    "NON_TARGET": "non-target",
}
RANK_ORDER = {"TOP": 0, "STRONG": 1, "MAYBE": 2, "LOW": 3, "REJECT": 4}


def default_rank_band(bucket: str) -> str:
    return {
        "AI_ENGINEERING": "TOP",
        "FDE": "TOP",
        "AI_FDE": "TOP",
        "AI_ADJACENT": "STRONG",
        "GENERIC_ENGINEERING": "LOW",
        "FALSE_POSITIVE": "REJECT",
        "NON_TARGET": "REJECT",
    }[bucket]


def main() -> None:
    pool = json.loads(POOL.read_text())["pool"]
    by_id = {p["job_id"]: p for p in pool}

    records = []
    for jid, label in LABELS.items():
        bucket, rationale = label[0], label[1]
        bucket = _OVERRIDES.get(jid, bucket)
        obs = by_id.get(jid, {})
        rank_band = obs.get("_rank_override") or default_rank_band(bucket)
        if len(label) > 2:
            rank_band = label[2]
        records.append(
            {
                "job_id": jid,
                "title": obs.get("title"),
                "company": obs.get("company"),
                "experience": obs.get("experience"),
                "description_evidence": (obs.get("description") or "")[:1500],
                "current_rank": obs.get("rank"),
                "current_score": obs.get("score"),
                "current_status": obs.get("status"),
                "current_rejection_reason": obs.get("reason"),
                "current_classification": f"{obs.get('subtrack') or 'N/A'} / overlay={obs.get('search_profile') or 'N/A'}",
                "expected_role_family": bucket,
                "expected_ai_depth": AI_DEPTH[bucket],
                "expected_fde_band": FDE_BAND[bucket],
                "expected_technical_fit": TECH_FIT[bucket],
                "expected_trajectory": TRAJECTORY[bucket],
                "expected_rank_band": rank_band,
                "rationale": rationale,
                "label_bucket": BUCKET_LABEL[bucket],
            }
        )

    counts = Counter(r["label_bucket"] for r in records)
    if len(records) != 120:
        print(f"WARNING: expected 120 records, got {len(records)}")

    OUT_JSON.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_run": "20260810T004012474615Z",
                "ground_truth": "human-labeled from description evidence + candidate profile; NOT current-ranker scores",
                "bucket_counts": dict(counts),
                "records": records,
            },
            indent=1,
        )
    )

    # ---------- Markdown audit table ----------
    lines = [
        "# ai_fde_eval_v1 — Labeled evaluation dataset (Phase B)",
        "",
        f"Source run: `20260810T004012474615Z` — {len(records)} records.",
        "Ground truth: **human judgment** from JD evidence + candidate profile (Pune, 5yrs exp, 3yrs GenAI/RAG/agentic, Azure, Python/FastAPI/LangChain/LangGraph). NOT derived from the current LLM score.",
        "",
        "## Bucket composition",
        "",
        "| bucket | count |",
        "|---|---|",
    ]
    for k in ("excellent-ai", "excellent-fde", "excellent-ai-fde", "ai-adjacent", "generic-engineering", "false-positive-ai", "non-target"):
        lines.append(f"| {k} | {counts.get(k, 0)} |")
    lines += [
        "",
        "## Labels",
        "",
        "| job_id | title | company | status | rank | score | family | depth | fde | tech | traj | rank_band | rationale |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(records, key=lambda r: (r["expected_rank_band"], r["label_bucket"])):
        lines.append(
            f"| {r['job_id']} | {r['title'] or ''} | {r['company'] or ''} | {r['current_status'] or ''} | "
            f"{r['current_rank'] or ''} | {r['current_score'] or ''} | {r['expected_role_family']} | "
            f"{r['expected_ai_depth']} | {r['expected_fde_band']} | {r['expected_technical_fit']} | "
            f"{r['expected_trajectory']} | {r['expected_rank_band']} | {r['rationale']} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n")

    # ---------- Baseline metrics (CURRENT ranker) ----------
    # Current ranker ordering: SELECTED have rank 1..50; ROUTED have rank #N;
    # DEFERRED/REJECTED have no rank (effectively below 50 / excluded).
    def target(r: dict) -> bool:
        return r["expected_role_family"] in ("AI_ENGINEERING", "FDE", "AI_FDE")

    ranked = [r for r in records if r["current_rank"] is not None]
    ranked.sort(key=lambda r: r["current_rank"])

    ai = [r for r in ranked if r["expected_role_family"] == "AI_ENGINEERING"]
    fde = [r for r in ranked if r["expected_role_family"] in ("FDE", "AI_FDE")]
    tgt = [r for r in ranked if target(r)]

    def precision(rs, k):
        if not rs:
            return 0.0
        return sum(1 for r in rs[:k] if target(r)) / min(k, len(rs))

    top50 = [r for r in ranked if r["current_rank"] <= 50]
    contam = sum(1 for r in top50 if r["expected_role_family"] in ("GENERIC_ENGINEERING", "FALSE_POSITIVE", "NON_TARGET"))
    fp_rate = sum(1 for r in top50 if r["expected_role_family"] == "FALSE_POSITIVE")
    trapped = [r for r in records if target(r) and (r["current_rank"] is None or r["current_rank"] > 50)]

    print("\n=== BASELINE METRICS (CURRENT RANKER, eval set only) ===")
    print(f"eval records: {len(records)}")
    print(f"AI precision@20: {precision(ranked, 20):.2f} ({sum(1 for r in ranked[:20] if r['expected_role_family']=='AI_ENGINEERING')}/20)")
    print(f"AI precision@50: {precision(ranked, 50):.2f}")
    print(f"FDE precision@20: {sum(1 for r in ranked[:20] if r['expected_role_family'] in ('FDE','AI_FDE'))}/20")
    print(f"FDE precision@50: {sum(1 for r in ranked[:50] if r['expected_role_family'] in ('FDE','AI_FDE'))}/50")
    print(f"AI/FDE precision@50: {precision(ranked, 50):.2f} ({sum(1 for r in top50 if target(r))}/50 in eval set)")
    print(f"generic contamination@50 (eval): {contam}")
    print(f"false-positive AI in top 50 (eval): {fp_rate}")
    print(f"target jobs trapped below rank 50 or unranked: {len(trapped)}")

    # 10 worst ranking failures: target jobs ranked LOW/REJECT or below generic
    print("\n=== WORST CURRENT-RANKING DECISIONS (target jobs penalized) ===")
    bad = [r for r in records if target(r) and (r["current_rank"] is None or r["current_rank"] > 50)]
    for r in sorted(bad, key=lambda r: (r["label_bucket"], r["current_rank"] or 999))[:12]:
        print(f"  {r['label_bucket']:<20} rank={r['current_rank'] or 'unranked':<6} {r['title']} @ {r['company']}")


if __name__ == "__main__":
    main()
