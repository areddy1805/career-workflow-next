import argparse
import sys
from pathlib import Path



from src.cache.cache_manager import CacheManager

def main():
    parser = argparse.ArgumentParser(description="Cache maintenance CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("stats", help="Show cache statistics")
    subparsers.add_parser("purge", help="Clear all disposable cache")
    subparsers.add_parser("purge-expired", help="Delete expired entries from cache")
    subparsers.add_parser("vacuum", help="Delete expired entries and VACUUM database")
    subparsers.add_parser("verify", help="Verify cache integrity")
    
    inspect_parser = subparsers.add_parser("inspect", help="Inspect a specific cache entry by fingerprint")
    inspect_parser.add_argument("fingerprint", type=str, help="The fingerprint to inspect")
    
    subparsers.add_parser("warm", help="Warm up the cache (placeholder)")
    
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
            
    elif args.command == "purge":
        print("Purging disposable caches...")
        for table in ["llm_cache", "embedding_cache", "detail_fetch_cache", "http_cache"]:
            try:
                cm.backend.execute(f"DELETE FROM {table}")
            except Exception as e:
                print(f"Error purging {table}: {e}")
        print("Caches purged.")
        
    elif args.command == "purge-expired":
        print("Purging expired entries...")
        try:
            # llm_cache
            try:
                cm.backend.execute("DELETE FROM llm_cache WHERE expires_at IS NOT NULL AND expires_at < datetime('now')")
                print("Purged expired from llm_cache")
            except Exception:
                pass
            cm.backend.execute("DELETE FROM detail_fetch_cache WHERE expires_at IS NOT NULL AND expires_at < datetime('now')")
            cm.backend.execute("DELETE FROM http_cache WHERE expires_at IS NOT NULL AND expires_at < datetime('now')")
            print("Expired entries purged.")
        except Exception as e:
            print(f"Error purging expired: {e}")

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
            
    elif args.command == "inspect":
        print(f"Inspecting fingerprint: {args.fingerprint}")
        found = False
        for table in ["llm_cache", "embedding_cache", "detail_fetch_cache", "http_cache"]:
            try:
                res = cm.backend.execute(f"SELECT * FROM {table} WHERE fingerprint = ?", (args.fingerprint,))
                row = res.fetchone()
                if row:
                    print(f"Found in {table}:")
                    for k in row.keys():
                        val = row[k]
                        if isinstance(val, str) and len(val) > 200:
                            val = val[:200] + "..."
                        print(f"  {k}: {val}")
                    found = True
                    break
            except Exception:
                pass
        if not found:
            print("Fingerprint not found in any cache table.")
            
    elif args.command == "warm":
        print("Cache warmup not currently implemented.")

if __name__ == "__main__":
    main()
