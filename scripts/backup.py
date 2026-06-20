from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT_PATH = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_PATH))
import config


PROJECT_ROOT = config.PROJECT_ROOT
BACKUP_ROOT = PROJECT_ROOT / "backups"


def backup_sqlite(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Banco nao encontrado: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)


def copy_if_exists(source: Path, target: Path) -> None:
    if not source.exists():
        return
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def run_backup(include_assets: bool = True) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target_dir = BACKUP_ROOT / f"mastersync-{stamp}"
    target_dir.mkdir(parents=True, exist_ok=True)

    backup_sqlite(config.DATABASE_PATH, target_dir / "mastersync.sqlite3")
    copy_if_exists(PROJECT_ROOT / ".env.example", target_dir / ".env.example")
    copy_if_exists(config.SCHEMA_PATH, target_dir / "schema.sql")

    if include_assets:
        copy_if_exists(config.ASSETS_DIR, target_dir / "assets")

    manifest = target_dir / "backup_manifest.txt"
    manifest.write_text(
        "\n".join(
            [
                "Master SYNC backup",
                f"created_at={datetime.now().isoformat(timespec='seconds')}",
                f"database={config.DATABASE_PATH}",
                f"assets_included={include_assets}",
            ]
        ),
        encoding="utf-8",
    )
    return target_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria backup local do Master SYNC.")
    parser.add_argument("--no-assets", action="store_true", help="Nao copia a pasta assets.")
    args = parser.parse_args()
    target = run_backup(include_assets=not args.no_assets)
    print(f"Backup criado em: {target}")


if __name__ == "__main__":
    main()
