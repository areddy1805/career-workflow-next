import ast
import csv
import json
from collections import Counter
from pathlib import Path

from config.candidate_profile import CANDIDATE_PROFILE
from src.utils.questionnaire_resolver import (
    resolve_answer,
    serialize_answer,
)

TELEMETRY_FILE = Path("data/questionnaire_telemetry.csv")


def parse_options(raw: str) -> dict:
    if not raw:
        return {}

    raw = raw.strip()

    if not raw:
        return {}

    try:
        value = json.loads(raw)

        if isinstance(value, dict):
            return value

    except json.JSONDecodeError:
        pass

    try:
        value = ast.literal_eval(raw)

        if isinstance(value, dict):
            return value

    except (ValueError, SyntaxError):
        pass

    return {}


def build_question(row: dict) -> dict:
    return {
        "questionId": row.get("question_id", ""),
        "questionName": row.get("question", ""),
        "questionType": row.get("question_type", ""),
        "category": row.get("category", ""),
        "isMandatory": (
            str(row.get("mandatory", "")).strip().lower()
            in {
                "true",
                "1",
                "yes",
            }
        ),
        "answerOption": parse_options(row.get("answer_options", "")),
    }


def main():
    if not TELEMETRY_FILE.exists():
        raise RuntimeError(f"Missing telemetry file: {TELEMETRY_FILE}")

    with TELEMETRY_FILE.open(
        encoding="utf-8",
        newline="",
    ) as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("No questionnaire telemetry observations found.")
        return

    unique_questions = {}

    for row in rows:
        key = (
            row.get("question", "").strip(),
            row.get("question_type", "").strip(),
            row.get("answer_options", "").strip(),
        )

        unique_questions.setdefault(
            key,
            row,
        )

    resolved = []
    unresolved = []

    print("=" * 120)
    print("QUESTIONNAIRE TELEMETRY RESOLUTION TEST")
    print("=" * 120)

    print(f"Telemetry observations: {len(rows)}")
    print(f"Unique questionnaire cases: {len(unique_questions)}")

    for index, row in enumerate(
        unique_questions.values(),
        1,
    ):
        question = build_question(row)

        semantic = resolve_answer(
            question,
            CANDIDATE_PROFILE,
        )

        serialized = None

        if semantic is not None:
            serialized = serialize_answer(
                question,
                semantic,
            )

        result = {
            "question": question["questionName"],
            "question_type": question["questionType"],
            "semantic": semantic,
            "serialized": serialized,
            "options": question["answerOption"],
        }

        print("\n" + "-" * 120)
        print(f"[{index}] {question['questionName']}")
        print(f"Type:       {question['questionType']}")
        print(f"Semantic:   {semantic}")
        print(f"Serialized: {serialized}")

        if question["answerOption"]:
            print(
                "Options:    "
                + json.dumps(
                    question["answerOption"],
                    ensure_ascii=False,
                )
            )

        if semantic is not None and serialized is not None:
            resolved.append(result)
            print("Result:     RESOLVED")

        else:
            unresolved.append(result)
            print("Result:     UNRESOLVED")

    print("\n" + "=" * 120)
    print("SUMMARY")
    print("=" * 120)

    print(f"Resolved:   {len(resolved)}")
    print(f"Unresolved: {len(unresolved)}")
    print(f"Total:      {len(unique_questions)}")

    resolution_rate = (
        len(resolved) / len(unique_questions) * 100 if unique_questions else 0
    )

    print(f"Resolution rate: {resolution_rate:.1f}%")

    print("\n" + "=" * 120)
    print("UNRESOLVED QUESTIONS")
    print("=" * 120)

    if not unresolved:
        print("None")

    else:
        for item in unresolved:
            print(f'[{item["question_type"]}] ' f'{item["question"]}')

            if item["semantic"] is not None:
                print(
                    "  Semantic resolved but serialization failed: "
                    f'{item["semantic"]}'
                )

            if item["options"]:
                print(
                    "  Options: "
                    + json.dumps(
                        item["options"],
                        ensure_ascii=False,
                    )
                )

    print("\n" + "=" * 120)
    print("UNRESOLVED BY TYPE")
    print("=" * 120)

    counts = Counter(item["question_type"] for item in unresolved)

    if not counts:
        print("None")

    else:
        for question_type, count in counts.most_common():
            print(f"{count:3} | {question_type}")


if __name__ == "__main__":
    main()
