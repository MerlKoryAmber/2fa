"""Stamp alembic head when tables exist from pre-migration bootstrap."""

from sqlalchemy import create_engine, inspect, text

from app.config import settings


def main() -> None:
    engine = create_engine(settings.database_url)
    try:
        names = inspect(engine).get_table_names()
        if "admins" not in names:
            return
        with engine.connect() as conn:
            try:
                conn.execute(text("SELECT version_num FROM alembic_version"))
                return
            except Exception:
                pass
        from alembic.config import Config
        from alembic import command

        cfg = Config("alembic.ini")
        command.stamp(cfg, "head")
        print("stamped alembic head for existing schema")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
