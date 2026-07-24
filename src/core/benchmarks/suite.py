import time
import json
from pathlib import Path
from typing import List, Dict, Any

from src.models.models import Job
from src.core.job_intelligence.normalizer import JobNormalizer
from src.core.job_intelligence.extractor import JobExtractor

class BenchmarkSuite:
    """
    Phase 0E Benchmark Suite.
    Profiles normalization and metadata extraction throughput, generating benchmark.json.
    """
    def __init__(self, corpus_path: str = "data/regression_corpus/sample_jobs.json"):
        self.corpus_path = Path(corpus_path)
        self.normalizer = JobNormalizer()
        self.extractor = JobExtractor()

    def generate_dummy_corpus(self, count: int = 100) -> List[Job]:
        corpus = []
        for i in range(count):
            job = Job(
                job_id=f"job_{i}",
                title=f"Senior Software Engineer {i} (React/Node.js)",
                company="TCS Ltd",
                location="Bengaluru",
                experience="5-8 years",
                salary="15-20 LPA",
                posted_date="2 days ago",
                description=f"Looking for a Senior Software Engineer with Python, React, and AWS experience. Job ID {i}."
            )
            corpus.append(job)
        return corpus

    def run_benchmark(self, corpus: List[Job]) -> Dict[str, Any]:
        count = len(corpus)
        
        # 1. Normalization Benchmark
        t0 = time.perf_counter()
        normalized_jobs = [self.normalizer.normalize_job(j) for j in corpus]
        t1 = time.perf_counter()
        norm_duration = t1 - t0
        norm_throughput = count / norm_duration if norm_duration > 0 else 0

        # 2. Extraction Benchmark
        t2 = time.perf_counter()
        extracted_metadata = [self.extractor.extract(nj) for nj in normalized_jobs]
        t3 = time.perf_counter()
        ext_duration = t3 - t2
        ext_throughput = count / ext_duration if ext_duration > 0 else 0

        results = {
            "sample_size": count,
            "normalization": {
                "total_time_sec": norm_duration,
                "throughput_jobs_per_sec": norm_throughput
            },
            "extraction": {
                "total_time_sec": ext_duration,
                "throughput_jobs_per_sec": ext_throughput
            },
            "total_throughput_jobs_per_sec": count / (norm_duration + ext_duration)
        }
        
        # Save to benchmark.json
        output_file = Path("artifacts/benchmark.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(results, indent=2))
        
        return results

if __name__ == "__main__":
    suite = BenchmarkSuite()
    dummy_corpus = suite.generate_dummy_corpus(500)
    res = suite.run_benchmark(dummy_corpus)
    print("Benchmark complete:", json.dumps(res, indent=2))
