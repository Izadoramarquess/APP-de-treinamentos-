from sqlalchemy import create_engine, inspect, text
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
    """Roda uma vez por processo no startup do FastAPI. Sob gunicorn com
    múltiplos workers (-w 4), isso significa várias cópias deste processo
    rodando ao mesmo tempo contra o MESMO banco — sem serialização, dois
    workers colidem tentando criar a mesma tabela ou inserir o mesmo usuário
    'admin' simultaneamente, e o deploy inteiro cai (visto em produção:
    UniqueViolation em pg_type_typname_nsp_index e em ix_users_username,
    com a senha do admin às vezes nem chegando a aparecer no log porque o
    worker que a gerou morria antes do commit). Um advisory lock do Postgres
    resolve: só quem pega o lock roda de verdade — os outros esperam a
    liberação e, quando a vez deles chega, todas as checagens idempotentes
    abaixo já veem tudo pronto e não fazem nada. SQLite não precisa disso
    (não há múltiplos processos concorrentes no dev local)."""
    is_postgres = engine.dialect.name == "postgresql"
    lock_conn = engine.connect() if is_postgres else None
    if lock_conn is not None:
        lock_conn.execute(text("SELECT pg_advisory_lock(727383001)"))
    try:
        _init_db_locked()
    finally:
        if lock_conn is not None:
            lock_conn.execute(text("SELECT pg_advisory_unlock(727383001)"))
            lock_conn.close()

