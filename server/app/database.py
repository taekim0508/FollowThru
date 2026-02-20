from sqlmodel import create_engine, Session, SQLModel
from .config import settings

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    echo=True,  # Set to False in production
    pool_pre_ping=True
)

def get_session():
    """Dependency for getting database session"""
    with Session(engine) as session:
        yield session

def create_db_and_tables():
    """Create all tables"""
    SQLModel.metadata.create_all(engine)
