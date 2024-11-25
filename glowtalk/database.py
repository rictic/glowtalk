from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

def init_db(db_path="sqlite:///audiobooks.db"):
    engine = create_engine(db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

