from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as DatabaseSession
from sqlalchemy.orm import sessionmaker

from persona.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def session_factory() -> sessionmaker[DatabaseSession]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[DatabaseSession]:
    with session_factory()() as db:
        yield db
