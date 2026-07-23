import re
from datetime import date, datetime
from typing import Any

# ==============================================================================
# Public resolver
# ==============================================================================


def resolve_answer(
    question: dict,
    profile: dict,
) -> Any:
    """
    Resolve a Naukri questionnaire question into a semantic answer.

    This layer returns semantic/profile values only.

    Payload conversion for:
        - Text Box
        - Radio Button
        - List Menu
        - Check Box

    is handled by serialize_answer().
    """

    text = (question.get("questionName") or "").strip()
    q = normalize(text)

    # ==========================================================================
    # Compensation
    # ==========================================================================

    if "expected" in q and ("ctc" in q or "salary" in q or "compensation" in q):
        if "inr" in q or "annual" in q:
            return profile.get("expected_ctc_inr")

        return profile.get("expected_ctc_lpa")

    if "current" in q and ("ctc" in q or "salary" in q or "compensation" in q):
        if "inr" in q or "annual" in q:
            return profile.get("current_ctc_inr")

        return profile.get("current_ctc_lpa")

    # ==========================================================================
    # Notice period / joining
    # ==========================================================================

    if "notice period" in q:
        return profile.get("notice_period_days", 30)

    if (
        "how soon can you join" in q
        or "when can you join" in q
        or "joining time" in q
        or "how early can you join" in q
    ):
        return profile.get("notice_period_days", 30)

    if "last working day" in q:
        return profile.get("last_working_day")

    # ==========================================================================
    # Sensitive personal fields
    # ==========================================================================

    if "pan number" in q or "pan no" in q or q == "pan":
        return profile.get("pan_number")

    if "date of birth" in q or "dob" in q:
        return profile.get("date_of_birth")

    if "whatsapp number" in q or "whatsapp mobile" in q:
        return profile.get("whatsapp_number")

    if "address with pincode" in q or "address with pin code" in q:
        return profile.get("address_with_pincode")

    # ==========================================================================
    # Overall experience
    # ==========================================================================

    if any(
        phrase in q
        for phrase in (
            "total years of experience",
            "total year of experience",
            "total experience",
            "overall experience",
            "overall years of experience",
            "total years experience",
        )
    ):
        return profile.get("total_experience_years")

    # ==========================================================================
    # Specific experience questions
    #
    # Specific technologies must be checked before broad AI categories.
    # ==========================================================================

    if contains_experience_question(q):

        # ----------------------------------------------------------------------
        # MCP
        # ----------------------------------------------------------------------

        if "mcp connector" in q:
            return profile.get(
                "mcp_connector_experience_years",
                profile.get("default_unmapped_experience_years", 2),
            )

        if re.search(r"\bmcp\b", q):
            return profile.get(
                "mcp_experience_years",
                profile.get("default_unmapped_experience_years", 2),
            )

        # ----------------------------------------------------------------------
        # RAG
        # ----------------------------------------------------------------------

        if "retrieval augmented generation" in q or re.search(r"\brag\b", q):
            return profile.get(
                "rag_experience_years",
                3,
            )

        # ----------------------------------------------------------------------
        # Agentic AI
        # ----------------------------------------------------------------------

        if any(
            phrase in q
            for phrase in (
                "agentic ai",
                "aiagents",
                "ai agents",
                "ai agent",
            )
        ):
            return profile.get(
                "agentic_ai_experience_years",
                3,
            )

        # ----------------------------------------------------------------------
        # LangGraph
        # ----------------------------------------------------------------------

        if "langgraph" in q or "lang graph" in q:
            return profile.get(
                "langgraph_experience_years",
                2,
            )

        # ----------------------------------------------------------------------
        # LangChain
        # ----------------------------------------------------------------------

        if "langchain" in q or "lang chain" in q:
            return profile.get(
                "langchain_experience_years",
                2,
            )

        # ----------------------------------------------------------------------
        # LLM
        # ----------------------------------------------------------------------

        if "large language model" in q or re.search(r"\bllms?\b", q):
            return profile.get(
                "llm_experience_years",
                3,
            )

        # ----------------------------------------------------------------------
        # Generative AI
        #
        # Includes common recruiter typo: Genrative AI
        # ----------------------------------------------------------------------

        if any(
            phrase in q
            for phrase in (
                "generative ai",
                "genrative ai",
                "gen ai",
                "genai",
                "gen-ai",
            )
        ):
            return profile.get(
                "genai_experience_years",
                3,
            )

        # ----------------------------------------------------------------------
        # Vector databases
        # ----------------------------------------------------------------------

        if "vector database" in q or "vector db" in q:
            return profile.get(
                "vector_db_experience_years",
                2,
            )

        # ----------------------------------------------------------------------
        # Chatbots
        # ----------------------------------------------------------------------

        if "chatbot" in q:
            return profile.get(
                "chatbot_experience_years",
                2,
            )

        # ----------------------------------------------------------------------
        # NLP
        # ----------------------------------------------------------------------

        if "natural language processing" in q or re.search(r"\bnlp\b", q):
            return profile.get(
                "nlp_experience_years",
                2,
            )

        # ----------------------------------------------------------------------
        # Prompt Engineering
        # ----------------------------------------------------------------------

        if "prompt engineering" in q:
            return profile.get(
                "prompt_engineering_experience_years",
                3,
            )

        # ----------------------------------------------------------------------
        # AI Evaluation
        # ----------------------------------------------------------------------

        if "ai evaluation" in q:
            return profile.get(
                "ai_evaluation_experience_years",
                2,
            )

        # ----------------------------------------------------------------------
        # Computer Vision
        # ----------------------------------------------------------------------

        if "computer vision" in q or "comptuer vision" in q or "comupter vision" in q:
            return profile.get(
                "computer_vision_experience_years",
                profile.get("default_unmapped_experience_years", 2),
            )

        # ----------------------------------------------------------------------
        # Machine Learning / Deep Learning / ML
        # ----------------------------------------------------------------------

        if "machine learning" in q or "deep learning" in q or re.search(r"\bml\b", q):
            return profile.get(
                "machine_learning_experience_years",
                3,
            )

        # ----------------------------------------------------------------------
        # Azure ML
        # ----------------------------------------------------------------------

        if "azure machine learning" in q or "azure ml" in q:
            return profile.get(
                "azure_ml_experience_years",
                profile.get("azure_experience_years", 2),
            )

        # ----------------------------------------------------------------------
        # OpenAI
        # ----------------------------------------------------------------------

        if "open ai" in q or "openai" in q or "azure openai" in q:
            return profile.get(
                "openai_experience_years",
                2,
            )

        # ----------------------------------------------------------------------
        # Broad AI
        # ----------------------------------------------------------------------

        if any(
            phrase in q
            for phrase in (
                "artificial intelligence",
                "ai automation",
                "intelligent ai assistant",
                "gen ai application",
                "genai application",
                "ai/ ml",
                "ai/ml",
                "aiml",
                "ai engineer",
            )
        ):
            return profile.get(
                "ai_experience_years",
                3,
            )

        # ----------------------------------------------------------------------
        # Python
        # ----------------------------------------------------------------------

        if "python" in q:
            return profile.get(
                "python_experience_years",
                3,
            )

        # ----------------------------------------------------------------------
        # TypeScript
        # ----------------------------------------------------------------------

        if "typescript" in q:
            return profile.get(
                "typescript_experience_years",
                4,
            )

        # ----------------------------------------------------------------------
        # Angular
        # ----------------------------------------------------------------------

        if "angular" in q:
            return profile.get(
                "angular_experience_years",
                4,
            )

        # ----------------------------------------------------------------------
        # Node.js
        # ----------------------------------------------------------------------

        if (
            "node.js" in q
            or "nodejs" in q
            or "node js" in q
            or re.search(r"\bnode\b", q)
        ):
            return profile.get(
                "node_experience_years",
                3,
            )

        # ----------------------------------------------------------------------
        # Full-stack development
        # ----------------------------------------------------------------------

        if (
            "fullstack development" in q
            or "full stack development" in q
            or ".net fullstack" in q
        ):
            return profile.get(
                "fullstack_experience_years",
                profile.get("default_unmapped_experience_years", 2),
            )

        # ----------------------------------------------------------------------
        # .NET
        # ----------------------------------------------------------------------

        if ".net" in q or "dotnet" in q:
            return profile.get(
                "dotnet_experience_years",
                profile.get("default_unmapped_experience_years", 2),
            )

        # ----------------------------------------------------------------------
        # API Development
        # ----------------------------------------------------------------------

        if "api development" in q or "api developer" in q:
            return profile.get(
                "api_development_experience_years",
                2,
            )

        # ----------------------------------------------------------------------
        # SQL
        # ----------------------------------------------------------------------

        if re.search(r"\bsql\b", q):
            return profile.get(
                "sql_experience_years",
                2,
            )

        # ----------------------------------------------------------------------
        # Databricks
        # ----------------------------------------------------------------------

        if "data bricks" in q or "databricks" in q:
            return profile.get(
                "databricks_experience_years",
                profile.get("default_unmapped_experience_years", 2),
            )

        # ----------------------------------------------------------------------
        # Azure
        # ----------------------------------------------------------------------

        if "azure" in q:
            return profile.get(
                "azure_experience_years",
                2,
            )

        # ----------------------------------------------------------------------
        # AWS
        # ----------------------------------------------------------------------

        if re.search(r"\baws\b", q):
            return profile.get(
                "aws_experience_years",
                2,
            )

        # ----------------------------------------------------------------------
        # Cloud
        # ----------------------------------------------------------------------

        if "cloud" in q:
            return profile.get(
                "cloud_experience_years",
                2,
            )

        # ----------------------------------------------------------------------
        # Generic unmapped experience question
        # ----------------------------------------------------------------------

        return profile.get(
            "default_unmapped_experience_years",
            2,
        )

    # ==========================================================================
    # Location / relocation
    # ==========================================================================

    if (
        q == "current location"
        or "what is your current location" in q
        or "your current location" in q
    ):
        return profile.get(
            "current_location",
            "Pune",
        )

    if q == "preferred location" or "preferred location" in q:
        return profile.get(
            "preferred_location",
            "Pune",
        )

    if "south delhi" in q and ("relocate" in q or "staying" in q or "living" in q):
        return "Yes"

    if "select the city" in q and (
        "currently residing" in q or "willing to relocate" in q
    ):
        return choose_location_answer(
            question=question,
            profile=profile,
        )

    if any(
        phrase in q
        for phrase in (
            "willing to relocate",
            "ready to relocate",
            "can relocate",
            "currently living in or ready to relocate",
            "currently residing in or willing to relocate",
            "currently residing or willing to relocate",
        )
    ):
        return "Yes"

    # ==========================================================================
    # Employment history
    # ==========================================================================

    if any(
        phrase in q
        for phrase in (
            "ex-employee of infosys",
            "ex employee of infosys",
            "ex infy",
        )
    ):
        former_employee = normalize(
            str(
                profile.get(
                    "former_infosys_employee",
                    "No",
                )
            )
        )

        if former_employee == "no":
            return "NA"

        return profile.get("infosys_employee_id")

    # ==========================================================================
    # Career break
    # ==========================================================================

    if "career break" in q or "are you on a career break" in q:
        return profile.get(
            "on_career_break",
            "No",
        )

    # ==========================================================================
    # Offer status
    # ==========================================================================

    if any(
        phrase in q
        for phrase in (
            "offer in hand",
            "offers in hand",
            "holding any offers",
        )
    ):
        return profile.get(
            "has_offer_in_hand",
            "No",
        )

    # ==========================================================================
    # Contract / employment type
    # ==========================================================================

    if "12 month fte" in q or "interested for 12 month fte" in q:
        return profile.get(
            "accept_fte",
            "Yes",
        )

    if (
        "1 year contract" in q
        or "one year contract" in q
        or ("contract role" in q and "1 year" in q)
    ):
        return profile.get(
            "accept_one_year_contract",
            "Yes",
        )

    if "contract to hire" in q or "contract-to-hire" in q or "c2h" in q:
        return profile.get(
            "accept_contract_to_hire",
            "Yes",
        )

    if (
        "interested working with accenture fte" in q
        or "interested in accenture fte" in q
    ):
        return "Yes"

    # ==========================================================================
    # Work arrangements
    # ==========================================================================

    if (
        "working remotely" in q
        or "comfortable working remotely" in q
        or ("work remotely" in q and "visit" in q)
    ):
        return "Yes"

    if "alternate saturday" in q:
        return "Yes"

    if "work from office" in q or "work from office" in q or "wfo" in q:
        return "Yes"

    # ==========================================================================
    # Interview availability
    #
    # User policy: answer Yes for interview availability.
    # Do not reject because the mentioned date is past.
    # ==========================================================================

    if any(
        phrase in q
        for phrase in (
            "available for interview",
            "available for virtual interview",
            "available for inperson interview",
            "available for in-person interview",
            "available to attend an in-person interview",
            "available to attend interview",
            "available on",
            "hiring event",
            "weekend drive",
            "f2f interview",
            "face to face interview",
            "in person face to face interview",
            "in-person face to face interview",
        )
    ):
        return "Yes"

    if "hacker rank" in q or "hackerrank" in q:
        return "Yes"

    # ==========================================================================
    # Domain experience
    # ==========================================================================

    if "edtech domain" in q:
        return profile.get(
            "edtech_experience",
            "No",
        )

    # ==========================================================================
    # Descriptive recruiter questions
    # ==========================================================================

    if (
        "reason of job change" in q
        or "reason for job change" in q
        or "reason for change" in q
    ):
        return profile.get(
            "reason_for_job_change",
            (
                "Looking for a role focused on production Generative AI, "
                "RAG and agentic AI systems with greater technical ownership."
            ),
        )

    if "which llm frameworks" in q or "llm frameworks have you worked" in q:
        return profile.get(
            "llm_frameworks",
            "LangChain, LangGraph, Hugging Face and Ollama",
        )

    if "which vector databases" in q or "vector databases have you worked" in q:
        return profile.get(
            "vector_databases",
            "FAISS and Chroma, with approximately 2 years of hands-on experience.",
        )

    if "which cloud platform" in q and ("azure openai" in q or "aws bedrock" in q):
        return profile.get(
            "preferred_cloud_platform",
            "Azure OpenAI",
        )

    if "how have you used docker" in q or "docker in deploying ai" in q:
        return profile.get(
            "docker_usage",
            (
                "Used Docker to containerize FastAPI-based AI services, "
                "RAG pipelines and model integration services for consistent "
                "local, CI/CD and cloud deployment environments."
            ),
        )

    if "worked on generative ai" in q and ("rag" in q or "llm" in q):
        return profile.get(
            "genai_application_summary",
            (
                "Yes. Built production-oriented Generative AI applications "
                "using RAG, hybrid retrieval, reranking, vector databases, "
                "prompt engineering, LLM evaluation and agentic workflows."
            ),
        )

    if "hands-on experience with mlops" in q or "hands on experience with mlops" in q:
        return profile.get(
            "mlops_summary",
            (
                "Yes. Hands-on experience with Docker, GitHub Actions, "
                "CI/CD, API deployment and Azure-based AI application deployment."
            ),
        )

    # ==========================================================================
    # Production AI capability questions
    # ==========================================================================

    # if "deployed llms" in q or "deployed llm" in q or "deployed slms" in q:
    #     return "Yes"

    # if "vllm" in q or "ollama frameworks" in q or "ollama framework" in q:
    #     return "Yes"

    # if (
    #     "fastapi-based model serving" in q
    #     or "fastapi based model serving" in q
    #     or ("fastapi" in q and "microservices" in q)
    # ):
    #     return "Yes"

    if "rag/context engineering" in q or "rag context engineering" in q:
        return "Yes"

    # if "lora" in q or "qlora" in q or "quantization" in q:
    #     return "Yes"

    # ==========================================================================
    # Production AI capability questions
    # ==========================================================================

    # if (
    #     "deployed llms" in q
    #     or "deployed llm" in q
    #     or "deployed slms" in q
    #     or "deployed slm" in q
    # ):
    #     return "Yes"

    # if (
    #     re.search(r"\bvllm\b", q)
    #     or "ollama frameworks" in q
    #     or "ollama framework" in q
    #     or re.search(r"\bollama\b", q)
    # ):
    #     return "Yes"

    # ==========================================================================
    # Tech Mahindra GenAI use-case descriptive questions
    # ==========================================================================

    if "which specific llm or embedding model" in q or (
        "llm or embedding model" in q and "why" in q
    ):
        return profile.get(
            "production_model_summary",
            (
                "Azure OpenAI GPT models for generation and "
                "text embedding models for retrieval, selected for strong "
                "enterprise integration, quality, latency and Azure ecosystem support."
            ),
        )

    if (
        "how long is the gen ai use-case deployed" in q
        or "how long is the gen ai use case deployed" in q
    ):
        return profile.get(
            "genai_production_duration",
            "Approximately 2 years",
        )

    # if (
    #     "how many user are currently using" in q
    #     or "how many users are currently using" in q
    # ):
    #     return profile.get(
    #         "genai_production_users",
    #         "100+ users",
    #     )

    if "indicative roi" in q or "metric improved" in q:
        return profile.get(
            "genai_roi_summary",
            (
                "Reduced response and information retrieval time, "
                "improved answer consistency and reduced manual support effort."
            ),
        )

    # if "non functional requirement" in q or "non-functional requirement" in q:
    #     return profile.get(
    #         "genai_nfr_summary",
    #         (
    #             "Latency, availability, scalability, observability, "
    #             "rate limiting, caching, retries, circuit breaking, "
    #             "security and response validation."
    #         ),
    #     )

    # ==========================================================================
    # Full-stack descriptive questions
    # ==========================================================================

    if "describe one full stack project" in q or "describe one fullstack project" in q:
        return profile.get(
            "fullstack_project_summary",
            (
                "Built and maintained enterprise Angular and Node.js applications "
                "with REST APIs, authentication, reusable UI architecture, "
                "backend integrations and CI/CD support. My role covered feature "
                "design, frontend and backend implementation, API integration, "
                "code reviews, debugging and production support."
            ),
        )

    if "react native apps" in q and ("play store" in q or "app store" in q):
        return profile.get(
            "react_native_apps_summary",
            "0",
        )

    # ==========================================================================
    # Previous application question
    # ==========================================================================

    if "applied for accenture" in q and "past one year" in q:
        return profile.get(
            "applied_accenture_last_year",
            "No",
        )

    # ==========================================================================
    # Cloud descriptive question
    # ==========================================================================

    if "working experience with any cloud" in q or "mention in which cloud" in q:
        return profile.get(
            "cloud_platforms",
            "Azure and AWS",
        )

    # ==========================================================================
    # Generic affirmative policy
    #
    # This is intentionally after specific questions.
    # ==========================================================================

    affirmative_markers = (
        "are you comfortable",
        "are you willing",
        "are you ready",
        "will you be available",
        "are you available",
        "can you attend",
        "can you relocate",
    )

    if any(marker in q for marker in affirmative_markers):
        return "Yes"

    # ==========================================================================
    # Generic experience fallback
    #
    # User policy:
    # unmapped experience question -> 2 years
    # ==========================================================================

    if contains_experience_question(q):
        return profile.get(
            "default_unmapped_experience_years",
            2,
        )

    return None


