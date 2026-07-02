---
name: research-quality-measurement
description: Rubric for scoring the quality of a bug-research document (e.g. codebase-research.md) after fact-checking it against live source. Used by the Bug Research Verifier agent to assign a Research Quality level and back it with reasoning.
---

# Research Quality Measurement

A rubric for turning a fact-check of a research document into a single, defensible quality
label. Apply this **after** every file:line reference and code snippet in the research
document has been checked against the live source files — never assign a level from
skimming.

## Dimensions

Score each claim in the research document against these four dimensions:

| Dimension | Question |
|---|---|
| **Location Accuracy** | Does the cited `file:line` actually contain the described code? |
| **Snippet Fidelity** | Does the quoted code snippet match the source verbatim (ignoring incidental whitespace)? |
| **Root Cause Correctness** | Is the stated defect/root cause technically accurate given the real code? |
| **Completeness** | Does the document cover all instances of the issue, or does it miss related occurrences (e.g., the same flaw repeated in a sibling function)? |

## Discrepancy Severity

Classify every mismatch found while checking the dimensions above:

| Severity | Definition | Example |
|---|---|---|
| **Blocking** | The claim is factually wrong in a way that would misdirect a fix (wrong root cause, wrong file, code doesn't exist at all). | Research says the bug is at line 40; the real defect is at line 58 in a different function. |
| **Major** | Location or snippet is off enough to slow down or confuse implementation, but the root cause is still correct. | Line number off by more than ~5 lines, or snippet omits a materially relevant line. |
| **Minor** | Cosmetic drift that doesn't affect implementation (off-by-1-2 line number after reformatting, trivial whitespace diff). | Snippet quoted matches except for a trailing comment. |

## Quality Levels

Compute the level from the counts of Blocking / Major / Minor discrepancies across all
verified claims:

| Level | Criteria | Meaning for downstream agents |
|---|---|---|
| **VERIFIED** | 0 Blocking, 0 Major, ≤1 Minor discrepancy across all claims. | Bug Planner may use the document as-is. |
| **VERIFIED WITH MINOR DISCREPANCIES** | 0 Blocking, 0 Major, 2+ Minor discrepancies. | Safe to use; downstream agent should re-check exact line numbers before editing. |
| **VERIFIED WITH MAJOR DISCREPANCIES** | 0 Blocking, 1+ Major discrepancies. | Usable only after downstream agent independently confirms the affected claims. |
| **FAILED VERIFICATION** | 1+ Blocking discrepancies. | Document must NOT be handed to the Bug Planner until corrected; affected claims must be re-researched. |

A single Blocking discrepancy anywhere in the document is enough to fail verification
overall, even if every other claim is perfect — a misdirected fix is worse than a slow one.

## Reasoning requirement

The verifier must not just state the level — it must justify it by listing, per dimension,
how many claims were checked, how many passed, and which discrepancies (with severity) drove
the final level. A level with no supporting count-based reasoning is not acceptable output.
