# Bug Context: SECUREVAULT-001

**Project:** SecureVault  
**Component:** `src/vault.py`, `src/crypto.py`  
**Severity:** High (Bugs 1 & 2), Critical (Security Flaw)  
**Status:** Open — awaiting automated pipeline remediation

---

## Application Overview

SecureVault is a local CLI password manager written in Python. It stores credentials (service name, username, encrypted password, creation timestamp) in a local `vault.json` file using Fernet symmetric encryption. All cryptographic operations are handled by `src/crypto.py`, and the CLI is exposed through `src/vault.py` via `argparse` subcommands: `init`, `add`, `list`, and `update`.

---

## Issue A — Runtime Crash on Empty Search (Bug 1)

**Severity:** High  
**Location:** `src/vault.py` → `cmd_list()`

### User Symptom

A user runs:

```bash
python src/vault.py list --search nonexistent
```

Instead of seeing `"No entries found."`, the process terminates with an unhandled Python traceback:

```
Traceback (most recent call last):
  File "src/vault.py", line 56, in cmd_list
    for r in results:
NameError: name 'results' is not defined
```

### Root Cause

The local variable `results` is only assigned inside the `if args.search.lower() in entry["service"].lower():` conditional branch. If the `for entry in entries` loop completes without any entry matching the search term, `results` is never defined. The subsequent `for r in results:` line then raises `NameError`.

There is also a secondary defect: even when a match is found, `results = [entry]` overwrites itself on every subsequent match rather than accumulating them, meaning only the last matching entry is ever shown.

### Business Impact

- The primary credential-lookup use case (`list --search`) is broken for any query that returns zero results.
- Any user who mistypes a service name sees a crash with a raw Python traceback, potentially leaking internal file paths.
- The feature is effectively unreliable in production.

### Reproduction Steps

```bash
python src/vault.py init
python src/vault.py add --service github --user alice --password secret1
python src/vault.py list --search nonexistent   # crashes with NameError
```

---

## Issue B — Silent Data Corruption on Update (Bug 2)

**Severity:** High  
**Location:** `src/vault.py` → `cmd_update()`

### User Symptom

A user updates a password:

```bash
python src/vault.py update --service github --password newsecret
```

The CLI confirms `"Password for 'github' updated."` but a subsequent inspection of `vault.json` reveals the entry now only contains `service` and `password` — the `username` and `created_at` fields have been silently erased.

### Root Cause

The update handler replaces the entire entry dictionary in `data["entries"][i]` with a freshly constructed dict containing only `"service"` and `"password"`. The original entry object — which holds `username` and `created_at` — is discarded without warning.

### Business Impact

- Silent, permanent data loss. There is no backup or undo path.
- Username fields must be manually re-added after every password rotation.
- Audit trails (creation timestamps) are destroyed, making it impossible to track when credentials were originally provisioned.
- Violates the principle of least surprise: a password *update* operation must not erase unrelated fields.

### Reproduction Steps

```bash
python src/vault.py init
python src/vault.py add --service github --user alice --password secret1
# Inspect vault.json — entry has: service, username, password, created_at
python src/vault.py update --service github --password newsecret
# Inspect vault.json — entry now only has: service, password
```

---

## Issue C — Hardcoded Encryption Key + Plaintext Debug Logging (Security Flaw)

**Severity:** Critical  
**Location:** `src/crypto.py`

### Symptom 1: Hardcoded Fallback Key

The module defines `_FALLBACK_KEY`, a static base64-encoded Fernet key embedded directly in source code. When the `VAULT_KEY` environment variable is absent (the default for most local installs), this hardcoded key is used to encrypt and decrypt all vault data.

**Risk:** Any person with read access to the repository — including anyone who clones it or finds it in version control history — can use the known key to decrypt the entire vault without any credentials.

### Symptom 2: Unsafe Exception Logging

Both `encrypt()` and `decrypt()` contain `except` blocks that write sensitive data to `vault_debug.log` in plaintext:

- `encrypt()` logs the raw `plaintext` value (i.e., the user's actual password).
- `decrypt()` logs the raw `ciphertext` string.

The log file is never rotated, purged, or access-controlled.

**Risk:** Any encryption or decryption failure (e.g., key mismatch, corrupted vault) silently writes plaintext passwords to an unprotected file on disk. If this file is included in a backup, log aggregation pipeline, or repository commit, credentials are fully exposed.

### Business Impact

- Complete compromise of all stored credentials if the repository is shared.
- Violations of SOC 2 CC6 (logical access), PCI-DSS Requirement 8 (protect system components), and most internal secret-management policies.
- Log hygiene violations: sensitive values must never appear in log output in any form.

---

## Affected Files Summary

| File | Issue |
|---|---|
| `src/vault.py` | Bug 1 (NameError in `cmd_list`), Bug 2 (dict overwrite in `cmd_update`) |
| `src/crypto.py` | Security Flaw (hardcoded `_FALLBACK_KEY`, plaintext `vault_debug.log` writes) |
| `tests/test_vault.py` | Baseline suite does not cover the buggy paths — pipeline must add coverage |