# ==============================================================================
# Serialization
# ==============================================================================


def serialize_answer(
    question: dict,
    semantic_value: Any,
) -> Any:
    """
    Convert semantic values to the payload representation expected by Naukri.
    """

    question_type = normalize(question.get("questionType") or "")

    # ==========================================================================
    # Text
    # ==========================================================================

    if question_type in {
        "text box",
        "textbox",
        "text",
        "textarea",
        "text area",
    }:
        return str(semantic_value)

    # ==========================================================================
    # Single-select
    # ==========================================================================

    if question_type in {
        "radio button",
        "radio",
        "single select",
        "single-select",
        "dropdown",
        "drop down",
        "list menu",
    }:
        option_id = match_option(
            question=question,
            semantic_value=str(semantic_value),
        )

        if option_id is None:
            return None

        return [option_id]

    # ==========================================================================
    # Multi-select
    # ==========================================================================

    if question_type in {
        "checkbox",
        "check box",
        "multi select",
        "multi-select",
        "multiple select",
    }:
        values = (
            semantic_value if isinstance(semantic_value, list) else [semantic_value]
        )

        selected = []

        for value in values:
            option_id = match_option(
                question=question,
                semantic_value=str(value),
            )

            if option_id is None:
                return None

            selected.append(option_id)

        return selected

    return None


