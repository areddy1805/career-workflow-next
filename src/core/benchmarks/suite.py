import time
import json
import statistics
import sys
try:
    import psutil
except ImportError:
    psutil = None
from pathlib import Path
from typing import List, Dict, Any

from src.models.models import Job
from src.core.job_intelligence.normalizer import JobNormalizer
from src.core.job_intelligence.extractor import JobExtractor

class BenchmarkSuite:
    """
    Release 3.0.5 Statistical Benchmark Validation Suite.
    Measures Mean, Median, P95, P99, StdDev, CPU, and Memory usage across warmup and measured runs.
    """
    def __init__(self, corpus_path: str = "data/regression_corpus/sample_jobs.json"):
        self.corpus_path = Path(corpus_path)
        self.normalizer = JobNormalizer()
        self.extractor = JobExtractor()

    def generate_dummy_corpus(self, count: int = 500) -> List[Job]:
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

    def calculate_stats(self, durations: List[float]) -> Dict[str, float]:
        sorted_d = sorted(durations)
        n = len(sorted_d)
        mean = statistics.mean(sorted_d)
        median = statistics.median(sorted_d)
        stdev = statistics.stdev(sorted_d) if n > 1 else 0.0
        p95 = sorted_d[int(0.95 * n)] if n > 0 else 0.0
        p99 = sorted_d[int(0.99 * n)] if n > 0 else 0.0
        return {
            "mean_ms": mean * 1000,
            "median_ms": median * 1000,
            "p95_ms": p95 * 1000,
            "p99_ms": p99 * 1000,
            "stdev_ms": stdev * 1000
        }

    def run_benchmark(self, corpus: List[Job], warmup_runs: int = 3, measured_runs: int = 10) -> Dict[str, Any]:
        count = len(corpus)
        process = psutil.Process() if psutil else None
        
        # 1. Warmup Runs
        for _ in range(warmup_runs):
            norm = [self.normalizer.normalize_job(j) for j in corpus]
            _ = [self.extractor.extract(nj) for nj in norm]

        # 2. Measured Runs
        norm_durations = []
        ext_durations = []
        mem_before = process.memory_info().rss / (1024 * 1024) if process else 0.0
        cpu_start = process.cpu_times() if process else None

        for _ in range(measured_runs):
            t0 = time.perf_counter()
            normalized_jobs = [self.normalizer.normalize_job(j) for j in corpus]
            t1 = time.perf_counter()
            norm_durations.append(t1 - t0)

            t2 = time.perf_counter()
            _ = [self.extractor.extract(nj) for nj in normalized_jobs]
            t3 = time.perf_counter()
            ext_durations.append(t3 - t2)

        mem_after = process.memory_info().rss / (1024 * 1024) if process else 0.0
        cpu_end = process.cpu_times() if process else None
        cpu_user_ms = ((cpu_end.user - cpu_start.user) * 1000) if (cpu_end and cpu_start) else 0.0
        cpu_sys_ms = ((cpu_end.system - cpu_start.system) * 1000) if (cpu_end and cpu_start) else 0.0

        norm_stats = self.calculate_stats(norm_durations)
        ext_stats = self.calculate_stats(ext_durations)

        avg_norm_sec = norm_stats["mean_ms"] / 1000
        avg_ext_sec = ext_stats["mean_ms"] / 1000
        total_throughput = count / (avg_norm_sec + avg_ext_sec)

        results = {
            "environment": {
                "python_version": sys.version,
                "warmup_runs": warmup_runs,
                "measured_runs": measured_runs,
                "dataset_size": count
            },
            "system_resources": {
                "memory_before_mb": mem_before,
                "memory_after_mb": mem_after,
                "memory_delta_mb": mem_after - mem_before,
                "cpu_user_time_ms": cpu_user_ms,
                "cpu_sys_time_ms": cpu_sys_ms
            },
            "normalization": {
                "stats": norm_stats,
                "throughput_jobs_per_sec": count / avg_norm_sec if avg_norm_sec > 0 else 0
            },
            "extraction": {
                "stats": ext_stats,
                "throughput_jobs_per_sec": count / avg_ext_sec if avg_ext_sec > 0 else 0
            },
            "total_throughput_jobs_per_sec": total_throughput
        }

        output_file = Path("artifacts/benchmark.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(results, indent=2))

        return results

if __name__ == "__main__":
    suite = BenchmarkSuite()
    dummy_corpus = suite.generate_dummy_corpus(500)
    res = suite.run_benchmark(dummy_corpus)
    print("Statistical Benchmark complete:", json.dumps(res, indent=2))
