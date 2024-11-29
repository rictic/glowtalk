from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base
from pathlib import Path

def init_db(db_path="sqlite:///audiobooks.db", run_migrations=True):
    """Initialize the database and optionally run migrations"""
    # if the db does't exist, then we don't run migrations, we just create all tables
    if not Path(db_path).exists():
        run_migrations = False

    engine = create_engine(db_path)

    # Just create all tables from scratch
    Base.metadata.create_all(engine)

    return sessionmaker(bind=engine)