# ==============================================================================
# Option matching
# ==============================================================================


def match_option(
    question: dict,
    semantic_value: str,
) -> str | None:
    """
    Match a semantic answer to a Naukri option ID.
    """

    options = question.get("answerOption") or {}

    if not options:
        return None

    value = str(semantic_value).strip()
    value_normalized = normalize(value)
    question_text = normalize(question.get("questionName") or "")

    # ==========================================================================
    # Exact option-label match
    # ==========================================================================

    for option_id, label in options.items():
        if normalize(str(label)) == value_normalized:
            return str(option_id)

    # ==========================================================================
    # Yes / No matching
    #
    # Also handles:
    #   Yes, willing
    #   Yes - Available
    #   No, not currently
    # ==========================================================================

    if value_normalized in {"yes", "no"}:
        for option_id, label in options.items():
            label_normalized = normalize(str(label))

            if value_normalized == "yes":
                if (
                    label_normalized == "yes"
                    or label_normalized.startswith("yes ")
                    or label_normalized.startswith("yes,")
                    or label_normalized.startswith("yes -")
                ):
                    return str(option_id)

            if value_normalized == "no":
                if (
                    label_normalized == "no"
                    or label_normalized.startswith("no ")
                    or label_normalized.startswith("no,")
                    or label_normalized.startswith("no -")
                ):
                    return str(option_id)

        return None

    # ==========================================================================
    # Text/location matching
    # ==========================================================================

    if not is_numeric(value):
        return match_text_option(
            options=options,
            semantic_value=value,
        )

    numeric_value = float(value)

    # ==========================================================================
    # Joining availability
    # ==========================================================================

    if any(
        phrase in question_text
        for phrase in (
            "how soon can you join",
            "when can you join",
            "joining time",
            "how early can you join",
        )
    ):
        return match_joining_window_option(
            options=options,
            days=numeric_value,
        )

    # ==========================================================================
    # Notice period
    # ==========================================================================

    if "notice period" in question_text:
        return match_notice_period_option(
            options=options,
            days=numeric_value,
        )

    # ==========================================================================
    # Experience
    # ==========================================================================

    if contains_experience_question(question_text):
        return match_experience_option(
            options=options,
            years=numeric_value,
        )

    return None


