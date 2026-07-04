# Verified Research: SecureVault (SECUREVAULT-001)

**Prepared by:** Bug Research Verifier Agent
**Source document:** `research/codebase-research.md`
**Verified against:** `src/vault.py`, `src/crypto.py`, `tests/test_vault.py` (live source tree)
**Quality rubric:** `skills/research-quality-measurement.md`

> **State note (read first):** This report supersedes an earlier `verified-research.md` that
> was written against a still-buggy revision of the source. Since that earlier pass the live
> tree has changed: **Bug 1 and Bug 2 are already fixed in the current source**, and
> `tests/test_vault.py` now contains passing regression tests for both. The source files are
> untracked in git (`?? ./`), so there is no hidden working-tree diff and only one copy of each
> file exists — the verification below reflects the tree exactly as it is on disk now.

---

## Verification Summary

**Result: FAILED VERIFICATION — Research Quality level: FAILED VERIFICATION.**

The document is **NOT safe** to hand to the Bug Planner as-is. Two of its three issues (Bug 1 —
NameError in `cmd_list`; Bug 2 — dictionary overwrite in `cmd_update`) describe **code that does
not exist in the live source tree.** The snippets attributed to those functions are of a buggy
version that has since been fixed. In the current `src/vault.py`:

- `cmd_list` (lines 48–66) already initializes `results = []` (53), uses `results.append(entry)`
  (56), and guards the empty case with `if not results: print("No entries found.")` (58–60).
- `cmd_update` (lines 69–82) already performs a targeted in-place field update
  (`entry["password"] = ...`, `entry["updated_at"] = ...`) that preserves `username` and
  `created_at`.

The document's own "Fix Required" snippets for both bugs match the *current* source almost
verbatim — i.e. the fixes it proposes are already implemented. `tests/test_vault.py` confirms
this independently with regression tests explicitly labelled "fixed for Bug 1" (line 178) and
"fixed for Bug 2" (line 219). Directing a fixer at these two "bugs" would waste effort or cause a
regression. Both are **Blocking** discrepancies, and a single Blocking discrepancy fails the
document overall per the rubric.

The **Security Flaw** section is different: the hardcoded `_FALLBACK_KEY` and the
plaintext/ciphertext exception logging **are genuinely present** in the live `src/crypto.py`, and
their root causes are described correctly. Only their line numbers drift (key: 5→7; encrypt log:
24→29). That section is salvageable; the two bug sections must be re-researched against the
current source.

---

## Verified Claims

| # | Claim (file:line) | What was claimed | What was found in live source | Verdict |
|---|---|---|---|---|
| 1 | `src/vault.py` ~48–60 | `cmd_list()` located here | `cmd_list()` spans lines 48–66 | Match (function location) |
| 2 | `src/vault.py` 52–57 (Bug 1 snippet) | `results = [entry]` in loop, no init; bare `for r in results` | Live 52–63: `results = []` (53), `results.append(entry)` (56), `if not results:` guard (58–60) | **Discrepancy (Blocking)** |
| 3 | `src/vault.py` 58 | NameError crash; `results` never initialized | Line 58 is `if not results:` — the empty-search guard; no NameError possible | **Discrepancy (Blocking)** |
| 4 | `src/vault.py` ~63–78 | `cmd_update()` located here | `cmd_update()` spans lines 69–82 | Match (function location, ~6 lines low) |
| 5 | `src/vault.py` 67–73 (Bug 2 snippet) | `data["entries"][i] = {"service":…, "password":…}` full-dict replacement | Live 73–77: `entry["password"] = encrypt(...)`, `entry["updated_at"] = ...`, `data["entries"][i] = entry` | **Discrepancy (Blocking)** |
| 6 | `src/vault.py` 71 | Full replacement drops `username`/`created_at` | Line 71 is `entries = data["entries"]`; update is in-place and preserves all keys | **Discrepancy (Blocking)** |
| 7 | `src/crypto.py` 5 | `_FALLBACK_KEY = b'ZmFrZS…'` | Value correct, but located at **line 7**; line 5 is blank | Discrepancy (Minor — line off by 2) |
| 8 | `src/crypto.py` 12–17 (get_key) | Returns fallback when `VAULT_KEY` absent | Confirmed: `get_key()` returns `_FALLBACK_KEY` when env var unset | Match |
| 9 | `src/crypto.py` 24 | `fh.write(f"[ERROR] encrypt failed | value='{plaintext}' | …")` | Snippet verbatim correct but at **line 29**; line 24 is `f = Fernet(key)` | Discrepancy (Major — line off by 5) |
| 10 | `src/crypto.py` decrypt() | Same pattern logs raw `ciphertext` | Confirmed at lines 41–42 | Match |
| 11 | Inventory: `tests/test_vault.py` ~60 lines, "init + add coverage only" | 60-line file, only init/add | File is **263 lines**; covers init, add, list (incl. Bug 1 no-match), update (incl. Bug 2 preservation) | Discrepancy (Major) |
| 12 | Inventory: `src/vault.py` ~118, `src/crypto.py` ~43 | Approximate line counts | 122 and 43 respectively | Match (approximate) |

