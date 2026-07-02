# Codebase Research: SecureVault

**Prepared for:** Bug Research Verifier Agent  
**Purpose:** Maps each known issue in SECUREVAULT-001 to exact source locations for use by the Bug Fixer agent.

> **Note for Verifier Agent:** Audit every file path, line number, and code snippet in this document against the live source files. Report any discrepancies before this document is handed to the Bug Fixer.

---

## File Inventory

| File | Approx. Lines | Responsibility |
|---|---|---|
| `src/vault.py` | ~118 | CLI entrypoint; all four subcommand handlers |
| `src/crypto.py` | ~43 | Fernet encryption/decryption utilities |
| `tests/test_vault.py` | ~60 | Pytest baseline suite (init + add coverage only) |

---

## Bug 1 — NameError Crash in `cmd_list` (`src/vault.py`)

### Reported Location

`src/vault.py`, function `cmd_list()`, approximately lines 48–60.

### Analysis

The search branch iterates over entries and conditionally assigns `results`:

```python
# src/vault.py, lines 52–57
    if args.search:
        for entry in entries:
            if args.search.lower() in entry["service"].lower():
                results = [entry]
        for r in results:   # line 58 — NameError when no match found
            print(f"  Service: {r['service']}, User: {r['username']}")
```

**Defect:** The comment above marks the crash at **line 58**. The variable `results` is never initialized before the loop, so if no entry matches the search term, Python raises:

```
NameError: name 'results' is not defined
```

A secondary defect exists on the same assignment: `results = [entry]` overwrites itself on each iteration rather than appending, so only the final matching entry would be returned even when multiple entries match.

**Fix Required:** Initialize `results = []` before the loop, replace `results = [entry]` with `results.append(entry)`, and add a guard to print `"No entries found."` when `results` is empty after the loop.

---

## Bug 2 — Dictionary Overwrite in `cmd_update` (`src/vault.py`)

### Reported Location

`src/vault.py`, function `cmd_update()`, approximately lines 63–78.

### Analysis

```python
# src/vault.py, lines 67–73
    for i, entry in enumerate(entries):
        if entry["service"] == args.service:
            encrypted_password = encrypt(args.password)
            data["entries"][i] = {          # line 71 — full replacement, not merge
                "service": args.service,
                "password": encrypted_password,
            }
```

**Defect:** The assignment at **line 71** replaces the entire dictionary stored at `data["entries"][i]` with a new object containing only `"service"` and `"password"`. The original fields `"username"` and `"created_at"` are permanently discarded.

**Fix Required:** Replace the full-dict assignment with a targeted in-place field update:

```python
entry["password"] = encrypt(args.password)
entry["updated_at"] = datetime.now(timezone.utc).isoformat()
data["entries"][i] = entry
```

---

## Security Flaw — Hardcoded Key + Plaintext Logging (`src/crypto.py`)

### Reported Location 1: Hardcoded Fallback Key

`src/crypto.py`, **line 5**.

```python
# src/crypto.py, line 5
_FALLBACK_KEY = b'ZmFrZS1kZXYta2V5LWRvLW5vdC11c2UtaW4tcHJvZA=='
```

**Risk:** The encryption key is embedded directly in source code. Any actor with repository read access can use this key to decrypt all vault data. The `get_key()` function returns this value whenever `VAULT_KEY` is absent from the environment, which is the default for local installations.

### Reported Location 2: Unsafe Exception Logging in `encrypt()`

`src/crypto.py`, `encrypt()` function, **line 24**.

```python
# src/crypto.py, line 24
            fh.write(f"[ERROR] encrypt failed | value='{plaintext}' | error={exc}\n")
```

**Risk:** The raw `plaintext` argument (the user's actual password) is written to `vault_debug.log` on any encryption failure. This log file is never rotated or access-controlled.

The same pattern exists in `decrypt()`, which logs the raw `ciphertext` string.

### Remediation Required

1. Remove `_FALLBACK_KEY` entirely. If `VAULT_KEY` env var is absent, raise `ValueError("VAULT_KEY environment variable is not set")`.
2. Replace both `except` logging blocks with a generic message that contains no sensitive values:
   ```python
   fh.write(f"[ERROR] crypto operation failed | error={type(exc).__name__}\n")
   ```

---

## Summary of Reported Locations

| Issue | File | Reported Line | Expected Fix |
|---|---|---|---|
| Bug 1 – NameError on empty search | `src/vault.py` | 58 | Initialize `results = []` before loop; use `append()` |
| Bug 2 – Dict overwrite on update | `src/vault.py` | 71 | Targeted field update, preserve all original keys |
| Security – Hardcoded key | `src/crypto.py` | 5 | Remove fallback; require `VAULT_KEY` env var |
| Security – Plaintext log write | `src/crypto.py` | 24 | Strip sensitive values from exception log messages |