# ==============================================================================
# Notice-period matching
# ==============================================================================


def match_notice_period_option(
    options: dict,
    days: float,
) -> str | None:
    """
    Match notice period against recruiter option labels.
    """

    normalized_options = {
        str(option_id): normalize(str(label)) for option_id, label in options.items()
    }

    # Exact 30-day / 1-month preference

    if days <= 30:
        preferred_patterns = (
            "1 month",
            "30 days",
            "30 day",
            "within 30 days",
            "within 1 month",
        )

        for option_id, text in normalized_options.items():
            if any(pattern in text for pattern in preferred_patterns):
                return option_id

    # 15 days or less

    if days <= 15:
        for option_id, text in normalized_options.items():
            if "15 day" in text and (
                "less" in text or "within" in text or "or less" in text
            ):
                return option_id

    # 2 months / 60 days

    if days <= 60:
        for option_id, text in normalized_options.items():
            if "2 month" in text or "60 day" in text:
                return option_id

    # 3 months / 90 days

    if days <= 90:
        for option_id, text in normalized_options.items():
            if ("3 month" in text or "90 day" in text) and "more than" not in text:
                return option_id

    # Generic range parser

    range_match = match_days_range_option(
        options=options,
        days=days,
    )

    if range_match is not None:
        return range_match

    # Immediate joiner fallback only for zero days

    if days <= 0:
        for option_id, text in normalized_options.items():
            if "immediate" in text or "immediately" in text:
                return option_id

    return None


