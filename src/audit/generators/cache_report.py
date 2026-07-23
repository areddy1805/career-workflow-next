import inspect
from pathlib import Path
from src.audit.markdown_builder import MarkdownBuilder
from src.audit.introspector import extract_class_attributes, get_class_methods

try:
    from src.cache.cache_manager import CacheManager
except ImportError:
    CacheManager = None

try:
    from src.search.job_search_cache import JobSearchCache
except ImportError:
    JobSearchCache = None

def generate_cache_report(output_dir: Path):
    mb = MarkdownBuilder("Cache Inventory")
    mb.add_paragraph("This report automatically extracts cache configurations and TTLs.")
    
    if CacheManager:
        mb.add_heading("Cache Manager")
        methods = get_class_methods(CacheManager)
        method_rows = [[m["name"], m["signature"]] for m in methods]
        mb.add_table(["Method", "Signature"], method_rows)
        
    if JobSearchCache:
        mb.add_heading("Job Search Cache")
        methods = get_class_methods(JobSearchCache)
        method_rows = [[m["name"], m["signature"]] for m in methods]
        mb.add_table(["Method", "Signature"], method_rows)
        
    output_path = output_dir / "cache.md"
    output_path.write_text(mb.build(), encoding="utf-8")
    return output_path
