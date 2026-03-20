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
        # Seed Teams
        team_alpha = db.query(models.Team).filter(models.Team.name == "Alpha").first()
        if not team_alpha:
            team_alpha = models.Team(name="Alpha", description="Equipe de Operações")
            db.add(team_alpha)
            db.commit()
            db.refresh(team_alpha)

        # Seed admin user
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

        # Seed lider user
        lider_exists = db.query(models.User).filter(models.User.username == "lider").first()
        if not lider_exists:
            hashed_password = get_password_hash("lider123")
            lider_user = models.User(
                username="lider",
                email="lider@geotrilha.com.br",
                hashed_password=hashed_password,
                role="lideranca",
                status="approved",
                team_id=team_alpha.id
            )
            db.add(lider_user)

        # Seed Learning Paths
        path_exists = db.query(models.LearningPath).filter(models.LearningPath.title == "Segurança da Informação").first()
        if not path_exists:
            path = models.LearningPath(title="Segurança da Informação", description="Princípios básicos de segurança digital e proteção de dados.")
            db.add(path)
            db.commit()
            db.refresh(path)
            
            # Seed a course
            course = models.Course(path_id=path.id, title="Introdução à LGPD", description="Conheça os fundamentos da Lei Geral de Proteção de Dados.", order=1)
            db.add(course)

        db.commit()
    finally:
        db.close()