# ==============================================================================
# Experience matching
# ==============================================================================


def match_experience_option(
    options: dict,
    years: float,
) -> str | None:
    """
    Match numeric years against common recruiter experience buckets.
    """

    # Exact numeric labels first

    for option_id, label in options.items():
        text = normalize(str(label))

        match = re.fullmatch(
            r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)?",
            text,
        )

        if match:
            exact = float(match.group(1))

            if years == exact:
                return str(option_id)

    # Semantic buckets

    candidates = []

    for option_id, label in options.items():
        text = normalize(str(label))

        # No experience

        if "no experience" in text or "fresher" in text:
            if years <= 0:
                return str(option_id)

        # Less than N

        match = re.search(
            r"less than\s*(\d+(?:\.\d+)?)",
            text,
        )

        if match:
            upper = float(match.group(1))

            if years < upper:
                candidates.append(
                    (
                        upper,
                        str(option_id),
                    )
                )

        # < N

        match = re.search(
            r"<\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)?",
            text,
        )

        if match:
            upper = float(match.group(1))

            if years < upper:
                candidates.append(
                    (
                        upper,
                        str(option_id),
                    )
                )

        # More than N

        match = re.search(
            r"more than\s*(\d+(?:\.\d+)?)",
            text,
        )

        if match:
            lower = float(match.group(1))

            if years > lower:
                candidates.append(
                    (
                        1000 + lower,
                        str(option_id),
                    )
                )

        # > N

        match = re.search(
            r">\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)?",
            text,
        )

        if match:
            lower = float(match.group(1))

            if years > lower:
                candidates.append(
                    (
                        1000 + lower,
                        str(option_id),
                    )
                )

        # N - M

        match = re.search(
            r"(\d+(?:\.\d+)?)"
            r"\s*(?:-|to)\s*"
            r"(\d+(?:\.\d+)?)"
            r"(?:\s*(?:years?|yrs?))?",
            text,
        )

        if match:
            lower = float(match.group(1))
            upper = float(match.group(2))

            if lower <= years <= upper:
                candidates.append(
                    (
                        upper - lower,
                        str(option_id),
                    )
                )

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])

    return candidates[0][1]


