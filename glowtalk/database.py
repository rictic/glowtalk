from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base
from alembic import command
from alembic.config import Config
from pathlib import Path

def init_db(db_path="sqlite:///audiobooks.db", run_migrations=True):
    """Initialize the database and optionally run migrations"""
    engine = create_engine(db_path)

    # Get the alembic.ini path relative to this file
    alembic_ini_path = Path(__file__).parent.parent / "alembic.ini"
    if run_migrations:

        # Run all migrations
        alembic_cfg = Config(str(alembic_ini_path))
        command.upgrade(alembic_cfg, "head")
    else:
        # Just create all tables from scratch
        Base.metadata.create_all(engine)

        # Stamp the database as being at the latest revision
        alembic_cfg = Config(str(alembic_ini_path))
        command.stamp(alembic_cfg, "head")

    Session = sessionmaker(bind=engine)
    return Session()
