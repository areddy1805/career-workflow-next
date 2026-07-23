from src.client import job_classifier as module

Pipeline = module.JobFilterPipeline2


def pipeline(tmp_path, min_apply_score=50):
    return Pipeline(
        api_key="test",
        cache_file=str(tmp_path / "cache.json"),
        min_apply_score=min_apply_score,
    )


def job(
    job_id,
    title,
    tags=None,
    description="",
    location="Pune",
    experience="4-8 Yrs",
    work_mode=None,
):
    data = {
        "job_id": job_id,
        "title": title,
        "company": "Test Co",
        "location": location,
        "tags": tags or [],
        "description": description,
        "experience": experience,
        "posted_date": "1 day ago",
    }
    if work_mode:
        data["work_mode"] = work_mode
    return data


def norm(p, raw):
    return p.normalize_jobs([raw])[0]


def test_ai_ml_title_not_hard_vetoed(tmp_path):
    p = pipeline(tmp_path)
    raw = job("1", "AI/ML Engineer", ["python", "pytorch"], "Build ML systems")
    assert p.hard_veto(p.normalize_jobs([raw]))


def test_data_scientist_ai_role_not_hard_vetoed(tmp_path):
    p = pipeline(tmp_path)
    raw = job("2", "Data Scientist - Generative AI", ["llm"], "Build AI systems")
    assert p.hard_veto(p.normalize_jobs([raw]))


def test_stack_conflict_is_never_eligibility_veto(tmp_path):
    p = pipeline(tmp_path)
    raws = [
        job("j", "Java AI Engineer", ["java", "spring", "machine learning"]),
        job("c", "C++ Computer Vision Engineer", ["c++", "opencv", "deep learning"]),
        job("n", ".NET AI Developer", [".net", "azure ai", "artificial intelligence"]),
    ]
    normalized = p.normalize_jobs(raws)
    assert len(p.primary_stack_conflict_filter(normalized, True)) == 3


def test_explicit_ml_and_cv_titles_pass_ai_relevance(tmp_path):
    p = pipeline(tmp_path)
    raws = [
        job("m", "Machine Learning Engineer", ["python"], "Train ML models"),
        job("v", "Computer Vision Engineer", ["opencv"], "Build vision AI"),
    ]
    normalized = p.normalize_jobs(raws)
    assert len(p.ai_relevance_gate(normalized)) == 2


def test_generic_backend_without_ai_fails_relevance(tmp_path):
    p = pipeline(tmp_path)
    raw = job("3", "Backend Developer", ["node.js"], "Build REST APIs")
    normalized = p.normalize_jobs([raw])
    assert p.ai_relevance_gate(normalized)[0]["ai_relevance"] is False


