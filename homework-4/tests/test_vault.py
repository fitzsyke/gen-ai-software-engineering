"""
Pytest suite for SecureVault.

Covers: vault initialisation, credential addition, list/search (including the
no-match path fixed for Bug 1), and update (including metadata preservation
fixed for Bug 2).

Run from the homework-4/ directory:
    pytest tests/ -v
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

VAULT_PY = Path(__file__).parent.parent / "src" / "vault.py"


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """
    Each test runs in a fresh temporary directory with a unique encryption key.
    vault.py uses Path("vault.json") (relative CWD), so changing directory
    ensures tests never share state and vault.json is never left behind.
    """
    monkeypatch.chdir(tmp_path)
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("VAULT_KEY", key)
    yield tmp_path


def vault(*args) -> subprocess.CompletedProcess:
    """Invoke a vault CLI command and return the CompletedProcess result."""
    return subprocess.run(
        [sys.executable, str(VAULT_PY)] + list(args),
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def test_init_creates_vault_file(isolated_env):
    result = vault("init")

    assert result.returncode == 0, result.stderr
    vault_file = isolated_env / "vault.json"
    assert vault_file.exists(), "vault.json should exist after init"

    data = json.loads(vault_file.read_text())
    assert data == {"entries": []}, "Newly initialised vault must be empty"


def test_init_is_idempotent(isolated_env):
    vault("init")
    result = vault("init")

    assert result.returncode == 0, result.stderr
    assert "already initialized" in result.stdout


def test_init_output_message(isolated_env):
    result = vault("init")

    assert "initialized" in result.stdout.lower()


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def test_add_creates_entry(isolated_env):
    vault("init")
    result = vault("add", "--service", "github", "--user", "alice", "--password", "s3cr3t")

    assert result.returncode == 0, result.stderr
    data = json.loads((isolated_env / "vault.json").read_text())
    assert len(data["entries"]) == 1

    entry = data["entries"][0]
    assert entry["service"] == "github"
    assert entry["username"] == "alice"
    assert "password" in entry
    assert "created_at" in entry


def test_add_stores_password_encrypted(isolated_env):
    vault("init")
    vault("add", "--service", "github", "--user", "alice", "--password", "plaintext_pass")

    data = json.loads((isolated_env / "vault.json").read_text())
    stored = data["entries"][0]["password"]
    assert stored != "plaintext_pass", "Password must not be stored in plaintext"
    assert len(stored) > 20, "Encrypted token should be significantly longer than the input"


def test_add_multiple_entries(isolated_env):
    vault("init")
    vault("add", "--service", "github", "--user", "alice", "--password", "p1")
    vault("add", "--service", "gitlab", "--user", "bob", "--password", "p2")
    vault("add", "--service", "npm", "--user", "charlie", "--password", "p3")

    data = json.loads((isolated_env / "vault.json").read_text())
    assert len(data["entries"]) == 3

    services = {e["service"] for e in data["entries"]}
    assert services == {"github", "gitlab", "npm"}


def test_add_entry_has_all_required_fields(isolated_env):
    vault("init")
    vault("add", "--service", "myapp", "--user", "dev", "--password", "devpass")

    data = json.loads((isolated_env / "vault.json").read_text())
    entry = data["entries"][0]

    for field in ("service", "username", "password", "created_at"):
        assert field in entry, f"Entry must contain field '{field}'"


def test_add_prints_confirmation(isolated_env):
    vault("init")
    result = vault("add", "--service", "github", "--user", "alice", "--password", "pass")

    assert "github" in result.stdout
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# list (happy path only — Bug 1 path intentionally not covered)
# ---------------------------------------------------------------------------

def test_list_shows_all_entries(isolated_env):
    vault("init")
    vault("add", "--service", "github", "--user", "alice", "--password", "p1")
    result = vault("list")

    assert result.returncode == 0, result.stderr
    assert "github" in result.stdout
    assert "alice" in result.stdout


def test_list_without_search_shows_all_services(isolated_env):
    vault("init")
    vault("add", "--service", "github", "--user", "alice", "--password", "p1")
    vault("add", "--service", "gitlab", "--user", "bob", "--password", "p2")
    result = vault("list")

    assert "github" in result.stdout
    assert "gitlab" in result.stdout


def test_list_with_matching_search_returns_result(isolated_env):
    vault("init")
    vault("add", "--service", "github", "--user", "alice", "--password", "p1")
    vault("add", "--service", "gitlab", "--user", "bob", "--password", "p2")
    result = vault("list", "--search", "github")

    assert result.returncode == 0, result.stderr
    assert "github" in result.stdout


def test_list_search_excludes_non_matching_entries(isolated_env):
    vault("init")
    vault("add", "--service", "github", "--user", "alice", "--password", "p1")
    vault("add", "--service", "gitlab", "--user", "bob", "--password", "p2")
    result = vault("list", "--search", "github")

    assert "gitlab" not in result.stdout


def test_list_search_with_no_match_prints_not_found_message(isolated_env):
    """Regression test for Bug 1: previously raised NameError because `results`
    was only assigned inside the loop body, so a non-matching search crashed
    instead of printing a message."""
    vault("init")
    vault("add", "--service", "github", "--user", "alice", "--password", "p1")
    result = vault("list", "--search", "nonexistent")

    assert result.returncode == 0, result.stderr
    assert "No entries found." in result.stdout
    assert "NameError" not in result.stderr


def test_list_search_matches_multiple_entries(isolated_env):
    vault("init")
    vault("add", "--service", "github", "--user", "alice", "--password", "p1")
    vault("add", "--service", "github-enterprise", "--user", "bob", "--password", "p2")
    vault("add", "--service", "npm", "--user", "charlie", "--password", "p3")
    result = vault("list", "--search", "github")

    assert "alice" in result.stdout
    assert "bob" in result.stdout
    assert "charlie" not in result.stdout


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

def test_update_changes_password(isolated_env):
    vault("init")
    vault("add", "--service", "github", "--user", "alice", "--password", "old_pass")
    before = json.loads((isolated_env / "vault.json").read_text())["entries"][0]["password"]

    result = vault("update", "--service", "github", "--password", "new_pass")

    assert result.returncode == 0, result.stderr
    after = json.loads((isolated_env / "vault.json").read_text())["entries"][0]["password"]
    assert after != before


def test_update_preserves_service_username_and_created_at(isolated_env):
    """Regression test for Bug 2: update used to replace the entire entry with
    only {service, password}, silently dropping username and created_at."""
    vault("init")
    vault("add", "--service", "github", "--user", "alice", "--password", "old_pass")
    before = json.loads((isolated_env / "vault.json").read_text())["entries"][0]

    vault("update", "--service", "github", "--password", "new_pass")

    after = json.loads((isolated_env / "vault.json").read_text())["entries"][0]
    assert after["service"] == before["service"]
    assert after["username"] == before["username"]
    assert after["created_at"] == before["created_at"]


def test_update_adds_updated_at_timestamp(isolated_env):
    vault("init")
    vault("add", "--service", "github", "--user", "alice", "--password", "old_pass")
    result = vault("update", "--service", "github", "--password", "new_pass")

    assert result.returncode == 0, result.stderr
    entry = json.loads((isolated_env / "vault.json").read_text())["entries"][0]
    assert "updated_at" in entry


def test_update_only_modifies_targeted_entry(isolated_env):
    vault("init")
    vault("add", "--service", "github", "--user", "alice", "--password", "p1")
    vault("add", "--service", "gitlab", "--user", "bob", "--password", "p2")
    before_gitlab = json.loads((isolated_env / "vault.json").read_text())["entries"][1]

    vault("update", "--service", "github", "--password", "new_pass")

    after_gitlab = json.loads((isolated_env / "vault.json").read_text())["entries"][1]
    assert after_gitlab == before_gitlab


def test_update_nonexistent_service_reports_not_found(isolated_env):
    vault("init")
    vault("add", "--service", "github", "--user", "alice", "--password", "p1")
    result = vault("update", "--service", "does-not-exist", "--password", "new_pass")

    assert "not found" in result.stdout
    entry = json.loads((isolated_env / "vault.json").read_text())["entries"][0]
    assert "updated_at" not in entry
