# SecureVault Bug Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Bug 1 (NameError crash in `cmd_list`) and Bug 2 (silent data corruption in
`cmd_update`) in `src/vault.py`, and remediate the Security Verifier's HIGH/MEDIUM findings in
`src/crypto.py` (hardcoded fallback encryption key; plaintext secrets logged on error).

**Architecture:** Bugs 1 and 2 live in `src/vault.py` and require only localised edits within
their respective command handler functions. The security remediation lives in `src/crypto.py`
and is likewise a localised edit — remove the hardcoded fallback key and strip sensitive
values from the two exception-logging blocks. No new files, modules, or dependencies are
introduced in any of the three tasks.

**Tech Stack:** Python 3.9+, `cryptography` (Fernet), `pytest` for test verification.

## Global Constraints

- Do not add new CLI arguments, commands, or external dependencies.
- All existing tests in `tests/test_vault.py` must continue to pass after every fix.
- Run tests from the `homework-4/` directory: `pytest tests/ -v`.
- The `VAULT_KEY` environment variable must be set to a valid Fernet key when running tests
  locally (see Task 0). After Task 3, `VAULT_KEY` is **required** — there is no fallback key,
  so any command or test that omits it must fail fast with a clear error instead of silently
  encrypting with a known key.

---

## Task 0: Environment Setup

**Files:** none modified

- [ ] **Step 1: Install dependencies**

```bash
cd homework-4
pip install cryptography pytest
```

Expected: packages installed without errors.

- [ ] **Step 2: Generate a test key and confirm baseline tests pass**

```bash
export VAULT_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
pytest tests/ -v
```

Expected output (all passing):

```
tests/test_vault.py::test_init_creates_vault_file PASSED
tests/test_vault.py::test_init_is_idempotent PASSED
tests/test_vault.py::test_add_creates_entry PASSED
tests/test_vault.py::test_add_stores_password_encrypted PASSED
tests/test_vault.py::test_add_multiple_entries PASSED
tests/test_vault.py::test_list_all_entries PASSED
tests/test_vault.py::test_list_without_search_shows_all PASSED
```

If any test fails before you touch any code, stop and investigate before proceeding.

---

## Task 1: Fix Bug 1 — NameError in `cmd_list`

**Files:**
- Modify: `src/vault.py:48–60` (`cmd_list` function body)

**Problem:** `results` is only assigned inside `if args.search.lower() in entry["service"].lower():`. When no entry matches, `results` is never defined and `for r in results:` raises `NameError`. A secondary defect: `results = [entry]` overwrites on every match instead of accumulating — only the last match is ever shown.

### Steps

- [ ] **Step 1: Reproduce the crash**

```bash
cd homework-4
python src/vault.py init
python src/vault.py add --service github --user alice --password secret1
python src/vault.py list --search nonexistent
```

Expected (current broken behaviour):
```
NameError: name 'results' is not defined
```

- [ ] **Step 2: Replace the `cmd_list` function body**

Open `src/vault.py`. Find `cmd_list` starting at line 48. Replace the entire function with:

```python
def cmd_list(args) -> None:
    data = load_vault()
    entries = data["entries"]

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
    else:
        for entry in entries:
            print(f"  Service: {entry['service']}, User: {entry['username']}")
```

Key changes:
- `results = []` initialised before the loop (fixes NameError).
- `results.append(entry)` accumulates all matches (fixes overwrite defect).
- `if not results: print("No entries found.")` provides graceful empty-result handling.

- [ ] **Step 3: Verify the crash is resolved**

```bash
python src/vault.py list --search nonexistent
```

Expected: `No entries found.`

- [ ] **Step 4: Verify matching still works**

```bash
python src/vault.py list --search github
```

Expected: `  Service: github, User: alice`

- [ ] **Step 5: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all 7 tests pass.

---

## Task 2: Fix Bug 2 — Data Corruption in `cmd_update`

**Files:**
- Modify: `src/vault.py:63–78` (`cmd_update` function body)

**Problem:** `data["entries"][i] = {"service": ..., "password": ...}` replaces the full entry dict with a new two-key object, permanently discarding `username` and `created_at`.

### Steps

- [ ] **Step 1: Reproduce the data loss**

```bash
python src/vault.py update --service github --password newsecret
cat vault.json
```

Expected (current broken output): entry contains only `"service"` and `"password"` — `"username"` and `"created_at"` are gone.

- [ ] **Step 2: Replace the `cmd_update` function body**

Open `src/vault.py`. Find `cmd_update` starting at line 63. Replace the entire function with:

```python
def cmd_update(args) -> None:
    data = load_vault()
    entries = data["entries"]

    for i, entry in enumerate(entries):
        if entry["service"] == args.service:
            entry["password"] = encrypt(args.password)
            entry["updated_at"] = datetime.now(timezone.utc).isoformat()
            data["entries"][i] = entry
            save_vault(data)
            print(f"Password for '{args.service}' updated.")
            return

    print(f"Service '{args.service}' not found.")
```

