#!/usr/bin/env python3
"""CLI-обёртка над app.services.ttl_cleanup.sweep_expired_batches.
Запускается по расписанию (cron/systemd timer на VPS, см. docs/deployment.md).

Пример cron (каждые 15 минут):
  */15 * * * * cd /opt/arbitrpack/apps/api && /opt/arbitrpack/apps/api/.venv/bin/python \
    /opt/arbitrpack/scripts/ttl_cleanup.py >> /var/log/arbitrpack-ttl.log 2>&1
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.db import SessionLocal
from app.services.ttl_cleanup import sweep_expired_batches


def main() -> int:
    db = SessionLocal()
    try:
        deleted = sweep_expired_batches(db)
        print(f"[ttl_cleanup] deleted_batches={len(deleted)}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
