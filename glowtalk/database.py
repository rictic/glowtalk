from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base
from pathlib import Path

def init_db(db_path="sqlite:///audiobooks.db", run_migrations=True):
    """Initialize the database and optionally run migrations"""
    engine = create_engine(db_path)
    # Create all tables
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
