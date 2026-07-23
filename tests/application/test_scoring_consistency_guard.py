from src.client.job_classifier import JobFilterPipeline2


def classifier(tmp_path, monkeypatch):
    monkeypatch.setenv("OMLX_API_KEY", "test")
    return JobFilterPipeline2(cache_file=str(tmp_path / "cache.json"))


def job(title, company, description, score):
    return {
        "title": title,
        "company": company,
        "description": description,
        "tags": [],
        "mandatory_tags": [],
        "optional_tags": [],
        "ai_score": score,
    }


def test_agentic_backend_generic_title_gets_floor(tmp_path, monkeypatch):
    c = classifier(tmp_path, monkeypatch)
    j = job(
        "Software Developer",
        "Anamika Consulting",
        "Build Python REST API microservices with MongoDB for AI agents, agentic AI, tool calling and LLM workflows.",
        49,
    )
    result = c.post_score_guard([j])
    assert result[0]["ai_score"] >= 72


def test_llm_operations_title_gets_ai_title_floor(tmp_path, monkeypatch):
    c = classifier(tmp_path, monkeypatch)
    j = job(
        "LLM Operations Engineer",
        "Accenture",
        "Deploy and operate LLM services on Kubernetes.",
        49,
    )
    result = c.post_score_guard([j])
    assert result[0]["ai_score"] >= c.min_apply_score


def test_generic_fullstack_incidental_ai_is_capped(tmp_path, monkeypatch):
    c = classifier(tmp_path, monkeypatch)
    j = job(
        "Developer",
        "Right Salary Resource",
        "Build React Next.js and Flutter apps, REST APIs, with occasional AI integration.",
        65,
    )
    result = c.post_score_guard([j])
    assert result[0]["ai_score"] <= 49


def test_vba_automation_ai_title_is_rejected(tmp_path, monkeypatch):
    c = classifier(tmp_path, monkeypatch)
    j = job(
        "AI Developer",
        "Jewelex India",
        "Maintain VBA automation, Excel macros, advanced Excel reports, user support and documentation.",
        50,
    )
    assert c.post_score_guard([j]) == []


def test_copywriter_prompt_title_is_rejected(tmp_path, monkeypatch):
    c = classifier(tmp_path, monkeypatch)
    j = job(
        "Junior Prompt Engineer - Brand Copywriter",
        "Aminu",
        "Write brand copy, marketing copy and social media content using AI tools.",
        50,
    )
    assert c.post_score_guard([j]) == []
