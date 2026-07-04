# Unit Test Report — SecureVault

## Summary

This pass covers **Task 3** of `fix-summary.md`: the security remediation in
`src/crypto.py` (removal of the hardcoded fallback key, and stripping
plaintext/ciphertext from error logs). Tasks 1 and 2 (`src/vault.py` bug
fixes) were already fully covered by the existing `tests/test_vault.py` suite
per `fix-summary.md`, so no changes were made there.

- New file: `tests/test_crypto.py`
- **Tests added:** 6
- **Test run result:** 25 passed, 0 failed (19 pre-existing in `test_vault.py` + 6 new in `test_crypto.py`)

## Tests Added

All in `tests/test_crypto.py`, targeting `src/crypto.py` as changed in `fix-summary.md` Task 3.

1. **`test_get_key_raises_when_vault_key_unset`** — the fixed behavior:
   `get_key()` must raise `ValueError` mentioning `VAULT_KEY` when the env var
   is absent, instead of silently returning the removed hardcoded fallback key.
   Targets: `src/crypto.py:9-18` (`get_key`).
   FIRST: fast (no I/O), independent (autouse fixture unsets `VAULT_KEY` per
   test), repeatable (no ambient env dependence), self-validating
   (`pytest.raises` + message match), timely (the exact previously-vulnerable
   path).

2. **`test_get_key_returns_env_value_when_set`** — boundary/happy-path
   companion to test 1: when `VAULT_KEY` *is* set, `get_key()` must return its
   encoded value.
   Targets: `src/crypto.py:9-18`.
   FIRST: fast, independent (`monkeypatch.setenv` scoped to the test), repeatable,
   self-validating (`==` on exact bytes), timely (adjacent boundary to the
   raise case).

3. **`test_no_hardcoded_fallback_key_defined`** — regression guard: asserts
   `crypto._FALLBACK_KEY` no longer exists as a module attribute, so the
   removed static key can't silently reappear.
   Targets: `src/crypto.py:1-18` (removal of `_FALLBACK_KEY`).
   FIRST: fast, independent, repeatable, self-validating (`hasattr` assertion),
   timely (directly verifies the security fix's core change).

4. **`test_encrypt_decrypt_round_trip`** — happy-path sanity check that
   `encrypt`/`decrypt` still work correctly after `get_key()` was changed
   (encrypted value differs from plaintext; decrypting recovers the original).
   Targets: `src/crypto.py:21-42` (`encrypt`, `decrypt`).
   FIRST: fast, independent (fresh key via `monkeypatch.setenv`), repeatable,
   self-validating, timely (confirms the fix didn't break existing behavior).

5. **`test_encrypt_error_log_excludes_plaintext`** — the actual bug scenario:
   forces `encrypt()` to fail (invalid Fernet key format) and asserts the raw
   plaintext password never appears in `vault_debug.log`, only the exception
   type.
   Targets: `src/crypto.py:21-30` (`encrypt` error-logging branch).
   FIRST: fast (single in-process call, no subprocess), independent (isolated
   `tmp_path` cwd via existing chdir pattern), repeatable, self-validating
   (`not in` on log contents plus a positive check for the sanitized log
   line), timely (exact previously-broken logging path).

6. **`test_decrypt_error_log_excludes_ciphertext`** — the actual bug scenario
   for `decrypt()`: forces an `InvalidToken` on decryption and asserts the raw
   ciphertext value never appears in `vault_debug.log`.
   Targets: `src/crypto.py:33-42` (`decrypt` error-logging branch).
   FIRST: fast, independent, repeatable, self-validating (`not in` on log
   contents plus a positive check for the sanitized log line), timely (exact
   previously-broken logging path).

## Test Run Results

Command:

```bash
export VAULT_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
python3 -m pytest tests/ -v
```

Result: **25 passed** in 4.70s (0 failed, 0 errors).

- `tests/test_crypto.py` — 6/6 passed
- `tests/test_vault.py` — 19/19 passed (pre-existing, unaffected by this change)

## Coverage Notes

- **`src/vault.py` (`cmd_list`, `cmd_update`)** — intentionally not touched in
  this pass. `fix-summary.md` states both bugs were already fixed in the
  codebase and are already covered by `test_list_search_with_no_match_prints_not_found_message`
  and `test_update_preserves_service_username_and_created_at` in
  `tests/test_vault.py`. Re-adding coverage would duplicate existing tests and
  is out of scope for a change-scoped pass.
- **`DEBUG_LOG` module-level path handling** — not separately tested; it is
  unchanged plumbing (`Path("vault_debug.log")`), not part of the Task 3 diff.
- **CLI-level integration of the crypto fix** (e.g. `vault.py add` failing
  fast without `VAULT_KEY`) is already implicitly exercised by
  `tests/test_vault.py`'s `isolated_env` fixture always setting `VAULT_KEY`
  before any CLI call; adding a CLI-level "missing key" test was considered
  but skipped since it would duplicate `test_get_key_raises_when_vault_key_unset`
  at a slower (subprocess) granularity without covering new logic.

## References

**Tests added:**
- `tests/test_crypto.py:37-40` — `test_get_key_raises_when_vault_key_unset`
- `tests/test_crypto.py:43-47` — `test_get_key_returns_env_value_when_set`
- `tests/test_crypto.py:50-53` — `test_no_hardcoded_fallback_key_defined`
- `tests/test_crypto.py:60-65` — `test_encrypt_decrypt_round_trip`
- `tests/test_crypto.py:72-86` — `test_encrypt_error_log_excludes_plaintext`
- `tests/test_crypto.py:93-107` — `test_decrypt_error_log_excludes_ciphertext`

**Source locations covered:**
- `src/crypto.py:9-18` (`get_key`, fallback-key removal)
- `src/crypto.py:1-18` (removal of `_FALLBACK_KEY` module attribute)
- `src/crypto.py:21-30` (`encrypt`, sanitized error logging)
- `src/crypto.py:33-42` (`decrypt`, sanitized error logging)