**Totals:** 12 claim-groups checked · 5 Match · 7 Discrepancy (2 Blocking, 2 Major, 3 Minor incl. key-line/update-line/cmd_update-range slippage rolled into the blocking snippet items).

---

## Discrepancies Found

### Blocking

**B1 — Bug 1 (`cmd_list`) describes code that does not exist in the live source.**
- **Claim:** Lines 52–57 assign `results = [entry]` inside the loop with no initialization and
  no empty guard, causing `NameError: name 'results' is not defined` at line 58 on an unmatched
  search.
- **Actual code (`src/vault.py` 52–63):**
  ```python
      if args.search:
          results = []
          for entry in entries:
              if args.search.lower() in entry["service"].lower():
                  results.append(entry)

          if not results:
              print("No entries found.")
              return

          for r in results:
              print(f"  Service: {r['service']}, User: {r['username']}")
  ```
- **Why it matters:** The described defect is already fixed. `results` is initialized (53),
  entries are appended (56), and the empty case is handled (58–60). Line 58 is the guard, not a
  crash site. `tests/test_vault.py:178`
  (`test_list_search_with_no_match_prints_not_found_message`) is a passing regression test for
  exactly this scenario. The document's own "Fix Required" is what the code already does.

**B2 — Bug 2 (`cmd_update`) describes code that does not exist in the live source.**
- **Claim:** Line 71 replaces the whole entry with `{"service":…, "password":…}`, discarding
  `username` and `created_at`.
- **Actual code (`src/vault.py` 73–77):**
  ```python
      for i, entry in enumerate(entries):
          if entry["service"] == args.service:
              entry["password"] = encrypt(args.password)
              entry["updated_at"] = datetime.now(timezone.utc).isoformat()
              data["entries"][i] = entry
  ```
- **Why it matters:** The live update is an in-place field write that preserves every original
  key — it *is* the fix the document claims still needs doing. Line 71 is actually
  `entries = data["entries"]`. `tests/test_vault.py:219`
  (`test_update_preserves_service_username_and_created_at`) is a passing regression test proving
  the fields are preserved. This "bug" is not actionable.

### Major

**M1 — Security snippet for `encrypt()` cited at wrong line (claimed 24, actual 29).** The
`fh.write(... value='{plaintext}' ...)` line is at **line 29**; line 24 is `f = Fernet(key)`.
Snippet text is verbatim correct and the root cause (raw password written to `vault_debug.log`
on failure) is real and accurate. Off by 5 and landing on unrelated code — enough to slow an
implementer, though the exact snippet aids recovery. (Borderline Major/Minor; classified Major
because line 24 references a materially different statement.)

**M2 — Test-file inventory is materially wrong.** Claimed "~60 lines" with "init + add coverage
only"; the file is **263 lines** and covers init, add, list (including the Bug 1 no-match path)
and update (including Bug 2 field preservation). This understates coverage ~4x and, critically,
hides that Bug 1 and Bug 2 already have passing regression tests — the strongest single signal
that both are already resolved.

### Minor

