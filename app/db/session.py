from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


BASE_DIR = Path(__file__).resolve().parents[2]
database_url = make_url(settings.database_url)
engine_kwargs = {"future": True}
if database_url.drivername.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    if database_url.database:
        sqlite_path = Path(database_url.database)
        if not sqlite_path.is_absolute():
            database_url = database_url.set(database=str((BASE_DIR / sqlite_path).resolve()))

engine = create_engine(database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