def test_remote_anywhere_passes_location_gate(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(
        p,
        job("4", "AI Engineer", ["ai"], "Remote role", "Bengaluru", work_mode="Remote"),
    )
    assert p.location_work_mode_gate([raw]) == [raw]


def test_pune_hybrid_passes_location_gate(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(
        p, job("5", "AI Engineer", ["ai"], "Hybrid role", "Pune", work_mode="Hybrid")
    )
    assert p.location_work_mode_gate([raw]) == [raw]


def test_non_pune_hybrid_rejected(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(
        p, job("6", "AI Engineer", ["ai"], "Hybrid role", "Chennai", work_mode="Hybrid")
    )
    assert p.location_work_mode_gate([raw])[0]["location_preference"] == "Acceptable"


def test_non_pune_office_rejected(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(p, job("7", "AI Engineer", ["ai"], "Work from office", "Hyderabad"))
    assert p.location_work_mode_gate([raw])[0]["location_preference"] == "Preferred"


def test_explicit_ai_title_gets_apply_floor(tmp_path):
    p = pipeline(tmp_path, min_apply_score=50)
    raw = norm(p, job("8", "Machine Learning Engineer", ["pytorch"], "Train models"))
    raw["ai_score"] = 31
    guarded = p.post_score_guard([raw])
    assert guarded[0]["ai_score"] == 50


def test_incidental_ai_generic_job_is_capped(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(p, job("9", "Backend Developer", ["node.js"], "Integrate one AI API"))
    raw["ai_score"] = 80
    guarded = p.post_score_guard([raw])
    assert guarded[0]["ai_score"] <= 49


def test_rank_prefers_fit_score(tmp_path):
    p = pipeline(tmp_path)
    a = {"ai_score": 90, "ai_signal_count": 2, "days_old": 7}
    b = {"ai_score": 70, "ai_signal_count": 8, "days_old": 0}
    assert p.rank([b, a])[0] is a


def test_remote_sensing_does_not_count_as_remote_work(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(
        p,
        job(
            "10",
            "AI Engineer",
            ["ai"],
            "Build remote sensing models for satellite imagery.",
            "Bengaluru",
        ),
    )
    assert p._classify_work_mode(raw) == "unknown"
    assert p.location_work_mode_gate([raw])[0]["location_preference"] == "Preferred"


def test_negative_remote_language_does_not_pass_worldwide_gate(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(
        p,
        job(
            "11",
            "AI Engineer",
            ["ai"],
            "This role is not remote. Work from office in Bengaluru.",
            "Bengaluru",
        ),
    )
    assert p._classify_work_mode(raw) == "office"
    assert p.location_work_mode_gate([raw])[0]["location_preference"] == "Preferred"


def test_incidental_pune_office_mention_does_not_make_bengaluru_job_pune(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(
        p,
        job(
            "12",
            "AI Engineer",
            ["ai"],
            "This position is based in Bengaluru. Our offices are in Pune and Hyderabad.",
            "Bengaluru",
            work_mode="Hybrid",
        ),
    )
    assert p.location_work_mode_gate([raw])[0]["location_preference"] == "Preferred"


def test_explicit_description_work_location_pune_is_accepted(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(
        p,
        job(
            "13",
            "AI Engineer",
            ["ai"],
            "Work location: Pune. Hybrid working model.",
            "",
        ),
    )
    assert p._classify_location_preference(raw) == "Preferred"
    assert p.location_work_mode_gate([raw]) == [raw]


def test_standalone_remote_location_passes_worldwide_gate(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(
        p,
        job(
            "14",
            "AI Engineer",
            ["ai"],
            "Build production AI systems.",
            "Remote",
        ),
    )

    assert p._classify_work_mode(raw) == "remote"
    assert p.location_work_mode_gate([raw]) == [raw]


def test_remote_india_location_passes_worldwide_gate(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(
        p,
        job(
            "15",
            "AI Engineer",
            ["ai"],
            "Build production AI systems.",
            "Remote - India",
        ),
    )

    assert p._classify_work_mode(raw) == "remote"
    assert p.location_work_mode_gate([raw]) == [raw]


def test_india_remote_location_passes_worldwide_gate(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(
        p,
        job(
            "16",
            "AI Engineer",
            ["ai"],
            "Build production AI systems.",
            "India - Remote",
        ),
    )

    assert p._classify_work_mode(raw) == "remote"
    assert p.location_work_mode_gate([raw]) == [raw]


def test_hybrid_signal_wins_over_remote_signal(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(
        p,
        job(
            "17",
            "AI Engineer",
            ["ai"],
            "Hybrid role with remote flexibility.",
            "Bengaluru",
        ),
    )

    assert p._classify_work_mode(raw) == "hybrid"
    assert p.location_work_mode_gate([raw])[0]["location_preference"] == "Preferred"


def test_plain_india_without_remote_signal_remains_rejected(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(
        p,
        job(
            "18",
            "AI Native Engineer",
            ["ai"],
            "Build agentic AI systems.",
            "India",
        ),
    )

    assert p._classify_work_mode(raw) == "unknown"
    assert p.location_work_mode_gate([raw])[0]["location_preference"] == "Acceptable"


def test_explicit_remote_location_overrides_conflicting_hybrid_metadata(tmp_path):
    p = pipeline(tmp_path)
    raw = norm(
        p,
        job(
            "19",
            "AI Engineer",
            ["ai"],
            "Build production AI systems.",
            "Remote",
            work_mode="Hybrid",
        ),
    )

    assert p._classify_work_mode(raw) == "remote"
    assert p.location_work_mode_gate([raw]) == [raw]
