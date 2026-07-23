import csv
from collections import Counter

INPUT_FILE = "data/raw_jobs.csv"


def normalize(value):
    return (value or "").strip().lower()


def main():
    with open(
        INPUT_FILE,
        encoding="utf-8",
        newline="",
    ) as file:
        jobs = list(csv.DictReader(file))

    print("=" * 80)
    print("DATASET SUMMARY")
    print("=" * 80)

    print(f"\nTotal jobs: {len(jobs)}")

    # --------------------------------------------------
    # Companies
    # --------------------------------------------------

    companies = Counter(
        row["company"].strip() for row in jobs if row["company"].strip()
    )

    print("\nTOP 20 COMPANIES")
    print("-" * 80)

    for company, count in companies.most_common(20):
        print(f"{count:>3}  {company}")

    # --------------------------------------------------
    # Titles
    # --------------------------------------------------

    titles = Counter(row["title"].strip() for row in jobs if row["title"].strip())

    print("\nTOP 30 EXACT TITLES")
    print("-" * 80)

    for title, count in titles.most_common(30):
        print(f"{count:>3}  {title}")

    # --------------------------------------------------
    # Locations
    # --------------------------------------------------

    locations = Counter(
        row["location"].strip() for row in jobs if row["location"].strip()
    )

    print("\nTOP 30 LOCATIONS")
    print("-" * 80)

    for location, count in locations.most_common(30):
        print(f"{count:>3}  {location}")

    # --------------------------------------------------
    # Experience
    # --------------------------------------------------

    experiences = Counter(
        row["experience"].strip() for row in jobs if row["experience"].strip()
    )

    print("\nEXPERIENCE VALUES")
    print("-" * 80)

    for experience, count in experiences.most_common():
        print(f"{count:>3}  {experience}")

    # --------------------------------------------------
    # Skill frequency
    # --------------------------------------------------

    skill_counter = Counter()

    for row in jobs:
        skills = row["tags"].split("|")

        for skill in skills:
            skill = normalize(skill)

            if skill:
                skill_counter[skill] += 1

    print("\nTOP 50 SKILLS")
    print("-" * 80)

    for skill, count in skill_counter.most_common(50):
        print(f"{count:>3}  {skill}")

    # --------------------------------------------------
    # Broad title categories
    # --------------------------------------------------

    categories = {
        "AI / GenAI": [
            "ai engineer",
            "artificial intelligence",
            "gen ai",
            "genai",
            "generative ai",
            "llm",
            "rag",
            "agentic",
            "applied ai",
        ],
        "Full Stack": [
            "full stack",
            "fullstack",
        ],
        "Angular": [
            "angular",
            "frontend",
            "front end",
        ],
        "Backend": [
            "backend",
            "back end",
            "node.js",
            "nodejs",
        ],
        "ML / Data Science": [
            "machine learning",
            "ml engineer",
            "data scientist",
            "deep learning",
            "computer vision",
        ],
    }

    category_counts = Counter()

    for row in jobs:
        title = normalize(row["title"])

        matched = False

        for category, terms in categories.items():
            if any(term in title for term in terms):
                category_counts[category] += 1
                matched = True

        if not matched:
            category_counts["Other"] += 1

    print("\nTITLE CATEGORY COUNTS")
    print("-" * 80)

    for category, count in category_counts.most_common():
        print(f"{count:>3}  {category}")


if __name__ == "__main__":
    main()
