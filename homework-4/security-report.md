# Security Review Report — SecureVault Bug Fixes

**Reviewer:** Security Vulnerabilities Verifier (audit only — no code modified)
**Date:** 2026-07-02
**Scope:** Files listed as changed in `fix-summary.md`, plus code the changed lines call
directly into (for data-flow context).

> **Note on a prior report:** An earlier `security-report.md` existed that described a
> hardcoded fallback key and plaintext-password logging as *unremediated*. Reading the
> **live** source shows those flaws have since been fixed in `src/crypto.py`. This report
> reflects the current on-disk code, not the earlier snapshot, and supersedes it.

---

## Summary

Per `fix-summary.md`, the only source file changed by the Bug Fixer is `src/crypto.py`
(three security remediations). `src/vault.py` is reported as **not changed** (both bugs were
pre-fixed in the codebase); it was read only to trace how the changed `crypto.py` functions
are called.

| Item | Detail |
|---|---|
| Files in change scope | `src/crypto.py` (`get_key`, `encrypt`, `decrypt`) |
| Call-site context read | `src/vault.py` (`cmd_add`, `cmd_update` → `encrypt`) |

**Severity counts (confirmed findings):**

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 1 |
| INFO | 1 |

**Bottom line:** All three remediations claimed in `fix-summary.md` are present and correct
in the live code: the hardcoded fallback key is gone and a missing `VAULT_KEY` now raises;
the `encrypt`/`decrypt` error logs no longer contain plaintext or ciphertext. No new
vulnerability was introduced by the changes. Two minor defense-in-depth items are noted;
neither is exploitable.

---

## Findings

### 1. LOW — Debug log written to a relative, default-permission path in the working directory

- **Location:** `src/crypto.py:6` (`DEBUG_LOG = Path("vault_debug.log")`), written at
  `src/crypto.py:28` and `src/crypto.py:40`.
- **Vulnerable code:**
  ```python
  DEBUG_LOG = Path("vault_debug.log")
  ...
  with open(DEBUG_LOG, "a") as fh:
      fh.write(f"[ERROR] encrypt failed | error={type(exc).__name__}\n")
  ```
- **Data flow / exploit scenario:** The log path is relative to the current working directory
  and the file is created with the process's default umask. On a shared host another local
  user could read it, or pre-create/symlink the path. After the fix the file contains only
  exception **type names** (e.g. `InvalidToken`) — no plaintext, ciphertext, or key — so the
  confidentiality impact is minimal. This is a file-placement/hygiene gap, not secret exposure.
- **Remediation:** Write diagnostics to an application-controlled path, create the file with
  restrictive permissions (`0o600`), and/or route through the `logging` module instead of a
  bare relative append. Optional; not introduced by the change.

### 2. INFO — Encryption key sourced from an environment variable

- **Location:** `src/crypto.py:9–18` (`get_key`).
- **Detail:** The remediation correctly removed the hardcoded `_FALLBACK_KEY` and now raises a
  fatal `ValueError` when `VAULT_KEY` is unset — this closes the previous HIGH-severity
  hardcoded-secret issue. Sourcing the key from an environment variable is a standard,
  acceptable pattern; noted only for awareness that env vars can be exposed via
  `/proc/<pid>/environ`, process listings on some platforms, or child-process inheritance.
  No action required for this codebase's threat model.

---

## Considered and Ruled Out

- **Plaintext password logging in `encrypt()` (`src/crypto.py:27–30`):** The pre-fix code
  logged `value='{plaintext}'`. The live code logs only `error={type(exc).__name__}`. Traced
  the f-string: no plaintext, key, or entry data reaches the log. **Fixed — not a finding.**
- **Ciphertext logging in `decrypt()` (`src/crypto.py:39–42`):** Pre-fix code logged
  `ciphertext='{ciphertext}'`; live code logs only the exception type name. **Fixed — not a
  finding.**
- **Hardcoded fallback key (`get_key`, `src/crypto.py:9–18`):** `_FALLBACK_KEY` is fully
  removed; there is no silent fallback, and a missing `VAULT_KEY` raises `ValueError`. **Fixed
  — not a finding.**
- **Broad `except Exception` in `encrypt()` (`src/crypto.py:23–30`):** `get_key()` is called
  at line 23, *outside* the `try`, so a missing-key `ValueError` propagates uncaught and is
  never logged. The `except` only wraps Fernet operations and re-`raise`s after logging. No
  secret leaks, no error suppression. **Safe.**
- **Secrets in propagated exceptions:** Both handlers `raise` after logging. Fernet's
  `InvalidToken`/exception messages do not embed the key or plaintext, so the resulting stack
  trace exposes no secret. **Safe.**
- **Injection at call sites (`src/vault.py`):** `encrypt`/`decrypt` values pass straight to
  Fernet; there is no SQL/shell/`eval`/`exec`/template sink anywhere in the path. CLI args are
  JSON-serialized (`json.dump`), not concatenated into a query/command. **Safe.**
- **`==` comparison on request-controlled data (`src/vault.py:74`):**
  `entry["service"] == args.service` compares a non-secret service *name*, not a token or
  signature — no meaningful timing side-channel. **Not applicable.**
- **Deserialization (`src/vault.py:17`):** Vault storage uses `json.load` (safe deserializer),
  not `pickle`/unsafe `yaml`; the file is the user's own local vault. **Safe.**

---

## References — everything reviewed

- `fix-summary.md` — full document (scope definition).
- `src/crypto.py:1–43` — all three changes:
  - `src/crypto.py:9–18` — `get_key` (hardcoded-key removal / fatal-on-missing) — verified fixed.
  - `src/crypto.py:21–30` — `encrypt` (plaintext stripped from error log) — verified fixed; finding #1 (log path).
  - `src/crypto.py:33–42` — `decrypt` (ciphertext stripped from error log) — verified fixed.
- `src/vault.py:34–45` — `cmd_add` (call site of `encrypt`) — context only.
- `src/vault.py:69–82` — `cmd_update` (call site of `encrypt`) — context only.
- `src/vault.py:12–23` — `load_vault` / `save_vault` (JSON storage; deserialization check) — context only.
