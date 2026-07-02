import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from crypto import encrypt, decrypt

VAULT_FILE = Path("vault.json")


def load_vault() -> dict:
    if not VAULT_FILE.exists():
        print("Vault not initialized. Run 'python vault.py init' first.")
        sys.exit(1)
    with open(VAULT_FILE, "r") as f:
        data = json.load(f)
    return data


def save_vault(data: dict) -> None:
    with open(VAULT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def cmd_init(args) -> None:
    if VAULT_FILE.exists():
        print("Vault already initialized.")
        return
    save_vault({"entries": []})
    print("Vault initialized.")


def cmd_add(args) -> None:
    data = load_vault()
    encrypted_password = encrypt(args.password)
    entry = {
        "service": args.service,
        "username": args.user,
        "password": encrypted_password,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data["entries"].append(entry)
    save_vault(data)
    print(f"Entry for '{args.service}' added.")


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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="vault",
        description="SecureVault – local encrypted credential store",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Initialize the vault file.")

    add_p = subparsers.add_parser("add", help="Add a new credential entry.")
    add_p.add_argument("--service", required=True, help="Service name")
    add_p.add_argument("--user", required=True, help="Username")
    add_p.add_argument("--password", required=True, help="Password")

    list_p = subparsers.add_parser("list", help="List or search credential entries.")
    list_p.add_argument("--search", default=None, help="Filter by service name")

    update_p = subparsers.add_parser("update", help="Update a credential's password.")
    update_p.add_argument("--service", required=True, help="Service name")
    update_p.add_argument("--password", required=True, help="New password")

    args = parser.parse_args()

    dispatch = {
        "init": cmd_init,
        "add": cmd_add,
        "list": cmd_list,
        "update": cmd_update,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
