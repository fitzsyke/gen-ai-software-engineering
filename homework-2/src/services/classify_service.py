"""
classify_service.py — Keyword-based auto-classification for support tickets.

Assigns a Category and Priority to a ticket based on keyword analysis of the
ticket's subject and description. Each assignment comes with a confidence score
(0.0–1.0) showing how strongly the text matched that label.

Algorithm overview:
  1. Build the search text: subject + " " + description (lowercased).
  2. For each Category, count how many of its keywords appear in the text.
  3. Pick the highest-scoring category.
     - If no keywords match: assign 'other' with confidence 0.5.
     - If top two scores are tied: assign 'other' with low confidence.
     - Otherwise: confidence = best_score / total_hits (dominance ratio).
  4. Repeat steps 2–3 for Priority (fallback: 'medium').
  5. Collect all matched keywords across every category/priority (deduped).

Public functions:
  classify(subject: str, description: str) -> ClassificationResult
"""

from datetime import datetime, timezone
from typing import Dict, List, Tuple

from ..models.ticket import Category, ClassificationResult, Priority


# ── Keyword dictionaries ───────────────────────────────────────────────────────
# Each keyword is a substring — it matches anywhere in the text (word or phrase).
# Keep keywords specific enough to avoid false positives.

_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    Category.account_access: [
        "login", "log in", "sign in", "signin", "password", "forgot password",
        "reset password", "locked out", "account access", "can't access",
        "cannot access", "authentication", "2fa", "two-factor", "two factor",
        "credentials", "invalid credentials", "unauthorized", "session expired",
        "account locked", "otp", "verification code",
    ],
    Category.technical_issue: [
        "error", "not working", "broken", "crash", "crashed", "slow",
        "performance", "timeout", "exception", "loading", "failed", "fails",
        "freeze", "frozen", "hung", "hang", "connection", "server error",
        "500", "503", "502", "gateway", "unavailable", "outage",
        "technical", "bug", "glitch",
    ],
    Category.billing_question: [
        "billing", "invoice", "payment", "charge", "charged", "refund",
        "subscription", "plan", "pricing", "price", "credit card", "debit",
        "receipt", "cost", "fee", "overcharged", "cancel", "cancellation",
        "upgrade", "downgrade", "trial", "discount", "promo", "coupon",
        "money", "paid", "purchase",
    ],
    Category.feature_request: [
        "feature request", "feature", "would like", "wish", "suggestion",
        "could you add", "please add", "add support", "new functionality",
        "enhancement", "improvement", "idea", "recommend", "propose",
        "requesting", "request for", "it would be great", "it would be helpful",
        "nice to have", "when will",
    ],
    Category.bug_report: [
        "bug", "defect", "reproduce", "steps to reproduce", "expected behavior",
        "actual behavior", "incorrect", "wrong result", "regression", "version",
        "workaround", "confirmed bug", "it used to work", "used to work",
        "recently broke", "after update", "since update",
    ],
}

_PRIORITY_KEYWORDS: Dict[str, List[str]] = {
    Priority.urgent: [
        "urgent", "critical", "emergency", "production down", "outage",
        "completely broken", "cannot work", "can't work", "blocking all",
        "blocked", "asap", "immediately", "right now", "data loss",
        "security", "breach", "hacked", "compromised",
    ],
    Priority.high: [
        "high priority", "important", "major", "significant", "need this soon",
        "affecting many", "multiple users", "team is blocked", "deadline",
        "clients affected", "revenue impact", "workaround needed", "escalate",
    ],
    Priority.medium: [
        "question", "how to", "wondering", "should", "when", "moderate",
        "normal", "medium priority", "regular",
    ],
    Priority.low: [
        "suggestion", "nice to have", "cosmetic", "minor", "small",
        "whenever", "when you get a chance", "no rush", "low priority",
        "sometime", "eventually", "not urgent", "trivial",
    ],
}


# ── Scoring helpers ────────────────────────────────────────────────────────────


def _score_text(text: str, keyword_map: Dict[str, List[str]]) -> Dict[str, int]:
    """
    Count keyword hits for each label in the keyword map.

    Each keyword is counted at most once per label even if it appears
    multiple times in the text — we care about coverage, not repetition.
    """
    text_lower = text.lower()
    return {
        label: sum(1 for kw in keywords if kw in text_lower)
        for label, keywords in keyword_map.items()
    }


def _pick_best(
    scores: Dict[str, int],
    fallback: str,
) -> Tuple[str, float]:
    """
    Choose the highest-scoring label and compute a confidence score.

    Confidence is the dominance ratio: best_score / total_hits.
    Special cases:
      - All scores zero        → return fallback at 0.5 (no signal)
      - Top two tied           → return fallback at 0.3 (ambiguous signal)
      - Best dominates clearly → return best label with confidence ≥ 0.5

    Returns: (label, confidence) where confidence ∈ [0.0, 1.0]
    """
    total = sum(scores.values())
    if total == 0:
        return fallback, 0.5

    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_label, best_score = sorted_items[0]
    runner_score = sorted_items[1][1] if len(sorted_items) > 1 else 0

    # If the top two labels are tied, the classification is ambiguous.
    if best_score == runner_score:
        return fallback, 0.3

    confidence = round(best_score / total, 2)
    return best_label, confidence


def _collect_matched_keywords(
    text: str,
    category_map: Dict[str, List[str]],
    priority_map: Dict[str, List[str]],
) -> List[str]:
    """
    Return a sorted, deduplicated list of every keyword found in the text.

    Searches both category and priority keyword pools so the caller gets
    the full picture of what the classifier detected.
    """
    text_lower = text.lower()
    found = set()

    for keywords in category_map.values():
        for kw in keywords:
            if kw in text_lower:
                found.add(kw)

    for keywords in priority_map.values():
        for kw in keywords:
            if kw in text_lower:
                found.add(kw)

    return sorted(found)


# ── Public API ─────────────────────────────────────────────────────────────────


def classify(subject: str, description: str) -> ClassificationResult:
    """
    Classify a ticket by its subject and description.

    Combines subject and description into a single search text, then runs
    keyword scoring for both Category and Priority independently.

    Returns a ClassificationResult with:
      - The best-matching category and its confidence score
      - The best-matching priority and its confidence score
      - All keywords that were found in the text
      - The UTC timestamp of when classification ran

    This function is pure (no side effects, no storage calls) — callers
    are responsible for persisting the result and updating the ticket.
    """
    text = f"{subject} {description}"

    # Score and pick best category
    category_scores = _score_text(text, _CATEGORY_KEYWORDS)
    best_category, category_confidence = _pick_best(
        category_scores, fallback=Category.other
    )

    # Score and pick best priority
    priority_scores = _score_text(text, _PRIORITY_KEYWORDS)
    best_priority, priority_confidence = _pick_best(
        priority_scores, fallback=Priority.medium
    )

    # Collect all matched keywords for transparency
    matched = _collect_matched_keywords(text, _CATEGORY_KEYWORDS, _PRIORITY_KEYWORDS)

    return ClassificationResult(
        category=Category(best_category),
        category_confidence=category_confidence,
        priority=Priority(best_priority),
        priority_confidence=priority_confidence,
        matched_keywords=matched,
        classified_at=datetime.now(timezone.utc),
    )
