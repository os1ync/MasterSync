from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import config


ENV_PATH = config.PROJECT_ROOT / ".env"


def upsert_env_value(lines: list[str], key: str, value: str) -> list[str]:
    found = False
    updated: list[str] = []
    for line in lines:
        if line.startswith(f"{key}="):
            updated.append(f"{key}={value}")
            found = True
        else:
            updated.append(line)
    if not found:
        updated.append(f"{key}={value}")
    return updated


def update_env_owner(owner_id: str) -> None:
    if not owner_id.isdigit():
        raise ValueError("OWNER_ID precisa ser numerico.")

    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    updated = upsert_env_value(lines, "OWNER_ID", owner_id)
    current_admins: set[str] = {owner_id}
    for line in updated:
        if line.startswith("GLOBAL_ADMIN_IDS="):
            raw = line.split("=", 1)[1]
            current_admins.update(item.strip() for item in raw.split(",") if item.strip().isdigit())
    updated = upsert_env_value(updated, "GLOBAL_ADMIN_IDS", ",".join(sorted(current_admins)))

    ENV_PATH.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Define o dono global do Master SYNC no arquivo .env.")
    parser.add_argument("owner_id", help="ID Discord do dono global do bot.")
    args = parser.parse_args()
    update_env_owner(args.owner_id.strip())
    print("OWNER_ID e GLOBAL_ADMIN_IDS atualizados no .env. Reinicie o bot para aplicar.")


if __name__ == "__main__":
    main()
