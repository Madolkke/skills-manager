"""Manually seed the built-in expression function catalog."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from sqlalchemy import select

from skillhub.models.rules.workflows.expression.registry import builtin_function_documents
from skillhub.models.schema.database import create_postgres_engine, resolve_database_url
from skillhub.models.schema.orm import ExpressionFunction


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed built-in Workflow expression functions.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing records with the code baseline.")
    parser.add_argument("--actor", default="seed-expression-functions", help="Audit actor stored on changed rows.")
    args = parser.parse_args()
    engine = create_postgres_engine(resolve_database_url())
    created = skipped = updated = 0
    try:
        with engine.begin() as connection:
            for document in builtin_function_documents():
                current = connection.execute(
                    select(ExpressionFunction.__table__.c.id).where(ExpressionFunction.__table__.c.name == document["name"])
                ).scalar_one_or_none()
                now = datetime.now(timezone.utc)
                values = {
                    "name": document["name"],
                    "description": document["description"],
                    "parameter_schema": document["parameterSchema"],
                    "return_schema": document["returnSchema"],
                    "body": document["body"],
                    "language": document["language"],
                    "is_builtin": True,
                    "enabled": True,
                    "updated_by": args.actor,
                    "updated_at": now,
                }
                if current is None:
                    connection.execute(ExpressionFunction.__table__.insert().values(
                        id=f"expression-function-{document['name']}",
                        created_by=args.actor,
                        created_at=now,
                        **values,
                    ))
                    created += 1
                elif args.force:
                    connection.execute(
                        ExpressionFunction.__table__.update()
                        .where(ExpressionFunction.__table__.c.id == current)
                        .values(**values)
                    )
                    updated += 1
                else:
                    skipped += 1
    finally:
        engine.dispose()
    print(f"expression functions: created={created} skipped={skipped} updated={updated}")


if __name__ == "__main__":
    main()
