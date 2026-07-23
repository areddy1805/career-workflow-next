import json
from collections import Counter
from pathlib import Path
from typing import Any

RESPONSES_DIR = Path("data/responses")


def summarize_value(
    value: Any,
    depth: int = 0,
    max_depth: int = 4,
) -> Any:
    if depth >= max_depth:
        if isinstance(value, dict):
            return f"<dict:{len(value)} keys>"

        if isinstance(value, list):
            return f"<list:{len(value)} items>"

        return value

    if isinstance(value, dict):
        return {
            key: summarize_value(
                item,
                depth + 1,
                max_depth,
            )
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            summarize_value(
                item,
                depth + 1,
                max_depth,
            )
            for item in value[:3]
        ]

    return value


def collect_paths(
    value: Any,
    prefix: str = "",
) -> list[str]:
    paths = []

    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key

            paths.append(path)

            paths.extend(
                collect_paths(
                    item,
                    path,
                )
            )

    elif isinstance(value, list):
        for index, item in enumerate(value[:3]):
            path = f"{prefix}[{index}]"

            paths.append(path)

            paths.extend(
                collect_paths(
                    item,
                    path,
                )
            )

    return paths


def main():
    files = sorted(
        path
        for path in RESPONSES_DIR.glob("*.json")
        if "__TEST" not in path.name and "__test_" not in path.name.lower()
    )

    if not files:
        print(f"No response files found in " f"{RESPONSES_DIR}")
        return

    print("=" * 120)
    print("UNKNOWN APPLY RESPONSE INSPECTION")
    print("=" * 120)

    print(f"Response files: {len(files)}")

    path_counter = Counter()
    top_level_counter = Counter()

    for index, path in enumerate(
        files,
        start=1,
    ):
        print("\n" + "=" * 120)
        print(f"[{index}] {path.name}")
        print("=" * 120)

        try:
            with path.open(
                encoding="utf-8",
            ) as f:
                response = json.load(f)

        except Exception as exc:
            print(f"FAILED TO READ: {exc}")
            continue

        if isinstance(response, dict):
            top_level_keys = list(response.keys())

            print(
                "Top-level keys:",
                top_level_keys,
            )

            for key in top_level_keys:
                top_level_counter[key] += 1

        else:
            print(
                "Top-level type:",
                type(response).__name__,
            )

        print("\nSTRUCTURE:")
        print(
            json.dumps(
                summarize_value(response),
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

        paths = collect_paths(response)

        path_counter.update(set(paths))

    print("\n" + "=" * 120)
    print("TOP-LEVEL KEY FREQUENCY")
    print("=" * 120)

    for key, count in top_level_counter.most_common():
        print(f"{count:3} | {key}")

    print("\n" + "=" * 120)
    print("COMMON RESPONSE PATHS")
    print("=" * 120)

    for path, count in path_counter.most_common():
        print(f"{count:3} | {path}")


if __name__ == "__main__":
    main()
