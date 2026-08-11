from sqlalchemy import create_engine, bindparam
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import secrets
import datetime

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
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    # 1. Migration: Rename 'courses' to 'modules' if the new structure isn't there yet
    if "modules" not in tables and "courses" in tables:
        print("Database Migration: Refactoring structure Path -> Course -> Module...")
        with engine.connect() as conn:
            # Rename existing course table to modules
            conn.execute(text("ALTER TABLE courses RENAME TO modules"))
            
            # SQLite: Index names are global. Renaming the table doesn't rename the index.
            # We must drop the old index so SQLAlchemy can create the new one for the 'Course' table.
            try:
                conn.execute(text("DROP INDEX IF EXISTS ix_courses_title"))
                conn.execute(text("DROP INDEX IF EXISTS ix_courses_id"))
            except Exception as e:
                print(f"Warning during index cleanup: {e}")

            # Rename course_id FKs in materials and questions
            # SQLite rename column is supported in newer versions (3.25.0+), 
            # but since we are refactoring, we'll try to keep it safe.
            try:
                conn.execute(text("ALTER TABLE materials RENAME COLUMN course_id TO module_id"))
                conn.execute(text("ALTER TABLE questions RENAME COLUMN course_id TO module_id"))
                conn.execute(text("ALTER TABLE course_progress RENAME TO module_progress"))
                conn.execute(text("ALTER TABLE module_progress RENAME COLUMN course_id TO module_id"))
                conn.execute(text("ALTER TABLE certificates RENAME COLUMN course_id TO module_id"))
            except Exception as e:
                print(f"Warning during column rename: {e}")
            
            conn.commit()

    # If 'modules' table exists, ensure it has the 'course_id' column, missing if renamed
    if "modules" in inspector.get_table_names():
        with engine.connect() as conn:
            columns = [c['name'] for c in inspector.get_columns('modules')]
            if 'course_id' not in columns:
                print("Adding missing column 'course_id' to 'modules' table...")
                try:
                    conn.execute(text("ALTER TABLE modules ADD COLUMN course_id INTEGER REFERENCES courses(id)"))
                    conn.commit()
                except Exception as e:
                    print(f"Warning while adding course_id column: {e}")

    # Ensure users table has new password reset columns
    if "users" in inspector.get_table_names():
        with engine.connect() as conn:
            columns = [c['name'] for c in inspector.get_columns('users')]
            added_any = False
            try:
                if 'reset_token' not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN reset_token VARCHAR"))
                    added_any = True
                if 'reset_token_expires' not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN reset_token_expires DATETIME"))
                    added_any = True
                if 'must_change_password' not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 0"))
                    added_any = True
                
                if added_any:
                    conn.commit()
                    print("Added missing reset password columns to 'users' table.")
            except Exception as e:
                print(f"Warning while adding reset password columns: {e}")

    # Departamento e Time passaram a ser obrigatórios (NOT NULL) em User, e
    # expires_at obrigatório em Certificate. Para bancos já existentes, isso
    # precisa de: (a) um time padrão para acolher usuários sem time, (b) um
    # backfill dos valores nulos, e (c) — só em Postgres, já que SQLite não
    # suporta ALTER COLUMN ... SET NOT NULL sem recriar a tabela — a
    # constraint física. Em bancos novos, create_all() abaixo já cria as
    # colunas como NOT NULL diretamente, então nada disto se aplica.
    if "teams" in inspector.get_table_names() and "users" in inspector.get_table_names():
        with engine.connect() as conn:
            default_team_id = conn.execute(text("SELECT id FROM teams WHERE name = 'Sem Equipe'")).scalar()
            if default_team_id is None:
                conn.execute(text("INSERT INTO teams (name, description) VALUES ('Sem Equipe', 'Time padrão para usuários sem equipe atribuída')"))
                conn.commit()
                default_team_id = conn.execute(text("SELECT id FROM teams WHERE name = 'Sem Equipe'")).scalar()

            conn.execute(text("UPDATE users SET team_id = :tid WHERE team_id IS NULL"), {"tid": default_team_id})
            conn.execute(text("UPDATE users SET department = 'Não informado' WHERE department IS NULL OR department = ''"))
            conn.commit()

            if engine.dialect.name == "postgresql":
                try:
                    conn.execute(text("ALTER TABLE users ALTER COLUMN department SET NOT NULL"))
                    conn.execute(text("ALTER TABLE users ALTER COLUMN team_id SET NOT NULL"))
                    conn.commit()
                except Exception as e:
                    print(f"Warning while enforcing NOT NULL on users columns: {e}")

    if "certificates" in inspector.get_table_names():
        with engine.connect() as conn:
            null_certs = conn.execute(text("SELECT id, issued_at FROM certificates WHERE expires_at IS NULL")).fetchall()
            if null_certs:
                from dateutil.relativedelta import relativedelta
                default_months = int(os.getenv("CERT_DEFAULT_VALIDITY_MONTHS", "12"))
                for cert_id, issued_at in null_certs:
                    if isinstance(issued_at, str):
                        issued_at = datetime.datetime.fromisoformat(issued_at)
                    base = issued_at or datetime.datetime.utcnow()
                    conn.execute(text("UPDATE certificates SET expires_at = :exp WHERE id = :id"), {"exp": base + relativedelta(months=default_months), "id": cert_id})
                conn.commit()

            if engine.dialect.name == "postgresql":
                try:
                    conn.execute(text("ALTER TABLE certificates ALTER COLUMN expires_at SET NOT NULL"))
                    conn.commit()
                except Exception as e:
                    print(f"Warning while enforcing NOT NULL on certificates.expires_at: {e}")

    # 2. Create tables based on new models
    Base.metadata.create_all(bind=engine)
    
    # 3. Post-migration: Create 'Default Courses' for orphaned modules
    db = SessionLocal()
    try:
        from models import LearningPath, Course, Module
        # Check for modules without a course_id
        orphaned_modules = db.query(Module).filter(Module.course_id == None).all()
        if orphaned_modules:
            print(f"Migrating {len(orphaned_modules)} modules to new tier...")
            # For each Path, create one default Course and move modules there
            paths = db.query(LearningPath).all()
            for path in paths:
                # Find modules that belong to this path (using the now-removed path_id column if it still exists in DB)
                # Since SQLAlchemy model for Module no longer has path_id, we use raw SQL to find them
                result = db.execute(text("SELECT id FROM modules WHERE path_id = :pid"), {"pid": path.id})
                module_ids = [row[0] for row in result]

                if module_ids:
                    # Create a default course for this path
                    default_course = Course(path_id=path.id, title="Módulos Gerais", description="Módulos migrados da versão anterior", order=1)
                    db.add(default_course)
                    db.flush()

                    # Update modules to link to this course
                    stmt = text("UPDATE modules SET course_id = :cid WHERE id IN :ids").bindparams(bindparam("ids", expanding=True))
                    db.execute(stmt, {"cid": default_course.id, "ids": module_ids})
            
            # Remove the old path_id column from modules to clean up (SQLite doesn't support DROP COLUMN well before 3.35.0)
            # but we can leave it there as redundant for now.
            db.commit()
    except Exception as e:
        print(f"Error during data migration: {e}")
        db.rollback()
    finally:
        db.close()
    
    # Seed admin user
    from sqlalchemy.orm import Session
    from auth import get_password_hash
    import models

    db = SessionLocal()
    try:
        # Time padrão para usuários sem equipe atribuída (department/team_id
        # são obrigatórios em User desde já)
        default_team = db.query(models.Team).filter(models.Team.name == "Sem Equipe").first()
        if not default_team:
            default_team = models.Team(name="Sem Equipe", description="Time padrão para usuários sem equipe atribuída")
            db.add(default_team)
            db.commit()
            db.refresh(default_team)

        # Seed Teams
        team_alpha = db.query(models.Team).filter(models.Team.name == "Alpha").first()
        if not team_alpha:
            team_alpha = models.Team(name="Alpha", description="Equipe de Operações")
            db.add(team_alpha)
            db.commit()
            db.refresh(team_alpha)

        # Seed admin user — senha aleatória, nunca fixa no código. Impressa
        # uma única vez no log de inicialização; o admin é forçado a trocá-la
        # no primeiro login (mesmo fluxo de must_change_password já usado
        # para reset de senha de outros usuários).
        admin_exists = db.query(models.User).filter(models.User.username == "admin").first()
        if not admin_exists:
            initial_password = secrets.token_urlsafe(12)
            hashed_password = get_password_hash(initial_password)
            admin_user = models.User(
                username="admin",
                email="admin@geotrilha.com.br",
                hashed_password=hashed_password,
                role="admin",
                status="approved",
                department="Administração",
                team_id=default_team.id,
                must_change_password=True
            )
            db.add(admin_user)
            print("=" * 60)
            print("USUÁRIO ADMIN CRIADO — copie a senha agora, ela não será mostrada de novo:")
            print(f"  usuário: admin")
            print(f"  senha:   {initial_password}")
            print("=" * 60)

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
                department="Operações",
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