# ==============================================================================
# Joining-window matching
# ==============================================================================


def match_joining_window_option(
    options: dict,
    days: float,
) -> str | None:
    """
    Match joining availability against recruiter-defined day windows.
    """

    candidates = []

    for option_id, label in options.items():
        text = normalize(str(label))

        # Within N days

        match = re.search(
            r"within\s+(\d+)\s*days?",
            text,
        )

        if match and "-" not in text and " to " not in text:
            upper = float(match.group(1))

            if days <= upper:
                candidates.append(
                    (
                        upper,
                        str(option_id),
                    )
                )

            continue

        # Within N-M days
        # Within N to M days

        match = re.search(
            r"within\s+"
            r"(\d+(?:\.\d+)?)"
            r"\s*(?:-|to)\s*"
            r"(\d+(?:\.\d+)?)"
            r"\s*days?",
            text,
        )

        if match:
            lower = float(match.group(1))
            upper = float(match.group(2))

            if lower <= days <= upper:
                candidates.append(
                    (
                        upper - lower,
                        str(option_id),
                    )
                )

    if candidates:
        candidates.sort(key=lambda item: item[0])

        return candidates[0][1]

    return match_days_range_option(
        options=options,
        days=days,
    )


# ==============================================================================
# Generic day-range matcher
# ==============================================================================


