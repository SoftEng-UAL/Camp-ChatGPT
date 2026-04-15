import os
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/database")

class Base(DeclarativeBase):
    pass

def create_db_engine():
    # pool_pre_ping helps recover from dropped connections
    return create_engine(DATABASE_URL, pool_pre_ping=True)

engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def wait_for_db(max_wait_seconds: int = 60) -> None:
    """Simple retry loop so the API can start reliably under docker-compose."""
    start = time.time()
    last_err = None
    while time.time() - start < max_wait_seconds:
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2)
    raise RuntimeError(f"Database not ready after {max_wait_seconds}s: {last_err}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
