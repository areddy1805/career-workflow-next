"""Unit tests for the deterministic multi-objective ranker (Phase C/D).

No fixtures, no framework magic — plain assertions on real job records.
"""

from src.core.ranking import new_ranker as nr


def _job(title, desc="", tags=None, exp="", loc="Pune", company="Acme"):
    return {
        "job_id": "t1",
        "title": title,
        "company": company,
        "description": desc,
        "tags": tags or [],
        "experience": exp,
        "location": loc,
    }


def test_ai_depth_tiers():
    assert nr.detect_ai_depth("AI Engineer", [], "Build RAG pipelines with LangChain and vector search")[0] == 4
    assert nr.detect_ai_depth("AI Engineer", [], "Build LLM applications with OpenAI, RAG, agents")[0] == 4
    assert nr.detect_ai_depth("Software Engineer", [], "Work with ML models and predictive analytics")[0] == 2
    assert nr.detect_ai_depth("Java Full Stack Developer", [], "Java Spring, React, LLM integration, RAG, LangChain, vector db")[0] <= 2
    assert nr.detect_ai_depth("QA Automation Tester", [], "GenAI, LLM, RAG, agents, Claude, LangChain")[0] == 1
    assert nr.detect_ai_depth("Java Developer", [], "Spring Boot, Hibernate, MySQL")[0] == 0


def test_fde_band_evidence():
    band, ev, _ = nr.detect_fde("Forward Deployed Engineer", "Deploy solutions to customer sites, rapid prototyping, technical discovery")
    assert band in ("HIGH", "EXCELLENT")
    assert ev

    # Customer Engineer doing hardware field service is NOT FDE
    band, _, _ = nr.detect_fde("Customer Engineer", "Associate degree, field service, electrical schematics")
    assert band == "NONE"

    # Support roles never FDE
    band, _, _ = nr.detect_fde("Technical Support Engineer", "Customer support, help desk")
    assert band == "NONE"


def test_family_priority():
    assert nr.detect_family(4, "HIGH", "AI Engineer", "deploy to customers") == "AI_FDE"
    assert nr.detect_family(4, "NONE", "AI Engineer", "") == "AI_ENGINEERING"
    assert nr.detect_family(0, "EXCELLENT", "Forward Deployed Engineer", "customer site") == "FDE"
    assert nr.detect_family(2, "NONE", "Data Engineer", "") == "AI_ADJACENT"
    assert nr.detect_family(0, "NONE", "Java Developer", "") == "GENERIC_ENGINEERING"
    assert nr.detect_family(0, "NONE", "Team Lead", "BPO sales") == "NON_TARGET"


def test_ai_fde_beats_generic():
    ai = _job("AI Engineer", "Build LLM apps: RAG, LangGraph agents, Azure OpenAI, vector search, prompt engineering")
    generic = _job("Senior Java Full Stack Developer", "Java, Spring Boot, React, SQL, Microservices, CI/CD")
    assert nr.score(ai) > nr.score(generic)


def test_rpa_and_qa_never_outrank_ai():
    rpa = _job("RPA Engineer", "UiPath automation, open-source LLM exposure, scheduling, logging")
    ai = _job("AI Engineer", "RAG, LangChain, agents, Azure OpenAI, vector search")
    assert nr.score(ai) > nr.score(rpa)

    qa = _job("QA Automation Tester - GenAI", "Playwright, test automation, GenAI test data")
    assert nr.score(ai) > nr.score(qa)


def test_score_bounded():
    for title, desc in [
        ("AI Engineer", "LLM RAG agents LangChain Azure OpenAI vector search prompt engineering fine-tuning"),
        ("Team Lead", "BPO sales target commission"),
        ("Java Full Stack Developer", "Java Spring React SQL Microservices"),
    ]:
        s = nr.score(_job(title, desc))
        assert 0.0 <= s <= 100.0


def test_analysis_explainable():
    a = nr.analyze(_job("AI Engineer", "RAG, LangChain, Azure OpenAI, agents"))
    for key in ("role_family", "ai_depth", "fde_band", "technical_fit", "trajectory",
                "noise_penalty", "final_score", "explanation", "components", "fde_evidence"):
        assert key in a, key
    assert a["final_score"] == min(100.0, max(0.0,
        a["components"]["base"] + a["components"]["ai_depth"]
        + a["components"]["fde_band"] + a["components"]["technical_fit"]
        + a["components"]["location_fit"] + a["components"]["experience_fit"]
        + a["components"]["trajectory"] - a["components"]["noise_penalty"]))
