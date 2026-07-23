import json
from pathlib import Path

RESPONSES_DIR = Path("data/responses")


def load_captures():
    files = sorted(
        path
        for path in RESPONSES_DIR.glob("*.json")
        if "__TEST" not in path.name and "__test_" not in path.name.lower()
    )

    captures = []

    for path in files:
        with path.open(
            encoding="utf-8",
        ) as f:
            capture = json.load(f)

        captures.append(
            (
                path,
                capture,
                capture.get("response") or {},
            )
        )

    return captures


def print_field(
    label,
    value,
):
    print(f"{label:<28}: {value!r}")


def main():
    captures = load_captures()

    print("=" * 120)
    print("UNKNOWN RESPONSE SEMANTIC INSPECTION")
    print("=" * 120)

    print(f"Responses: {len(captures)}")

    for index, (
        path,
        capture,
        response,
    ) in enumerate(
        captures,
        start=1,
    ):
        chatbot = response.get("chatbotResponse") or {}

        jobs = response.get("jobs") or []

        job = jobs[0] if jobs and isinstance(jobs[0], dict) else {}

        print("\n" + "=" * 120)
        print(f"[{index}] {path.name}")
        print("=" * 120)

        print_field(
            "capture job_id",
            capture.get("job_id"),
        )

        print_field(
            "capture stage",
            capture.get("stage"),
        )

        print_field(
            "statusCode",
            response.get("statusCode"),
        )

        print_field(
            "flowType",
            response.get("flowType"),
        )

        print_field(
            "applyRedirectUrl",
            response.get("applyRedirectUrl"),
        )

        print_field(
            "ncFlow",
            response.get("ncFlow"),
        )

        print_field(
            "aurusFlow",
            response.get("aurusFlow"),
        )

        print_field(
            "pzero",
            response.get("pzero"),
        )

        print_field(
            "jobId",
            job.get("jobId"),
        )

        print_field(
            "jobTitle",
            job.get("jobTitle"),
        )

        print_field(
            "companyName",
            job.get("companyName"),
        )

        print_field(
            "job.isCustom",
            job.get("isCustom"),
        )

        print("\nCHATBOT")

        print_field(
            "currentNodeName",
            chatbot.get("currentNodeName"),
        )

        print_field(
            "currentNode",
            chatbot.get("currentNode"),
        )

        print_field(
            "actionType",
            chatbot.get("actionType"),
        )

        print_field(
            "isApply",
            chatbot.get("isApply"),
        )

        print_field(
            "isLeafNode",
            chatbot.get("isLeafNode"),
        )

        print_field(
            "dataCommitted",
            chatbot.get("dataCommitted"),
        )

        print_field(
            "currentConversationName",
            chatbot.get("currentConversationName"),
        )

        input_data = chatbot.get("input") or {}

        print("\nINPUT")

        print_field(
            "input.name",
            input_data.get("name"),
        )

        print_field(
            "input.type",
            input_data.get("type"),
        )

        print_field(
            "input.placeholder",
            input_data.get("placeholder"),
        )

        print_field(
            "input.value",
            input_data.get("value"),
        )

        print("\nSPEECH")

        for speech_index, item in enumerate(
            chatbot.get("speechResponse") or [],
            start=1,
        ):
            print_field(
                f"speech[{speech_index}]",
                item.get("response") if isinstance(item, dict) else item,
            )

        print("\nOPTIONS")

        for option in chatbot.get("options") or []:
            if not isinstance(option, dict):
                print(option)
                continue

            print(
                {
                    "name": option.get("name"),
                    "value": option.get("value"),
                    "headline": option.get("headline"),
                    "type": option.get("type"),
                }
            )


if __name__ == "__main__":
    main()
