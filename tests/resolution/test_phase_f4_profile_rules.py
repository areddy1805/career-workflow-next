"""Phase F4 — optional candidate-evidence questionnaire rules.

The automation must never invent education history, gaps, employer type,
or payroll preferences.  These rules resolve ONLY when the candidate
explicitly supplied the fact in the profile (default None → manual review).
"""

from src.utils.questionnaire_resolver import resolve_answer


BASE = {
    "education_history": None,
    "has_education_gap": None,
    "education_gap_reason": None,
    "organization_type": None,
    "accept_direct_payroll": None,
}


def _q(text):
    return {"questionName": text}


def test_default_unconfigured_stays_unresolved():
    # Without candidate facts every one of these must stay None so the
    # LLM safety gate / manual-review path decides — never auto-answered.
    for text in (
        "Ug or degree or Graduation, If u done PG or master in fulltime - "
        "mention 10th, 12th, Diploma UG or PG - passing year for all.",
        "Is there any gap in between 10th,12th,Graduation,Postgraduation,"
        "Employment? if Yes, Please Specify the reason",
        "What type of organization you work in?",
        "Are you interested for Direct Payroll?",
    ):
        assert resolve_answer(_q(text), BASE) is None


def test_education_passing_year_from_profile():
    profile = dict(BASE)
    profile["education_history"] = {"10th": "2014", "12th": "2016", "ug": "2020"}
    answer = resolve_answer(
        _q("mention 10th, 12th, Diploma UG or PG - passing year for all"),
        profile,
    )
    assert answer == "10th: 2014 ; 12th: 2016 ; ug: 2020"


def test_education_passing_year_no_history_stays_none():
    assert (
        resolve_answer(
            _q("mention 10th, 12th, Diploma UG or PG - passing year for all"),
            dict(BASE),
        )
        is None
    )


def test_gap_no():
    profile = dict(BASE)
    profile["has_education_gap"] = "No"
    assert (
        resolve_answer(
            _q("Is there any gap in between 10th,12th,Graduation,"
               "Postgraduation,Employment? if Yes, Please Specify the reason"),
            profile,
        )
        == "No"
    )


def test_gap_reason_when_true():
    profile = dict(BASE)
    profile["has_education_gap"] = "Yes"
    profile["education_gap_reason"] = "Career break for family"
    assert (
        resolve_answer(
            _q("Is there any gap in between 10th,12th,Graduation,"
               "Postgraduation,Employment? if Yes, Please Specify the reason"),
            profile,
        )
        == "Career break for family"
    )


def test_organization_type():
    profile = dict(BASE)
    profile["organization_type"] = "Product"
    assert (
        resolve_answer(_q("What type of organization you work in?"), profile)
        == "Product"
    )
    assert resolve_answer(_q("What type of organization you work in?"), dict(BASE)) is None


def test_direct_payroll_preference():
    profile = dict(BASE)
    profile["accept_direct_payroll"] = "No"
    assert (
        resolve_answer(
            _q("Are you interested for Direct Payroll?"),
            profile,
        )
        == "No"
    )
    assert (
        resolve_answer(_q("Are you interested for Direct Payroll?"), dict(BASE))
        is None
    )
