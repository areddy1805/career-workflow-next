import argparse
import sys
from pathlib import Path

# Fix python path for direct CLI execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.cache.cache_manager import CacheManager

def main():
    parser = argparse.ArgumentParser(description="Cache maintenance CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("stats", help="Show cache statistics")
    subparsers.add_parser("clear", help="Clear all disposable cache")
    subparsers.add_parser("vacuum", help="Delete expired entries and VACUUM database")
    subparsers.add_parser("verify", help="Verify cache integrity")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    cm = CacheManager()
    
    if args.command == "stats":
        print("Cache Statistics:")
        for table in ["llm_cache", "embedding_cache", "detail_fetch_cache", "http_cache"]:
            try:
                count = cm.backend.execute(f"SELECT COUNT(*) as c FROM {table}")[0]["c"]
                print(f"  {table}: {count} entries")
            except Exception as e:
                print(f"  {table}: Error - {e}")
            
    elif args.command == "clear":
        print("Clearing disposable caches...")
        for table in ["llm_cache", "embedding_cache", "detail_fetch_cache", "http_cache"]:
            try:
                cm.backend.execute(f"DELETE FROM {table}")
            except Exception as e:
                print(f"Error clearing {table}: {e}")
        print("Caches cleared.")
        
    elif args.command == "vacuum":
        print("Vacuuming caches...")
        try:
            # delete expired from detail
            cm.backend.execute("DELETE FROM detail_fetch_cache WHERE expires_at IS NOT NULL AND expires_at < datetime('now')")
            # delete expired from http
            cm.backend.execute("DELETE FROM http_cache WHERE expires_at IS NOT NULL AND expires_at < datetime('now')")
            
            cm.backend.execute("VACUUM")
            cm.backend.execute("ANALYZE")
            print("Vacuum and Analyze complete.")
        except Exception as e:
            print(f"Error during vacuum: {e}")
        
    elif args.command == "verify":
        print("Verifying cache integrity...")
        try:
            result = cm.backend.execute("PRAGMA integrity_check")
            print(f"Result: {result[0]['integrity_check']}")
        except Exception as e:
            print(f"Error during verify: {e}")

if __name__ == "__main__":
    main()
