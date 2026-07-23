from config.candidate_profile import CANDIDATE_PROFILE
from src.utils.questionnaire_resolver import (
    resolve_answer,
    serialize_answer,
)

TEST_QUESTIONS = [
    {
        "questionId": "1",
        "questionName": "How many years of experience do you have in RAG?",
        "questionType": "Radio Button",
        "answerOption": {
            "1": "No experience",
            "2": "<4 years",
            "3": "4-6 years",
            "4": "6-8 years",
            "5": "8-10 years",
            "6": ">10 years",
        },
    },
    {
        "questionId": "2",
        "questionName": "What is your notice period?",
        "questionType": "List Menu",
        "answerOption": {
            "0": "15 Days or less",
            "1": "1 Month",
            "2": "2 Months",
            "3": "3 Months",
            "4": "More than 3 Months",
            "5": "Serving Notice Period",
        },
    },
    {
        "questionId": "3",
        "questionName": (
            "Please select the city you are currently residing "
            "or willing to relocate to"
        ),
        "questionType": "Check Box",
        "answerOption": {
            "0": "Bhubaneswar",
            "1": "Hyderabad",
        },
    },
    {
        "questionId": "4",
        "questionName": (
            "Are you ex-employee of Infosys, if no mention NA, "
            "if yes please mention ex infy ID."
        ),
        "questionType": "Text Box",
        "answerOption": {},
    },
    {
        "questionId": "5",
        "questionName": ("Are you available for virtual interview on 1st July 2026"),
        "questionType": "Radio Button",
        "answerOption": {
            "1": "Yes",
            "2": "No",
        },
    },
    {
        "questionId": "6",
        "questionName": (
            "Level - 1 Interview is a test in Hacker Rank. "
            "Are you comfortable writing a hacker rank test?"
        ),
        "questionType": "Check Box",
        "answerOption": {
            "1": "Yes",
            "2": "No",
        },
    },
    {
        "questionId": "7",
        "questionName": "How soon can you join us, if you get selected?",
        "questionType": "Radio Button",
        "answerOption": {
            "newOption1": "Within 15 Days",
            "newOption2": "Within 15 - 30 Days",
            "newOption3": "Within 30 - 60 Days",
            "newOption4": "Within 60 - 90 Days",
        },
    },
]


def main():
    for question in TEST_QUESTIONS:
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

        print("=" * 100)
        print(f'Question:   {question["questionName"]}')
        print(f"Type:       {question['questionType']}")
        print(f"Semantic:   {semantic}")
        print(f"Serialized: {serialized}")


if __name__ == "__main__":
    main()
