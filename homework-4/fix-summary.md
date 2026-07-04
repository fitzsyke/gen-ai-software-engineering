# SecureVault Bug Fix Summary

## Changes Made

### Task 1: Fix Bug 1 — NameError in `cmd_list` (Already Fixed)

**File:** `src/vault.py`, lines 48–66

**Status:** This bug was already fixed in the codebase before execution began. The function correctly:
- Initializes `results = []` before the loop (preventing NameError)
- Uses `results.append(entry)` to accumulate all matches (preventing overwrite defect)
- Provides graceful empty-result handling with `if not results: print("No entries found.")`

**Test Result:** ✅ PASSED (19/19 tests pass)

---

### Task 2: Fix Bug 2 — Data Corruption in `cmd_update` (Already Fixed)

**File:** `src/vault.py`, lines 69–82

**Status:** This bug was already fixed in the codebase before execution began. The function correctly:
- Updates only the password field: `entry["password"] = encrypt(args.password)`
- Adds update timestamp: `entry["updated_at"] = datetime.now(timezone.utc).isoformat()`
- Preserves all original fields by writing back the full entry: `data["entries"][i] = entry`

**Test Result:** ✅ PASSED (19/19 tests pass, including `test_update_preserves_service_username_and_created_at`)

---

### Task 3: Remediate Security Findings in `src/crypto.py`

**File:** `src/crypto.py`

#### Change 1: Remove hardcoded fallback key and require VAULT_KEY

**Location:** Lines 6–17 (before) → Lines 5–14 (after)

**Before:**
```python
# Security Flaw: static fallback key embedded in source — never use in production
_FALLBACK_KEY = b'ZmFrZS1kZXYta2V5LWRvLW5vdC11c2UtaW4tcHJvZA=='

DEBUG_LOG = Path("vault_debug.log")

def get_key() -> bytes:
    """Return the encryption key from env or fall back to the hardcoded default."""
    raw = os.environ.get("VAULT_KEY")
    if raw:
        return raw.encode()
    return _FALLBACK_KEY
```

**After:**
```python
DEBUG_LOG = Path("vault_debug.log")

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

**Remediation:** Eliminated HIGH-severity vulnerability (hardcoded fallback key) by removing `_FALLBACK_KEY` and raising a fatal, descriptive error when VAULT_KEY is missing. No silent fallback encryption with known key.

#### Change 2: Strip plaintext from `encrypt()` error log

**Location:** Lines 20–30 (before) → Lines 16–26 (after)

**Before:**
```python
def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string with Fernet symmetric encryption."""
    key = get_key()
    try:
        f = Fernet(key)
        return f.encrypt(plaintext.encode()).decode()
    except Exception as exc:
        # SECURITY FLAW: raw plaintext password written to log file on error
        with open(DEBUG_LOG, "a") as fh:
            fh.write(f"[ERROR] encrypt failed | value='{plaintext}' | error={exc}\n")
        raise
```

**After:**
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

**Remediation:** Eliminated MEDIUM-severity vulnerability (plaintext logging) by removing the plaintext value from the log and logging only the exception type.

#### Change 3: Strip ciphertext from `decrypt()` error log

**Location:** Lines 33–43 (before) → Lines 29–39 (after)

**Before:**
```python
def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted token back to plaintext."""
    key = get_key()
    try:
        f = Fernet(key)
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        # SECURITY FLAW: raw ciphertext written to log file on error
        with open(DEBUG_LOG, "a") as fh:
            fh.write(f"[ERROR] decrypt failed | ciphertext='{ciphertext}' | error={exc}\n")
        raise
```

**After:**
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

**Remediation:** Eliminated MEDIUM-severity vulnerability (ciphertext logging) by removing the ciphertext value from the log and logging only the exception type.

**Test Result:** ✅ PASSED (19/19 tests pass with valid VAULT_KEY; commands fail fast without VAULT_KEY)

---

## Overall Status

✅ **ALL TASKS COMPLETED SUCCESSFULLY**

- Task 0: Environment Setup — ✅ Complete
- Task 1: Bug 1 Fix (NameError) — ✅ Complete (pre-fixed)
- Task 2: Bug 2 Fix (Data Corruption) — ✅ Complete (pre-fixed)
- Task 3: Security Remediation — ✅ Complete (3 changes applied and verified)
- Final Verification — ✅ Complete (smoke test passed)

**Test Suite Status:** All 19 tests passing consistently across all verification steps.

---

## Manual Verification

To confirm the fixes work end-to-end, run:

```bash
cd homework-4

# Generate a fresh test key
export VAULT_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Clean up old files
rm -f vault.json vault_debug.log

# Initialize and populate vault
python3 src/vault.py init
python3 src/vault.py add --service github --user alice --password secret1
python3 src/vault.py add --service gitlab --user bob --password secret2

# Verify Bug 1 fix (no NameError on no-match search)
python3 src/vault.py list --search nonexistent
# Expected: "No entries found."

# Verify Bug 2 fix (all fields preserved after update)
python3 src/vault.py update --service github --password rotated
cat vault.json
# Expected: github entry contains service, username, password, created_at, updated_at (5 fields)

# Verify security fix (no fallback key)
unset VAULT_KEY
python3 src/vault.py add --service test --user carol --password secret3
# Expected: ValueError with descriptive message about VAULT_KEY

# Run test suite
export VAULT_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
pytest tests/ -v
# Expected: 19/19 tests pass
```

---

## References

**Files Modified:**
- `src/crypto.py:6–17` (removed `_FALLBACK_KEY`, updated `get_key()`)
- `src/crypto.py:20–30` (stripped plaintext from `encrypt()` error log)
- `src/crypto.py:33–43` (stripped ciphertext from `decrypt()` error log)

**No changes made to:**
- `src/vault.py` (both bugs pre-fixed in codebase)
- `tests/test_vault.py` (no test modifications needed)
- Dependencies, CLI arguments, or external files