def match_days_range_option(
    options: dict,
    days: float,
) -> str | None:
    candidates = []

    for option_id, label in options.items():
        text = normalize(str(label))

        match = re.search(
            r"(\d+(?:\.\d+)?)" r"\s*(?:-|to)\s*" r"(\d+(?:\.\d+)?)" r"\s*days?",
            text,
        )

        if not match:
            continue

        lower = float(match.group(1))
        upper = float(match.group(2))

        if lower <= days <= upper:
            candidates.append(
                (
                    upper - lower,
                    str(option_id),
                )
            )

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])

    return candidates[0][1]


# ==============================================================================
# Location selection
# ==============================================================================


def choose_location_answer(
    question: dict,
    profile: dict,
) -> str | list[str] | None:
    """
    Choose one or more location labels based on candidate preference ranking.

    Returns labels, not IDs. serialize_answer() converts labels to IDs.
    """

    options = question.get("answerOption") or {}

    if not options:
        return None

    current_location = normalize(profile.get("current_location", "Pune"))

    relocation_preferences = [
        normalize(location)
        for location in profile.get(
            "relocation_preferences",
            [
                "Pune",
                "Bengaluru",
                "Hyderabad",
                "Mumbai",
                "Chennai",
                "Noida",
                "Gurugram",
                "Delhi",
                "Kolkata",
                "Ahmedabad",
            ],
        )
    ]

    ranked_locations = []

    if current_location:
        ranked_locations.append(current_location)

    for location in relocation_preferences:
        if location not in ranked_locations:
            ranked_locations.append(location)

    matched_labels = []

    for wanted_location in ranked_locations:
        for _, label in options.items():
            label_normalized = normalize(str(label))

            if location_matches(
                wanted=wanted_location,
                candidate=label_normalized,
            ):
                label_string = str(label)

                if label_string not in matched_labels:
                    matched_labels.append(label_string)

    if not matched_labels:
        return None

    question_type = normalize(question.get("questionType") or "")

    if question_type in {
        "checkbox",
        "check box",
        "multi select",
        "multi-select",
        "multiple select",
    }:
        return matched_labels

    return matched_labels[0]


