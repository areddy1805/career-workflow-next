import pytest
from src.core.semantic.entity_identity import EntityIdentityLayer
from src.core.semantic.vector_service import VectorSemanticService, SimilarityResult
from src.core.knowledge.store import KnowledgeStore, KnowledgeEntity

def test_semantic_intelligence_release_3_2():
    # 1. Entity Identity Layer
    cid1 = EntityIdentityLayer.generate_job_canonical_id("Senior AI Engineer", "TCS", "Bengaluru")
    cid2 = EntityIdentityLayer.generate_job_canonical_id("Senior AI Engineer", "TCS", "Bengaluru")
    assert cid1 == cid2
    assert cid1.startswith("job_canon_")

    # 2. Vector Similarity Engine & Similarity Bands
    svc = VectorSemanticService()
    vec_a = [1.0, 0.5, 0.2, 0.0]
    vec_b = [0.99, 0.49, 0.21, 0.0]  # ~99.9% similar
    vec_c = [0.0, 0.0, 1.0, 1.0]     # completely different

    svc.add_vector("job_a", vec_a)
    
    sim_res_b = svc.find_most_similar(vec_b)
    assert sim_res_b is not None
    assert sim_res_b.band == "REUSE_IMMEDIATE"
    assert sim_res_b.similarity_score >= 0.99

    sim_res_c = svc.find_most_similar(vec_c)
    assert sim_res_c.band == "SEPARATE"

    # 3. Knowledge Store
    ks = KnowledgeStore()
    k_entity = KnowledgeEntity(entity_id="company_tcs", entity_type="Company", confidence=98, payload={"name": "Tata Consultancy Services"})
    ks.put(k_entity)
    
    retrieved = ks.get("company_tcs")
    assert retrieved is not None
    assert retrieved.entity_type == "Company"
    assert len(ks.list_by_type("Company")) == 1
