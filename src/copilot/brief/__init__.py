"""Application Brief (CP-2-01).

Frozen contract ``05_APPLICATION_BRIEF.md`` (ADR-013): the intelligence
briefing produced before the user opens the apply flow. This module holds
the :class:`ApplicationBrief` shape plus the deterministic aggregation that
fills its CP-2-01 sections (verdict, fit breakdown, missing skills, resume
recommendation, strategy, risk flags, provenance summary). Later sections
(salary CP-2-02, effort CP-2-03, probability CP-2-04, questions CP-2-05)
are added additively by their tasks.
"""
