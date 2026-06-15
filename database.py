from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cv_sorter.db")

# create_engine is SQLAlchemy's connection to the database file
# check_same_thread=False is needed for SQLite when used with FastAPI
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# SessionLocal is a factory — each request gets its own session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# All your models will inherit from this Base class
class Base(DeclarativeBase):
    pass

# Dependency — FastAPI calls this to give each endpoint a fresh DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()