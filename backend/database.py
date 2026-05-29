#sqlalchemy engine + session. models inherit from Base here.
#fastapi: Depends(get_db). workers/scripts: session_scope().

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings


class Base(DeclarativeBase):
    #all orm models subclass this
    pass


#pool_pre_ping handles supabase pooler dropping idle conns
engine = create_engine(
    settings.DATABASE_URL or "postgresql+psycopg2://placeholder",
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    #fastapi dep: `db: Session = Depends(get_db)`
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


#[GenAI Use] Prompt: Write a python context manager called session_scope that
#wraps a SQLAlchemy SessionLocal. Should yield a session, commit on success, roll back
#on any exception, and always close the session in a finally block. It should be 
#type annotated as Generator[Session, None, None].
#[GenAI Use] LLM Response:
@contextmanager
def session_scope() -> Generator[Session, None, None]:
    #non-fastapi callers. commits on success, rolls back on exc.
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
#[GenAI Use] Response end
#[GenAI Use] Reflection: After looking at the code and running tests, I believe that this
#is what we are looking for
