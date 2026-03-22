from sqlmodel import create_engine, Session, SQLModel
from .config import settings

engine_kwargs = {
    "echo": True,  # Set to False in production
    "pool_pre_ping": True,
}

# SQLite needs this when used in a FastAPI app with threaded request handling.
if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

# Create engine
engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

def get_session():
    """Dependency for getting database session"""
    with Session(engine) as session:
        yield session

def create_db_and_tables():
    """Create all tables"""
    SQLModel.metadata.create_all(engine)