# ==============================================================================
# Text option matching
# ==============================================================================


def match_text_option(
    options: dict,
    semantic_value: str,
) -> str | None:
    wanted = normalize(semantic_value)

    if not wanted:
        return None

    # Exact first

    for option_id, label in options.items():
        candidate = normalize(str(label))

        if wanted == candidate:
            return str(option_id)

    # Partial/location matching

    for option_id, label in options.items():
        candidate = normalize(str(label))

        if location_matches(
            wanted=wanted,
            candidate=candidate,
        ):
            return str(option_id)

    return None


def location_matches(
    wanted: str,
    candidate: str,
) -> bool:
    wanted = normalize(wanted)
    candidate = normalize(candidate)

    if not wanted or not candidate:
        return False

    if wanted == candidate:
        return True

    if wanted in candidate:
        return True

    if candidate in wanted:
        return True

    aliases = {
        "bangalore": "bengaluru",
        "bengaluru": "bangalore",
        "gurgaon": "gurugram",
        "gurugram": "gurgaon",
        "new delhi": "delhi",
        "delhi": "new delhi",
    }

    wanted_alias = aliases.get(wanted)

    if wanted_alias and (wanted_alias == candidate or wanted_alias in candidate):
        return True

    candidate_alias = aliases.get(candidate)

    if candidate_alias and (candidate_alias == wanted or candidate_alias in wanted):
        return True

    return False


# ==============================================================================
# Date helpers
# ==============================================================================


MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def extract_date_from_text(
    text: str,
) -> date | None:
    normalized = normalize(text)

    pattern = re.compile(
        r"\b"
        r"(\d{1,2})"
        r"(?:st|nd|rd|th)?"
        r"\s+"
        r"(" + "|".join(MONTHS.keys()) + r")"
        r"(?:\s+(\d{4}))?"
        r"\b"
    )

    match = pattern.search(normalized)

    if not match:
        return None

    day = int(match.group(1))
    month = MONTHS[match.group(2)]

    year = int(match.group(3)) if match.group(3) else datetime.now().year

    try:
        return date(
            year,
            month,
            day,
        )
    except ValueError:
        return None


def interview_date_is_past(
    text: str,
) -> bool:
    """
    Retained for diagnostics.

    Current resolver policy intentionally answers Yes to interview
    availability questions even when recruiter text contains an old date.
    """

    extracted = extract_date_from_text(text)

    if extracted is None:
        return False

    return extracted < date.today()


# ==============================================================================
# Generic helpers
# ==============================================================================


def contains_experience_question(
    q: str,
) -> bool:
    """
    Return True only for questions asking for a numeric duration
    of experience.

    Descriptive questions such as:
        "Describe your experience with RAG"
        "Explain your experience building AI systems"

    must not enter the numeric experience resolver.
    """

    quantitative_patterns = (
        r"\bhow many years\b",
        r"\bhow many year\b",
        r"\byears of experience\b",
        r"\byear of experience\b",
        r"\byears experience\b",
        r"\byear experience\b",
        r"\bexperience in years\b",
        r"\bexperience \(years\)\b",
        r"\bexperience \(in years\)\b",
        r"\bnumber of years\b",
        r"\bno\.? of years\b",
        r"\btotal years\b",
    )

    return any(re.search(pattern, q) for pattern in quantitative_patterns)


def is_numeric(
    value: str,
) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def normalize(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value).strip().lower(),
    )
