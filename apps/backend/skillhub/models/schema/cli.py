from __future__ import annotations

import argparse

from skillhub.models.schema.database import create_postgres_engine, resolve_database_url
from skillhub.models.schema.migrations import prepare_database, verify_database_revision


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the SkillHub PostgreSQL schema.")
    parser.add_argument("command", choices=("upgrade", "check"))
    args = parser.parse_args()
    engine = create_postgres_engine(resolve_database_url())
    try:
        if args.command == "upgrade":
            prepare_database(engine)
        else:
            verify_database_revision(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
