from src.application.lifecycle import (
    LifecycleStage,
    normalize_server_status,
    should_advance_lifecycle,
)


def test_application_sent_maps_to_submitted():
    assert normalize_server_status("Application Sent") == LifecycleStage.SUBMITTED


def test_viewed_maps_to_viewed():
    assert normalize_server_status("Application Viewed") == LifecycleStage.VIEWED


def test_shortlisted_maps_to_shortlisted():
    assert normalize_server_status("Profile Shortlisted") == LifecycleStage.SHORTLISTED


def test_interview_maps_to_interview():
    assert normalize_server_status("Interview Scheduled") == LifecycleStage.INTERVIEW


def test_rejected_maps_to_rejected():
    assert normalize_server_status("Not Selected") == LifecycleStage.REJECTED


def test_offer_maps_to_offer():
    assert normalize_server_status("Offer Released") == LifecycleStage.OFFER


def test_unknown_status_remains_unknown():
    assert normalize_server_status("Recruiter Processing") == LifecycleStage.UNKNOWN


def test_unknown_does_not_overwrite_meaningful_stage():
    assert (
        should_advance_lifecycle(
            LifecycleStage.SUBMITTED,
            LifecycleStage.UNKNOWN,
        )
        is False
    )


def test_forward_progression_is_allowed():
    assert (
        should_advance_lifecycle(
            LifecycleStage.SUBMITTED,
            LifecycleStage.VIEWED,
        )
        is True
    )


def test_backward_progression_is_rejected():
    assert (
        should_advance_lifecycle(
            LifecycleStage.INTERVIEW,
            LifecycleStage.VIEWED,
        )
        is False
    )


def test_rejected_can_terminate_interview():
    assert (
        should_advance_lifecycle(
            LifecycleStage.INTERVIEW,
            LifecycleStage.REJECTED,
        )
        is True
    )


def test_offer_is_sticky():
    assert (
        should_advance_lifecycle(
            LifecycleStage.OFFER,
            LifecycleStage.REJECTED,
        )
        is False
    )


def test_offer_can_correct_rejected_state():
    assert (
        should_advance_lifecycle(
            LifecycleStage.REJECTED,
            LifecycleStage.OFFER,
        )
        is True
    )
