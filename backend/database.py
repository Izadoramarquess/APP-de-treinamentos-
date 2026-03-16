from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Database Configuration
# Default to SQLite for local development if DATABASE_URL is not set
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'training_platform.db')}")

# PostgreSQL fix: SQLAlchemy requires postgresql:// instead of postgres://
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Seed admin user
    from sqlalchemy.orm import Session
    from auth import get_password_hash
    import models

    db = SessionLocal()
    try:
        admin_exists = db.query(models.User).filter(models.User.username == "admin").first()
        if not admin_exists:
            hashed_password = get_password_hash("admin")
            admin_user = models.User(
                username="admin",
                email="admin@geotrilha.com.br",
                hashed_password=hashed_password,
                role="admin",
                status="approved"
            )
            db.add(admin_user)
            db.commit()
    finally:
        db.close()
