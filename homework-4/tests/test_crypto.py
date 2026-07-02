"""
Pytest suite for src/crypto.py.

Covers the security remediation from fix-summary.md Task 3:
- get_key() no longer falls back to a hardcoded key; it raises when VAULT_KEY
  is unset.
- encrypt()/decrypt() error logging no longer writes plaintext/ciphertext to
  vault_debug.log.

Run from the homework-4/ directory:
    pytest tests/ -v
"""

import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet, InvalidToken

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import crypto  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Each test runs in a fresh temp dir with VAULT_KEY unset by default,
    so vault_debug.log never leaks between tests and no ambient env state
    from the shell leaks in."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VAULT_KEY", raising=False)
    yield tmp_path


# ---------------------------------------------------------------------------
# get_key — hardcoded fallback key removal
# ---------------------------------------------------------------------------

def test_get_key_raises_when_vault_key_unset():
    with pytest.raises(ValueError, match="VAULT_KEY"):
        crypto.get_key()


def test_get_key_returns_env_value_when_set(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("VAULT_KEY", key)

    assert crypto.get_key() == key.encode()


def test_no_hardcoded_fallback_key_defined():
    """Regression test: _FALLBACK_KEY must be fully removed, not just unused,
    so there is no static key left in source that could be reintroduced."""
    assert not hasattr(crypto, "_FALLBACK_KEY")


# ---------------------------------------------------------------------------
# encrypt / decrypt — happy path
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_round_trip(monkeypatch):
    monkeypatch.setenv("VAULT_KEY", Fernet.generate_key().decode())

    token = crypto.encrypt("hunter2")

    assert token != "hunter2"
    assert crypto.decrypt(token) == "hunter2"


# ---------------------------------------------------------------------------
# encrypt — error log must not contain plaintext
# ---------------------------------------------------------------------------

def test_encrypt_error_log_excludes_plaintext(monkeypatch, tmp_path):
    """Regression test: encrypt() used to write the raw plaintext password
    into vault_debug.log on failure. Force a failure (invalid Fernet key
    format) and confirm the secret value never reaches the log."""
    monkeypatch.setenv("VAULT_KEY", "not-a-valid-fernet-key")

    with pytest.raises(Exception):
        crypto.encrypt("super_secret_password")

    log_path = tmp_path / "vault_debug.log"
    assert log_path.exists()
    log_contents = log_path.read_text()
    assert "super_secret_password" not in log_contents
    assert "[ERROR] encrypt failed | error=" in log_contents


# ---------------------------------------------------------------------------
# decrypt — error log must not contain ciphertext
# ---------------------------------------------------------------------------

def test_decrypt_error_log_excludes_ciphertext(monkeypatch, tmp_path):
    """Regression test: decrypt() used to write the raw ciphertext into
    vault_debug.log on InvalidToken. Confirm the ciphertext value never
    reaches the log."""
    monkeypatch.setenv("VAULT_KEY", Fernet.generate_key().decode())
    bogus_token = "not-a-real-fernet-token"

    with pytest.raises(InvalidToken):
        crypto.decrypt(bogus_token)

    log_path = tmp_path / "vault_debug.log"
    assert log_path.exists()
    log_contents = log_path.read_text()
    assert bogus_token not in log_contents
    assert "[ERROR] decrypt failed | error=" in log_contents
