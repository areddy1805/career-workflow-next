import csv
import os
import sqlite3
from datetime import datetime, UTC

CSV_FILE = "data/applied_jobs.csv"
DB_FILE = "data/application_ledger.db"


def migrate_csv_to_ledger():
    if not os.path.exists(CSV_FILE):
        print(f"No CSV file found at {CSV_FILE}. Nothing to migrate.")
        return

    if not os.path.exists(DB_FILE):
        print(f"No DB found at {DB_FILE}. Ensure ledger is initialized first.")
        return

    conn = sqlite3.connect(DB_FILE, isolation_level="EXCLUSIVE")
    cursor = conn.cursor()

    migrated_count = 0
    skipped_count = 0

    try:
        with open(CSV_FILE, "r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                job_id = str(row.get("job_id", "")).strip()
                if not job_id:
                    continue

                title = row.get("title", "")
                company = row.get("company", "")

                # We need to see if it exists
                cursor.execute(
                    "SELECT status FROM applications WHERE job_id = ?", (job_id,)
                )
                result = cursor.fetchone()

                now = datetime.now(UTC).isoformat()

                if result:
                    # Already in the ledger, make sure it's marked applied
                    if result[0] not in ("applied", "already_applied"):
                        cursor.execute(
                            "UPDATE applications SET status = 'applied', applied_at = ?, last_updated_at = ? WHERE job_id = ?",
                            (now, now, job_id),
                        )
                        migrated_count += 1
                    else:
                        skipped_count += 1
                else:
                    # Not in ledger, insert minimal record
                    cursor.execute(
                        """
                        INSERT INTO applications (
                            job_id, title, company, status, first_seen_at, last_updated_at, applied_at
                        ) VALUES (?, ?, ?, 'applied', ?, ?, ?)
                        """,
                        (job_id, title, company, now, now, now),
                    )
                    migrated_count += 1

        conn.commit()
        print(
            f"Migration successful. Migrated {migrated_count} rows, skipped {skipped_count} (already applied)."
        )
        print(f"You can now safely delete {CSV_FILE}.")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_csv_to_ledger()
