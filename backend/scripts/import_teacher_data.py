import argparse
import json
import logging
from dataclasses import asdict
from pathlib import Path

from sqlmodel import Session

from app.core.db import engine
from app.data_import import import_components, import_vulnerabilities

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import the teacher-provided CVE and component SQL into OpenGuard."
    )
    parser.add_argument("--vul-sql", type=Path, required=True, help="Path to vul.sql")
    parser.add_argument("--comp-sql", type=Path, required=True, help="Path to comp.sql")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate the files, then roll back database changes.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for path in (args.vul_sql, args.comp_sql):
        if not path.is_file():
            raise FileNotFoundError(f"SQL file not found: {path}")

    with Session(engine) as session:
        vulnerability_report = import_vulnerabilities(session, args.vul_sql)
        component_report = import_components(session, args.comp_sql)
        if args.dry_run:
            session.rollback()
        else:
            session.commit()

    result = {
        "dry_run": args.dry_run,
        "vulnerabilities": asdict(vulnerability_report),
        "components": asdict(component_report),
    }
    logger.info(json.dumps(result, ensure_ascii=False, indent=2))

    if vulnerability_report.failed or component_report.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