**m1 — Hardcoded key cited at wrong line (claimed 5, actual 7).** `_FALLBACK_KEY` is at line
**7**; line 5 is blank and line 6 is the preceding comment. Value quoted is exact and the root
cause (hardcoded fallback usable to decrypt all vault data; `get_key()` fallback path at 12–17)
is accurate. Cosmetic, off by 2.

*(No decrypt-side discrepancy: the document's claim that `decrypt()` repeats the plaintext-logging
pattern is correct — confirmed at `src/crypto.py:41–42`.)*

---

## Research Quality Assessment

**Level: FAILED VERIFICATION** (per `skills/research-quality-measurement.md`: 1+ Blocking).

A single Blocking discrepancy fails the document overall regardless of other claims; here there
are **two**.

Count-based reasoning per dimension (12 discrete claim-groups checked):

| Dimension | Claims checked | Passed | Failed (severity) |
|---|---|---|---|
| **Location Accuracy** | 6 (claims 1,3,4,6,7,9) | 2 (function-level locates for `cmd_list` & `cmd_update`) | 4 — line 58 not a crash (Blocking), line 71 not the update (Blocking), key 5→7 (Minor), log 24→29 (Major) |
| **Snippet Fidelity** | 4 (claims 2,5,7,9) | 2 (crypto key + encrypt-log verbatim) | 2 — Bug 1 snippet fabricated vs live (Blocking), Bug 2 snippet fabricated vs live (Blocking) |
| **Root Cause Correctness** | 4 (Bug 1, Bug 2, hardcoded key, plaintext log) | 2 (both security flaws) | 2 — Bug 1 non-existent (Blocking), Bug 2 non-existent (Blocking) |
| **Completeness** | 2 (decrypt sibling pattern; test inventory) | 1 (decrypt logging correctly flagged) | 1 — test inventory misrepresents scope, hiding existing Bug 1/Bug 2 regression tests (Major) |

**Discrepancy tally:** 2 Blocking, 2 Major, 1 Minor.

**Driver of the level:** The two Blocking discrepancies (Bug 1 and Bug 2 describe code absent
from the live tree; the documented defects are already fixed and covered by passing regression
tests) force **FAILED VERIFICATION** on their own — this is what keeps the document out of every
"VERIFIED …" tier. The Major and Minor items are secondary. Before this document is usable, the
Bug 1 and Bug 2 sections must be re-researched against the current source; the security section
needs only line-number corrections (key 5→7; encrypt log 24→29) and is otherwise sound.

---

## References

Every location below was personally opened and confirmed during this verification pass:

- `src/vault.py:48-66` — `cmd_list()`; confirmed `results = []` init (53), `.append()` (56), empty guard (58–60)
- `src/vault.py:58` — actual content `if not results:` (document mislabels this as the NameError crash site)
- `src/vault.py:69-82` — `cmd_update()`; confirmed in-place field update (75–77) preserving all keys
- `src/vault.py:71` — actual content `entries = data["entries"]` (document claims full-dict replacement here)
- `src/vault.py:41` — `created_at` set in `cmd_add` (the field Bug 2 claimed was dropped)
- `src/crypto.py:7` — `_FALLBACK_KEY = b'ZmFrZS1kZXYta2V5LWRvLW5vdC11c2UtaW4tcHJvZA=='` (document claims line 5)
- `src/crypto.py:12-17` — `get_key()` returns `_FALLBACK_KEY` when `VAULT_KEY` unset
- `src/crypto.py:24` — actual content `f = Fernet(key)` (document claims the log write is here)
- `src/crypto.py:29` — `fh.write(f"[ERROR] encrypt failed | value='{plaintext}' | error={exc}\n")` (real log-write line)
- `src/crypto.py:41-42` — `decrypt()` logging of raw `ciphertext` (confirms repeated pattern)
- `tests/test_vault.py:178-188` — `test_list_search_with_no_match_prints_not_found_message` (Bug 1 regression)
- `tests/test_vault.py:219-231` — `test_update_preserves_service_username_and_created_at` (Bug 2 regression)
- Line counts confirmed via `wc -l`: `vault.py` 122, `crypto.py` 43, `test_vault.py` 263
- Git state confirmed: source files untracked (`?? ./`), single copy of each file, no working-tree diff