def _init_db_locked():
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

    # "ativo" e "approved" significavam a mesma coisa (usuário liberado para
    # logar) em pontos diferentes do código — padroniza tudo para "ativo".
    if "users" in inspector.get_table_names():
        with engine.connect() as conn:
            conn.execute(text("UPDATE users SET status = 'ativo' WHERE status = 'approved'"))
            conn.commit()

    # Achatamento Trilha -> Curso -> Módulo em Curso -> Módulo: Curso vira o
    # nível de topo (nunca mais precisa de uma "trilha" por cima pra existir).
    # Curso absorve is_standard_training (vinha de LearningPath) e
    # validity_months/certificate_template_url (vinham de Module — agora o
    # certificado é um por curso, não um por módulo). Em bancos novos,
    # create_all() já cria tudo certo; isto só migra bancos que ainda tinham
    # o modelo antigo (learning_paths / courses.path_id / modules.validity_months).
    if "courses" in inspector.get_table_names():
        with engine.connect() as conn:
            course_columns = [c['name'] for c in inspector.get_columns('courses')]
            added_any = False
            for col, coltype in [("is_standard_training", "BOOLEAN DEFAULT 0"), ("validity_months", "INTEGER"), ("certificate_template_url", "VARCHAR")]:
                if col not in course_columns:
                    conn.execute(text(f"ALTER TABLE courses ADD COLUMN {col} {coltype}"))
                    added_any = True
            if added_any:
                conn.commit()
                course_columns = [c['name'] for c in inspect(engine).get_columns('courses')]

            module_columns = [c['name'] for c in inspector.get_columns('modules')] if "modules" in inspector.get_table_names() else []

            # Backfill is_standard_training a partir da trilha antiga (se a coluna path_id ainda existir).
            if 'path_id' in course_columns and "learning_paths" in inspector.get_table_names():
                conn.execute(text("""
                    UPDATE courses SET is_standard_training = (
                        SELECT is_standard_training FROM learning_paths WHERE learning_paths.id = courses.path_id
                    ) WHERE path_id IS NOT NULL
                """))
                conn.commit()

            # Backfill validity_months/certificate_template_url a partir do primeiro módulo não-nulo de cada curso.
            if 'validity_months' in module_columns:
                rows = conn.execute(text("SELECT course_id, validity_months FROM modules WHERE course_id IS NOT NULL AND validity_months IS NOT NULL")).fetchall()
                seen = set()
                for course_id, months in rows:
                    if course_id in seen: continue
                    seen.add(course_id)
                    conn.execute(text("UPDATE courses SET validity_months = :v WHERE id = :cid AND validity_months IS NULL"), {"v": months, "cid": course_id})
                if rows: conn.commit()
            if 'certificate_template_url' in module_columns:
                rows = conn.execute(text("SELECT course_id, certificate_template_url FROM modules WHERE course_id IS NOT NULL AND certificate_template_url IS NOT NULL")).fetchall()
                seen = set()
                for course_id, url in rows:
                    if course_id in seen: continue
                    seen.add(course_id)
                    conn.execute(text("UPDATE courses SET certificate_template_url = :u WHERE id = :cid AND certificate_template_url IS NULL"), {"u": url, "cid": course_id})
                if rows: conn.commit()

    # Enrollment: path_id -> course_id. Uma matrícula antiga em trilha vira
    # uma matrícula por curso daquela trilha (uma trilha podia ter vários cursos).
    if "enrollments" in inspector.get_table_names():
        with engine.connect() as conn:
            enr_columns = [c['name'] for c in inspector.get_columns('enrollments')]
            if 'course_id' not in enr_columns:
                conn.execute(text("ALTER TABLE enrollments ADD COLUMN course_id INTEGER REFERENCES courses(id)"))
                conn.commit()
                if 'path_id' in enr_columns:
                    old_enrollments = conn.execute(text("SELECT id, user_id, path_id FROM enrollments WHERE path_id IS NOT NULL")).fetchall()
                    for enr_id, user_id, path_id in old_enrollments:
                        course_ids = [r[0] for r in conn.execute(text("SELECT id FROM courses WHERE path_id = :pid"), {"pid": path_id}).fetchall()]
                        if not course_ids:
                            continue
                        conn.execute(text("UPDATE enrollments SET course_id = :cid WHERE id = :eid"), {"cid": course_ids[0], "eid": enr_id})
                        for extra_cid in course_ids[1:]:
                            exists = conn.execute(text("SELECT 1 FROM enrollments WHERE user_id=:uid AND course_id=:cid"), {"uid": user_id, "cid": extra_cid}).first()
                            if not exists:
                                conn.execute(text("INSERT INTO enrollments (user_id, course_id, enrolled_at) VALUES (:uid, :cid, CURRENT_TIMESTAMP)"), {"uid": user_id, "cid": extra_cid})
                    conn.commit()

    # Certificate: module_id -> course_id. Um certificado por módulo virava
    # vários certificados pro mesmo curso — mantém só o mais antigo por
    # (usuário, curso), já que agora é um certificado por curso.
    if "certificates" in inspector.get_table_names():
        with engine.connect() as conn:
            cert_columns = [c['name'] for c in inspector.get_columns('certificates')]
            if 'course_id' not in cert_columns:
                conn.execute(text("ALTER TABLE certificates ADD COLUMN course_id INTEGER REFERENCES courses(id)"))
                conn.commit()
                if 'module_id' in cert_columns:
                    old_certs = conn.execute(text("SELECT id, user_id, module_id FROM certificates WHERE module_id IS NOT NULL ORDER BY issued_at ASC")).fetchall()
                    seen_pairs = set()
                    for cert_id, user_id, module_id in old_certs:
                        course_row = conn.execute(text("SELECT course_id FROM modules WHERE id = :mid"), {"mid": module_id}).first()
                        if not course_row or course_row[0] is None:
                            continue
                        course_id = course_row[0]
                        key = (user_id, course_id)
                        if key in seen_pairs:
                            conn.execute(text("DELETE FROM certificates WHERE id = :cid"), {"cid": cert_id})
                            continue
                        seen_pairs.add(key)
                        conn.execute(text("UPDATE certificates SET course_id = :cid WHERE id = :id"), {"cid": course_id, "id": cert_id})
                    conn.commit()

    # Colunas de dedupe do job de e-mail automático (lembrete de curso parado
    # e aviso de certificado vencendo) — sem elas o job manda o mesmo e-mail
    # de novo toda vez que roda.
    if "enrollments" in inspector.get_table_names():
        with engine.connect() as conn:
            enr_columns = [c['name'] for c in inspector.get_columns('enrollments')]
            if 'reminder_sent' not in enr_columns:
                conn.execute(text("ALTER TABLE enrollments ADD COLUMN reminder_sent BOOLEAN DEFAULT 0"))
                conn.commit()
    if "certificates" in inspector.get_table_names():
        with engine.connect() as conn:
            cert_columns = [c['name'] for c in inspector.get_columns('certificates')]
            if 'expiry_reminder_sent' not in cert_columns:
                conn.execute(text("ALTER TABLE certificates ADD COLUMN expiry_reminder_sent BOOLEAN DEFAULT 0"))
                conn.commit()

    # Multi-empresa: GeoTrilha passou a atender mais de uma empresa a partir
    # do mesmo banco. Toda empresa/curso/time já existente pertencia
    # implicitamente à empresa que já estava em produção — cria essa empresa
    # ("Geo") e faz o backfill antes de mais nada, pra tudo que já existe
    # continuar funcionando sem intervenção manual.
    import models as _models
    if "companies" not in inspector.get_table_names():
        _models.Company.__table__.create(bind=engine, checkfirst=True)
        inspector = inspect(engine)

    with engine.connect() as conn:
        default_company_id = conn.execute(text("SELECT id FROM companies WHERE name = 'Geo'")).scalar()
        if default_company_id is None:
            # created_at explícito — inserindo via SQL puro (não pela ORM), o
            # default do modelo (Python-side) nunca dispara, e CompanySchema
            # exige created_at não-nulo.
            conn.execute(text("INSERT INTO companies (name, created_at) VALUES ('Geo', CURRENT_TIMESTAMP)"))
            conn.commit()
            default_company_id = conn.execute(text("SELECT id FROM companies WHERE name = 'Geo'")).scalar()
        # Backfill defensivo — cobre quem já rodou uma versão anterior desta
        # migração que não setava created_at.
        conn.execute(text("UPDATE companies SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
        conn.commit()

    for _table in ("teams", "courses", "users"):
        if _table in inspector.get_table_names():
            with engine.connect() as conn:
                _cols = [c['name'] for c in inspector.get_columns(_table)]
                if 'company_id' not in _cols:
                    conn.execute(text(f"ALTER TABLE {_table} ADD COLUMN company_id INTEGER REFERENCES companies(id)"))
                    conn.commit()
                    conn.execute(text(f"UPDATE {_table} SET company_id = :cid WHERE company_id IS NULL"), {"cid": default_company_id})
                    conn.commit()

    # Time.name deixou de poder ser globalmente único: toda empresa nova
    # precisa do próprio time "Sem Equipe" com o MESMO nome de outra
    # empresa, o que colide com o índice único antigo (Column(unique=True)).
    # Remove esse índice — unicidade passa a ser aplicada só na aplicação,
    # escopada por (company_id, name).
    if "teams" in inspector.get_table_names():
        with engine.connect() as conn:
            try:
                conn.execute(text("DROP INDEX IF EXISTS ix_teams_name"))
                conn.commit()
            except Exception as e:
                print(f"Warning ao remover índice único de teams.name: {e}")

    # teams.company_id e courses.company_id são sempre obrigatórios (só
    # User.company_id fica nulo, e só para super_admin) — reforça a
    # constraint física em Postgres, igual já é feito para outras colunas
    # que passaram de opcionais a obrigatórias neste arquivo.
    if engine.dialect.name == "postgresql":
        for _table, _col in (("teams", "company_id"), ("courses", "company_id")):
            if _table in inspector.get_table_names():
                with engine.connect() as conn:
                    try:
                        conn.execute(text(f"ALTER TABLE {_table} ALTER COLUMN {_col} SET NOT NULL"))
                        conn.commit()
                    except Exception as e:
                        print(f"Warning while enforcing NOT NULL on {_table}.{_col}: {e}")

    # Promove o admin do seed original a super_admin (enxerga as duas
    # empresas) — só roda uma vez, só se ainda não existir nenhum
    # super_admin e houver exatamente um 'admin' (o cenário de quem já
    # tinha o sistema rodando antes da divisão por empresa existir).
    if "users" in inspector.get_table_names():
        with engine.connect() as conn:
            super_admin_count = conn.execute(text("SELECT COUNT(*) FROM users WHERE role = 'super_admin'")).scalar()
            admin_count = conn.execute(text("SELECT COUNT(*) FROM users WHERE role = 'admin'")).scalar()
            if super_admin_count == 0 and admin_count == 1:
                conn.execute(text("UPDATE users SET role = 'super_admin', company_id = NULL WHERE role = 'admin'"))
                conn.commit()

    # 2. Create tables based on new models
    Base.metadata.create_all(bind=engine)

    # Seed admin user
    from sqlalchemy.orm import Session
    from auth import get_password_hash
    import models

    db = SessionLocal()
    try:
        # Time padrão para usuários sem equipe atribuída (department/team_id
        # são obrigatórios em User desde já) — escopado pela empresa padrão
        # criada acima; empresas novas ganham a própria "Sem Equipe" sob
        # demanda via auth.get_default_team(db, company_id).
        default_team = db.query(models.Team).filter(models.Team.name == "Sem Equipe", models.Team.company_id == default_company_id).first()
        if not default_team:
            default_team = models.Team(name="Sem Equipe", description="Time padrão para usuários sem equipe atribuída", company_id=default_company_id)
            db.add(default_team)
            db.commit()
            db.refresh(default_team)

        # Seed Teams
        team_alpha = db.query(models.Team).filter(models.Team.name == "Alpha", models.Team.company_id == default_company_id).first()
        if not team_alpha:
            team_alpha = models.Team(name="Alpha", description="Equipe de Operações", company_id=default_company_id)
            db.add(team_alpha)
            db.commit()
            db.refresh(team_alpha)

        # Seed admin user — senha aleatória, nunca fixa no código. Impressa
        # uma única vez no log de inicialização; o admin é forçado a trocá-la
        # no primeiro login (mesmo fluxo de must_change_password já usado
        # para reset de senha de outros usuários).
        admin_exists = db.query(models.User).filter(models.User.username == "admin").first()
        new_admin_password = None
        if not admin_exists:
            initial_password = secrets.token_urlsafe(12)
            hashed_password = get_password_hash(initial_password)
            admin_user = models.User(
                username="admin",
                email="admin@geotrilha.com.br",
                hashed_password=hashed_password,
                role="super_admin",
                status="ativo",
                department="Administração",
                team_id=default_team.id,
                company_id=None,
                must_change_password=True
            )
            db.add(admin_user)
            new_admin_password = initial_password

        # Seed lider user
        lider_exists = db.query(models.User).filter(models.User.username == "lider").first()
        if not lider_exists:
            hashed_password = get_password_hash("lider123")
            lider_user = models.User(
                username="lider",
                email="lider@geotrilha.com.br",
                hashed_password=hashed_password,
                role="lideranca",
                status="ativo",
                department="Operações",
                team_id=team_alpha.id,
                company_id=default_company_id
            )
            db.add(lider_user)

        # Seed Course (Curso é o nível de topo agora — não existe mais trilha por cima)
        course_exists = db.query(models.Course).filter(models.Course.title == "Segurança da Informação").first()
        if not course_exists:
            course = models.Course(title="Segurança da Informação", description="Princípios básicos de segurança digital e proteção de dados — Introdução à LGPD.", order=1, company_id=default_company_id)
            db.add(course)

        db.commit()

        # Só imprime a senha depois do commit confirmar de verdade — se a
        # senha aparecesse antes e o commit falhasse (ex.: corrida entre
        # workers), o log mostraria uma senha de uma conta que não existe.
        if new_admin_password:
            print("=" * 60)
            print("USUÁRIO ADMIN CRIADO — copie a senha agora, ela não será mostrada de novo:")
            print(f"  usuário: admin")
            print(f"  senha:   {new_admin_password}")
            print("=" * 60)
    finally:
        db.close()
