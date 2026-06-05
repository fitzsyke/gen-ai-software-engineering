"""
test_categorization.py — Unit tests for the auto-classification service.

Tests classify() directly — no HTTP, no storage. Verifies keyword matching,
category/priority assignment, confidence scoring, and edge cases.

Coverage targets:
  src/services/classify_service.py — all code paths
"""

import pytest

from src.models.ticket import Category, Priority
from src.services.classify_service import (
    _collect_matched_keywords,
    _pick_best,
    _score_text,
    classify,
)
from src.services.classify_service import (
    _CATEGORY_KEYWORDS,
    _PRIORITY_KEYWORDS,
)


# ── Category classification ────────────────────────────────────────────────────


def test_classify_account_access():
    result = classify(
        "Cannot log into my account",
        "I forgot my password and the reset email is not arriving. I am locked out.",
    )
    assert result.category == Category.account_access
    assert result.category_confidence > 0.0


def test_classify_billing_question():
    result = classify(
        "Invoice question about refund",
        "I was charged twice for my subscription. I need a refund for the duplicate payment.",
    )
    assert result.category == Category.billing_question
    assert result.category_confidence > 0.0


def test_classify_technical_issue():
    result = classify(
        "Application crashes on startup",
        "I get an unhandled exception error every time I open the app. Not working at all.",
    )
    assert result.category == Category.technical_issue


def test_classify_feature_request():
    result = classify(
        "Feature request: dark mode",
        "It would be great if you could add dark mode support. Just a suggestion for improvement.",
    )
    assert result.category == Category.feature_request


def test_classify_bug_report():
    result = classify(
        "Bug: wrong result when filtering",
        "Steps to reproduce: filter by date. Expected behavior: correct results. Actual behavior: incorrect results shown.",
    )
    assert result.category == Category.bug_report


def test_classify_no_keywords_returns_other():
    result = classify("Hello", "I need some help please.")
    assert result.category == Category.other
    assert result.category_confidence == 0.5  # no-signal fallback


# ── Priority classification ────────────────────────────────────────────────────


def test_classify_urgent_priority():
    result = classify(
        "Production down - critical outage",
        "Our production environment is completely broken. This is a critical emergency.",
    )
    assert result.priority == Priority.urgent


def test_classify_high_priority():
    result = classify(
        "Important issue blocking the team",
        "This is a high priority problem that is blocking all team members. Need to escalate.",
    )
    assert result.priority == Priority.high


def test_classify_low_priority():
    result = classify(
        "Minor cosmetic issue",
        "This is a minor suggestion. No rush, whenever you get a chance. Low priority.",
    )
    assert result.priority == Priority.low


def test_classify_no_priority_keywords_returns_medium():
    result = classify("Hello", "I need some help please.")
    assert result.priority == Priority.medium
    assert result.priority_confidence == 0.5


# ── Confidence scoring ─────────────────────────────────────────────────────────


def test_classify_confidence_is_float_between_0_and_1():
    result = classify("Test subject", "I cannot log in to my account since yesterday.")
    assert 0.0 <= result.category_confidence <= 1.0
    assert 0.0 <= result.priority_confidence <= 1.0


def test_classify_high_confidence_dominant_category():
    """Strong keyword signal for one category → confidence should be well above 0.5."""
    result = classify(
        "Refund request for billing invoice",
        "I was charged and need a refund. The subscription invoice has an error. Payment failed.",
    )
    assert result.category == Category.billing_question
    assert result.category_confidence >= 0.5


def test_classify_tied_scores_return_other():
    """Equal hits across two categories → ambiguous → fallback to 'other' at 0.3."""
    # Force a tie by passing an empty text to _pick_best via _score_text
    scores = {"a": 2, "b": 2, "c": 0}
    label, confidence = _pick_best(scores, fallback="other")
    assert label == "other"
    assert confidence == 0.3


def test_classify_all_zero_scores_return_fallback():
    scores = {"a": 0, "b": 0, "c": 0}
    label, confidence = _pick_best(scores, fallback="other")
    assert label == "other"
    assert confidence == 0.5


# ── Matched keywords ──────────────────────────────────────────────────────────


def test_classify_matched_keywords_are_sorted_deduped():
    result = classify(
        "Password reset not working",
        "I cannot log in and my password reset is not working. I am locked out of my account.",
    )
    keywords = result.matched_keywords
    assert keywords == sorted(set(keywords))


def test_classify_matched_keywords_subset_of_all_keywords():
    """Every matched keyword must actually exist in the keyword dictionaries."""
    result = classify(
        "Billing invoice refund",
        "I was charged twice and need a refund for the duplicate subscription payment.",
    )
    all_kw = set()
    for kws in _CATEGORY_KEYWORDS.values():
        all_kw.update(kws)
    for kws in _PRIORITY_KEYWORDS.values():
        all_kw.update(kws)
    for kw in result.matched_keywords:
        assert kw in all_kw


def test_classify_empty_matched_keywords_when_no_hits():
    result = classify("Hello", "I need some help please.")
    assert result.matched_keywords == []


# ── classified_at timestamp ───────────────────────────────────────────────────


def test_classify_classified_at_is_set():
    result = classify("Test", "A long enough description for testing purposes.")
    assert result.classified_at is not None


# ── _score_text helper ────────────────────────────────────────────────────────


def test_score_text_case_insensitive():
    scores = _score_text("PASSWORD RESET LOGIN", {"account_access": ["password", "login"]})
    assert scores["account_access"] == 2


def test_score_text_each_keyword_counted_once():
    """A keyword appearing multiple times in text counts as 1 hit."""
    scores = _score_text(
        "billing billing billing",
        {"billing_question": ["billing"]},
    )
    assert scores["billing_question"] == 1


# ── _collect_matched_keywords helper ──────────────────────────────────────────


def test_collect_matched_keywords_from_both_maps():
    text = "billing urgent"
    keywords = _collect_matched_keywords(text, _CATEGORY_KEYWORDS, _PRIORITY_KEYWORDS)
    assert "billing" in keywords
    assert "urgent" in keywords