Key changes:
- `entry["password"] = encrypt(args.password)` updates only the password field in-place.
- `entry["updated_at"] = ...` records when the update occurred without touching other fields.
- `data["entries"][i] = entry` writes back the full original entry with only the changed fields modified.

- [ ] **Step 3: Verify no data loss**

Re-run the full scenario from scratch:

```bash
python src/vault.py init
python src/vault.py add --service github --user alice --password secret1
python src/vault.py update --service github --password newsecret
cat vault.json
```

Expected `vault.json` content:

```json
{
  "entries": [
    {
      "service": "github",
      "username": "alice",
      "password": "<encrypted-token>",
      "created_at": "<original-timestamp>",
      "updated_at": "<update-timestamp>"
    }
  ]
}
```

Confirm `"username"` and `"created_at"` are still present.

- [ ] **Step 4: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all 7 tests pass.

---

## Task 3: Remediate Security Findings in `src/crypto.py`

**Files:**
- Modify: `src/crypto.py` (`get_key`, lines 12–17; `encrypt`, lines 20–30; `decrypt`, lines 33–43)

**Problem (from `security-report.md`):**
- **HIGH** — `get_key()` silently falls back to a hardcoded `_FALLBACK_KEY` when `VAULT_KEY` is
  unset, so anyone with repo access can decrypt every stored credential.
- **MEDIUM** — both `encrypt()` and `decrypt()` write the raw plaintext password / ciphertext
  into `vault_debug.log` on error, leaking secrets to an unrotated, unprotected file.

### Steps

- [ ] **Step 1: Reproduce the hardcoded-key fallback**

```bash
cd homework-4
unset VAULT_KEY
python src/vault.py init
python src/vault.py add --service test --user bob --password secret1
```

Expected (current insecure behaviour): commands succeed silently using `_FALLBACK_KEY` — no
error, no warning that a known, committed key is protecting the data.

- [ ] **Step 2: Replace `get_key()` in `src/crypto.py`**

Remove `_FALLBACK_KEY` entirely and raise a fatal, descriptive error when `VAULT_KEY` is
missing:

```python
def get_key() -> bytes:
    """Return the encryption key from the VAULT_KEY environment variable."""
    raw = os.environ.get("VAULT_KEY")
    if not raw:
        raise ValueError(
            "VAULT_KEY environment variable is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    return raw.encode()
```

Also delete the now-unused `_FALLBACK_KEY` line and its preceding comment near the top of the
file.

- [ ] **Step 3: Strip sensitive values from the `encrypt()` error log**

```python
def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string with Fernet symmetric encryption."""
    key = get_key()
    try:
        f = Fernet(key)
        return f.encrypt(plaintext.encode()).decode()
    except Exception as exc:
        with open(DEBUG_LOG, "a") as fh:
            fh.write(f"[ERROR] encrypt failed | error={type(exc).__name__}\n")
        raise
```

- [ ] **Step 4: Strip sensitive values from the `decrypt()` error log**

```python
def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted token back to plaintext."""
    key = get_key()
    try:
        f = Fernet(key)
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        with open(DEBUG_LOG, "a") as fh:
            fh.write(f"[ERROR] decrypt failed | error={type(exc).__name__}\n")
        raise
```

- [ ] **Step 5: Verify the fallback key is gone**

```bash
unset VAULT_KEY
python src/vault.py init
python src/vault.py add --service test --user bob --password secret1
```

Expected: command fails fast with `ValueError: VAULT_KEY environment variable is not set. ...`
— no silent fallback, no encryption performed with a known key.

- [ ] **Step 6: Verify no plaintext/ciphertext ever reaches the log**

```bash
export VAULT_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
rm -f vault_debug.log
python src/vault.py init
python src/vault.py add --service test --user bob --password "super-secret-value"
export VAULT_KEY="not-a-valid-fernet-key"   # force an encrypt() failure
python src/vault.py add --service test2 --user carol --password "another-secret" || true
grep -i "super-secret-value\|another-secret" vault_debug.log
```

Expected: the `grep` finds **no matches** — `vault_debug.log` contains only
`[ERROR] encrypt failed | error=<ExceptionType>` lines, never the raw secret.

- [ ] **Step 7: Run the full test suite**

```bash
export VAULT_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
pytest tests/ -v
```

Expected: all existing tests pass — none of them rely on the removed fallback key.

---

## Final Verification

After all three tasks are complete, run one final end-to-end smoke test:

```bash
export VAULT_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
rm -f vault.json vault_debug.log

python src/vault.py init
python src/vault.py add --service github --user alice --password secret1
python src/vault.py add --service gitlab --user bob --password secret2
python src/vault.py list                        # shows both entries
python src/vault.py list --search github        # shows github only
python src/vault.py list --search nonexistent   # prints "No entries found."
python src/vault.py update --service github --password rotated
cat vault.json                                  # github entry has all 5 fields

unset VAULT_KEY
python src/vault.py add --service test --user carol --password secret3
# Expected: fails with "VAULT_KEY environment variable is not set" — no silent fallback

export VAULT_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
pytest tests/ -v                                # all tests green
```
