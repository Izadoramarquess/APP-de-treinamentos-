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
            for col, coltype in [("is_standard_training", "BOOLEAN DEFAULT 0"), ("validity_months", "INTEGER"), ("certificate_template_url", "VARCHAR"), ("workload_hours", "INTEGER")]:
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

    # Dados pro novo modelo de certificado: quem assina por essa empresa e a
    # cidade que aparece na data de emissão.
    with engine.connect() as conn:
        company_columns = [c['name'] for c in inspect(engine).get_columns('companies')]
        for col in ("signatory_name", "signatory_role", "city"):
            if col not in company_columns:
                conn.execute(text(f"ALTER TABLE companies ADD COLUMN {col} VARCHAR"))
                conn.commit()

    # Nome completo — username sozinho (ex.: "raul.guilherme") não é
    # apresentável no certificado.
    if "users" in inspector.get_table_names():
        with engine.connect() as conn:
            user_columns = [c['name'] for c in inspect(engine).get_columns('users')]
            if "full_name" not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR"))
                conn.commit()

    for _table in ("teams", "users"):
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

    # teams.company_id é sempre obrigatório (só User.company_id fica nulo,
    # e só para super_admin) — reforça a constraint física em Postgres,
    # igual já é feito para outras colunas que passaram de opcionais a
    # obrigatórias neste arquivo.
    if engine.dialect.name == "postgresql":
        for _table, _col in (("teams", "company_id"),):
            if _table in inspector.get_table_names():
                with engine.connect() as conn:
                    try:
                        conn.execute(text(f"ALTER TABLE {_table} ALTER COLUMN {_col} SET NOT NULL"))
                        conn.commit()
                    except Exception as e:
                        print(f"Warning while enforcing NOT NULL on {_table}.{_col}: {e}")

    # Curso deixou de pertencer a uma empresa (virou catálogo global) — a
    # coluna courses.company_id fica pra trás no banco (sem valor pra dados
    # antigos), então a constraint NOT NULL que uma versão anterior desta
    # migração aplicou em Postgres precisa ser relaxada, senão todo INSERT
    # novo em courses (que não manda mais company_id) quebra.
    if engine.dialect.name == "postgresql" and "courses" in inspector.get_table_names():
        _course_cols = [c['name'] for c in inspector.get_columns('courses')]
        if 'company_id' in _course_cols:
            with engine.connect() as conn:
                try:
                    conn.execute(text("ALTER TABLE courses ALTER COLUMN company_id DROP NOT NULL"))
                    conn.commit()
                except Exception as e:
                    print(f"Warning while relaxing NOT NULL on courses.company_id: {e}")

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

    # Líder passa a poder liderar mais de uma equipe (team_leaders é
    # separado de users.team_id, que continua sendo só a equipe-base da
    # pessoa) — backfill idempotente: todo líder já existente vira 1 linha
    # aqui, preservando exatamente a equipe que ele já liderava.
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO team_leaders (team_id, user_id)
            SELECT team_id, id FROM users u
            WHERE role = 'lideranca'
              AND NOT EXISTS (SELECT 1 FROM team_leaders tl WHERE tl.user_id = u.id AND tl.team_id = u.team_id)
        """))
        conn.commit()

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
            course = models.Course(title="Segurança da Informação", description="Princípios básicos de segurança digital e proteção de dados — Introdução à LGPD.", order=1)
            db.add(course)

        _seed_nr_quiz_questions(db)

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


# Questionários de NR fornecidos pela Iza (extraídos dos .docx que ela
# mandou) — cada chave é o título EXATO do curso já cadastrado em produção
# (conferido por print da tela de Cursos), pra casar a pergunta com o
# curso certo sem precisar saber o id.
_NR_QUIZ_DATA = {
    "NR-35 Trabalho em altura": [
        {"text": "De acordo com o item 35.1.2 da NR 35, considera-se trabalho em altura toda atividade executada acima de qual limite em relação ao nível inferior, onde haja risco de queda?",
         "option_a": "1,00 metro", "option_b": "1,50 metros", "option_c": "2,00 metros", "option_d": "2,50 metros", "correct_option": "C"},
        {"text": "A aptidão médica do trabalhador para executar atividades em altura deve ser avaliada periodicamente. Em qual documento legal essa aptidão específica deve constar obrigatoriamente?",
         "option_a": "Na Ordem de Serviço (OS)", "option_b": "No Atestado de Saúde Ocupacional (ASO)", "option_c": "Na Permissão de Trabalho (PT)", "option_d": "Na Carteira de Trabalho (CTPS)", "correct_option": "B"},
        {"text": "Toda atividade de trabalho em altura que não seja rotineira deve ser precedida de uma análise minuciosa e autorizada formalmente. Quais são os dois documentos obrigatórios para essas atividades?",
         "option_a": "Análise de Risco (AR) e Permissão de Trabalho (PT)", "option_b": "Ordem de Serviço (OS) e Ficha de EPI", "option_c": "Relatório de Inspeção e Plano de Abandono", "option_d": "Mapa de Riscos e Check-list de Máquinas", "correct_option": "A"},
        {"text": "De acordo com a hierarquia de controle estabelecida na NR 35 para o planejamento das atividades, qual deve ser a primeira medida a ser adotada pela organização?",
         "option_a": "Fornecer cinturões de segurança do tipo paraquedista a todos os envolvidos", "option_b": "Instalar redes de proteção coletiva ao redor do perímetro", "option_c": "Evitar o trabalho em altura, avaliando alternativas para executar a tarefa no nível inferior", "option_d": "Ministrar treinamento de reciclagem para a equipe", "correct_option": "C"},
        {"text": "Sempre que o trabalhador utilizar um talabarte de segurança para retenção de quedas conectado ao cinturão tipo paraquedista, a norma exige a utilização integrada de um componente específico para reduzir o impacto no corpo do trabalhador. Que componente é esse?",
         "option_a": "Conector do tipo mosquetão de rosca", "option_b": "Dispositivo absorvedor de energia", "option_c": "Dispositivo trava-quedas guiada", "option_d": "Protetor de corda em lona", "correct_option": "B"},
        {"text": "O treinamento periódico para os trabalhadores autorizados a realizar trabalho em altura deve ocorrer com qual periodicidade regular mínima?",
         "option_a": "A cada 1 ano (anual)", "option_b": "A cada 2 anos (bienal)", "option_c": "A cada 3 anos (trienal)", "option_d": "Somente quando houver mudança de empresa", "correct_option": "B"},
        {"text": "A Permissão de Trabalho (PT) emitida para a execução de uma determinada atividade em altura possui regras rígidas de controle. Qual das alternativas abaixo apresenta uma afirmação INCORRETA sobre a PT?",
         "option_a": "Deve ter validade limitada à duração da atividade, restrita ao turno ou jornada de trabalho", "option_b": "Deve ser aprovada e assinada pelo responsável pela autorização", "option_c": "Deve ficar permanentemente disponível e acessível no local de execução do trabalho", "option_d": "Pode ser utilizada por tempo indeterminado, desde que a equipe de trabalhadores permaneça rigorosamente a mesma", "correct_option": "D"},
        {"text": "O trabalhador tem o direito e o dever de interromper suas atividades em altura sempre que constatar uma situação de trabalho que apresente risco grave e iminente para sua vida ou de terceiros. Esse conceito é conhecido na segurança do trabalho como:",
         "option_a": "Direito de Recusa", "option_b": "Permissão Especial", "option_c": "Análise de Contingência", "option_d": "Autoinspeção Trabalhista", "correct_option": "A"},
    ],
    "NR-18 Segurança e saúde no trabalho na indústria da construção": [
        {"text": "Qual é o principal objetivo da Norma Regulamentadora nº 18 (NR-18)?",
         "option_a": "Garantir a produtividade e o prazo de entrega das obras de construção civil.", "option_b": "Estabelecer diretrizes de ordem administrativa, de planejamento e de organização para a prevenção de acidentes e doenças na construção.", "option_c": "Definir os impostos e taxas trabalhistas aplicáveis às empreiteiras.", "option_d": "Regulamentar apenas a fabricação de máquinas pesadas usadas em obras.", "correct_option": "B"},
        {"text": "Sobre o Programa de Gerenciamento de Riscos (PGR) no canteiro de obras, é correto afirmar que:",
         "option_a": "O PGR é opcional para empresas com menos de 20 trabalhadores.", "option_b": "Deve contemplar os riscos ocupacionais e suas respectivas medidas de prevenção na construção.", "option_c": "Substitui totalmente o uso de Equipamentos de Proteção Individual (EPIs).", "option_d": "Deve ser elaborado exclusivamente pelo Ministério do Trabalho.", "correct_option": "B"},
        {"text": "Em relação à proteção contra quedas em altura, a NR-18 determina que a instalação de proteção coletiva é obrigatória:",
         "option_a": "Apenas em obras públicas de grande porte.", "option_b": "Somente quando o trabalhador solicita formalmente ao encarregado.", "option_c": "Em áreas com risco de queda de trabalhadores ou projeção de materiais, projetada por profissional habilitado.", "option_d": "A partir de 10 metros de altura do solo.", "correct_option": "C"},
        {"text": "Quando os anteparos rígidos (guarda-corpo e rodapé) são utilizados como fechamento total do vão na periferia da laje, qual deve ser a altura mínima de proteção?",
         "option_a": "0,90 metro.", "option_b": "1,00 metro.", "option_c": "1,20 metro.", "option_d": "1,50 metro.", "correct_option": "C"},
        {"text": "De acordo com a NR-18, quem é o responsável por fornecer os Equipamentos de Proteção Individual (EPIs) adequados aos riscos e em perfeito estado de conservação?",
         "option_a": "O próprio trabalhador.", "option_b": "O sindicato da categoria.", "option_c": "O empregador, de forma gratuita.", "option_d": "O Ministério do Trabalho e Emprego.", "correct_option": "C"},
        {"text": "Sobre o uso de escadas de mão de uso coletivo na obra, a NR-18 estabelece que elas devem:",
         "option_a": "Ultrapassar em pelo menos 1,00 metro o piso superior ou ponto de apoio.", "option_b": "Ser construídas com sobras de madeira da obra sem lixamento.", "option_c": "Ter no máximo 10 metros de extensão.", "option_d": "Dispensar fixação nos pontos de apoio superiores e inferiores se forem pesadas.", "correct_option": "A"},
        {"text": "É expressamente proibido pela NR-18 o uso de quais tipos de andaimes na indústria da construção?",
         "option_a": "Andaimes suspensos mecânicos.", "option_b": "Andaimes apoiados sobre cavaletes com altura superior a 2,00 metros e largura inferior a 0,90 metro.", "option_c": "Andaimes fachadeiros de fabricação industrial.", "option_d": "Andaimes suspensos motorizados.", "correct_option": "B"},
    ],
    "NR-33 Segurança e saúde no trabalho em espaços confinados": [
        {"text": 'Para que um ambiente seja legalmente considerado um "Espaço Confinado", ele deve atender simultaneamente a quais requisitos?',
         "option_a": "Não ser projetado para ocupação humana contínua e possuir apenas uma entrada.", "option_b": "Não ser projetado para ocupação humana contínua, possuir meios limitados de entrada/saída e ter ou poder ter atmosfera perigosa.", "option_c": "Ter pouca iluminação, ser subterrâneo e apresentar ausência total de oxigênio.", "option_d": "Ser um local fechado com risco iminente de desabamento ou soterramento.", "correct_option": "B"},
        {"text": "Qual é a carga horária mínima exigida pela NR-33 para o treinamento inicial de um Supervisor de Entrada?",
         "option_a": "8 horas", "option_b": "16 horas", "option_c": "24 horas", "option_d": "40 horas", "correct_option": "D"},
        {"text": "A Permissão de Entrada e Trabalho (PET) é um documento essencial para qualquer atividade em espaço confinado. Quem é o responsável exclusivo por preencher e assinar a PET antes do início das atividades?",
         "option_a": "O Vigia", "option_b": "O Trabalhador Autorizado", "option_c": "O Supervisor de Entrada", "option_d": "O Técnico de Segurança do Trabalho terceirizado", "correct_option": "C"},
        {"text": "Durante a execução dos trabalhos, o Vigia desempenha um papel crítico de segurança. Assinale a alternativa que apresenta uma atitude PROIBIDA para o Vigia:",
         "option_a": "Manter a comunicação constante com os trabalhadores autorizados.", "option_b": "Operar os movimentadores de pessoas em caso de resgate.", "option_c": "Entrar no espaço confinado para auxiliar em uma tarefa rápida ou carregar uma ferramenta.", "option_d": "Ordenar o abandono do local caso note algum sinal de perigo.", "correct_option": "C"},
        {"text": "Uma atmosfera é considerada perigosa e IPVS (Imediatamente Perigosa à Vida ou à Saúde) quando apresenta, entre outros fatores, uma deficiência extrema de oxigênio. Qual é o percentual mínimo de oxigênio em volume que deve estar presente no ar para que o ambiente seja considerado seguro para entrada sem proteção respiratória especial?",
         "option_a": "15%", "option_b": "18%", "option_c": "20,9%", "option_d": "23,5%", "correct_option": "C"},
        {"text": "O monitoramento e a avaliação da atmosfera interna do espaço confinado devem ser realizados em qual momento?",
         "option_a": "Apenas uma vez na semana antes de iniciar a campanha de manutenção.", "option_b": "Antes da entrada dos trabalhadores, de forma contínua durante o trabalho, e após as pausas.", "option_c": "Somente se os trabalhadores relatarem mal-estar ou tontura.", "option_d": "Exclusivamente no momento da abertura do bueiro ou do tanque.", "correct_option": "B"},
        {"text": "Caso um trabalhador note um risco grave e iminente dentro do espaço confinado, qual direito e dever ele deve exercer de acordo com as normas de segurança brasileiras?",
         "option_a": "Abandonar o local imediatamente em silêncio para não alarmar a equipe.", "option_b": "Continuar a tarefa até o final do turno e relatar o problema por escrito no dia seguinte.", "option_c": "Exercer o direito de recusa, interromper as atividades e comunicar imediatamente o fato ao Vigia ou Supervisor.", "option_d": "Tentar resolver o vazamento ou problema sozinho antes de avisar a chefia.", "correct_option": "C"},
    ],
    "NR-17 Ergonimia": [
        {"text": "Qual é o principal objetivo da NR-17?",
         "option_a": "Estabelecer regras para prevenção e combate a incêndios.", "option_b": "Adaptar as condições de trabalho às características psicofisiológicas dos trabalhadores.", "option_c": "Definir os equipamentos de proteção individual obrigatórios.", "option_d": "Regulamentar exclusivamente o trabalho em máquinas.", "correct_option": "B"},
        {"text": "O que é ergonomia no ambiente de trabalho?",
         "option_a": "Conjunto de medidas voltadas exclusivamente à organização financeira da empresa.", "option_b": "Estudo e adaptação das condições de trabalho para proporcionar segurança, conforto, saúde e desempenho adequado ao trabalhador.", "option_c": "Utilização obrigatória de equipamentos de proteção individual.", "option_d": "Apenas a correção da postura do trabalhador.", "correct_option": "B"},
        {"text": "Qual das situações abaixo pode representar um risco ergonômico?",
         "option_a": "Postura inadequada durante a execução das atividades.", "option_b": "Uso correto do uniforme.", "option_c": "Organização adequada do ambiente.", "option_d": "Iluminação adequada do posto de trabalho.", "correct_option": "A"},
        {"text": "Em relação ao mobiliário dos postos de trabalho, é importante:",
         "option_a": "Utilizar o mesmo ajuste para todos os trabalhadores.", "option_b": "Adaptar o mobiliário às características do trabalhador e às exigências da atividade.", "option_c": "Evitar qualquer tipo de regulagem.", "option_d": "Priorizar somente a aparência do mobiliário.", "correct_option": "B"},
        {"text": "Durante atividades que exigem permanência prolongada em determinada postura, uma medida ergonômica adequada é:",
         "option_a": "Manter a posição durante toda a jornada.", "option_b": "Ignorar sinais de desconforto.", "option_c": "Adotar medidas que favoreçam a alternância postural e a redução de sobrecargas.", "option_d": "Aumentar a velocidade de execução do trabalho.", "correct_option": "C"},
        {"text": "O levantamento, transporte e descarga individual de cargas devem considerar:",
         "option_a": "Somente o peso da carga.", "option_b": "Apenas a idade do trabalhador.", "option_c": "As características da carga, do trabalhador e das condições de execução da atividade.", "option_d": "Somente o tempo necessário para realizar a tarefa.", "correct_option": "C"},
        {"text": "Qual atitude contribui para a prevenção de problemas ergonômicos?",
         "option_a": "Ignorar dores e desconfortos durante o trabalho.", "option_b": "Ajustar o posto de trabalho de acordo com as características da atividade e do trabalhador.", "option_c": "Trabalhar sempre na mesma postura.", "option_d": "Aumentar o ritmo de trabalho quando houver desconforto.", "correct_option": "B"},
        {"text": "A organização do trabalho pode influenciar a saúde do trabalhador?",
         "option_a": "Não, somente o mobiliário pode causar problemas ergonômicos.", "option_b": "Sim. Aspectos como ritmo, exigências, duração e organização das atividades podem influenciar a saúde e o conforto.", "option_c": "Não, desde que o trabalhador utilize uniforme.", "option_d": "Somente em atividades realizadas ao ar livre.", "correct_option": "B"},
        {"text": "Ao perceber desconforto ou dificuldade relacionada às condições ergonômicas do trabalho, o trabalhador deve:",
         "option_a": "Ignorar o problema até o final da jornada.", "option_b": "Continuar trabalhando sem comunicar ninguém.", "option_c": "Comunicar a situação ao responsável conforme os procedimentos da empresa, contribuindo para a identificação e correção do problema.", "option_d": "Fazer alterações improvisadas sem comunicar a empresa.", "correct_option": "C"},
        {"text": "Qual das alternativas representa uma boa prática de ergonomia?",
         "option_a": "Ajustar cadeira, mesa, equipamentos e demais elementos do posto conforme a atividade e o trabalhador.", "option_b": "Utilizar mobiliário sem regulagem independentemente da necessidade.", "option_c": "Permanecer em postura desconfortável para aumentar a produtividade.", "option_d": "Desconsiderar pausas e alternância de atividades quando houver desconforto.", "correct_option": "A"},
    ],
    "NR-20 Inflamáveis": [
        {"text": "Qual é o principal objetivo da NR-20?",
         "option_a": "Estabelecer regras para trabalhos em altura.", "option_b": "Estabelecer requisitos para a segurança e saúde no trabalho com inflamáveis e combustíveis.", "option_c": "Regulamentar exclusivamente o uso de equipamentos de proteção individual.", "option_d": "Estabelecer regras para instalações elétricas.", "correct_option": "B"},
        {"text": "O que é considerado um dos principais riscos relacionados aos inflamáveis?",
         "option_a": "Incêndio e explosão.", "option_b": "Apenas ruído.", "option_c": "Apenas iluminação inadequada.", "option_d": "Somente risco ergonômico.", "correct_option": "A"},
        {"text": "Qual situação pode representar uma fonte de ignição?",
         "option_a": "Faísca elétrica.", "option_b": "Água limpa.", "option_c": "Piso seco.", "option_d": "Ventilação natural.", "correct_option": "A"},
        {"text": "Ao identificar um vazamento de produto inflamável, o trabalhador deve:",
         "option_a": "Ignorar o vazamento se for pequeno.", "option_b": "Tentar resolver sozinho, independentemente do procedimento estabelecido.", "option_c": "Comunicar imediatamente a situação e seguir os procedimentos de emergência da instalação.", "option_d": "Acender uma chama para identificar a origem do vazamento.", "correct_option": "C"},
        {"text": "A análise de riscos tem como finalidade principal:",
         "option_a": "Identificar perigos, avaliar riscos e definir medidas de prevenção e controle.", "option_b": "Aumentar a velocidade da produção.", "option_c": "Substituir todos os treinamentos.", "option_d": "Eliminar a necessidade de procedimentos operacionais.", "correct_option": "A"},
        {"text": "Durante uma situação de emergência envolvendo inflamáveis, o trabalhador deve:",
         "option_a": "Agir de acordo com os procedimentos e o plano de resposta a emergências da instalação.", "option_b": "Permanecer próximo ao local para observar o ocorrido.", "option_c": "Utilizar qualquer equipamento disponível, mesmo sem treinamento.", "option_d": "Retornar ao local sem autorização.", "correct_option": "A"},
        {"text": "Por que é importante controlar as fontes de ignição em áreas com inflamáveis?",
         "option_a": "Para reduzir o risco de incêndios e explosões.", "option_b": "Para aumentar a temperatura do ambiente.", "option_c": "Para melhorar a iluminação.", "option_d": "Para reduzir o consumo de água.", "correct_option": "A"},
        {"text": "Qual das alternativas apresenta uma atitude segura durante o manuseio de inflamáveis?",
         "option_a": "Fumar próximo ao produto.", "option_b": "Utilizar equipamentos e procedimentos adequados e seguir as orientações de segurança.", "option_c": "Improvisar ferramentas quando necessário.", "option_d": "Ignorar pequenos vazamentos.", "correct_option": "B"},
        {"text": "Em caso de incêndio envolvendo inflamáveis, o trabalhador deve:",
         "option_a": "Combater o incêndio sem treinamento, independentemente da situação.", "option_b": "Seguir o plano de emergência e utilizar os recursos previstos para sua função e treinamento.", "option_c": "Aproximar-se do fogo para verificar sua origem.", "option_d": "Retirar equipamentos sem autorização.", "correct_option": "B"},
        {"text": "A capacitação prevista na NR-20 deve considerar, entre outros fatores:",
         "option_a": "A atividade exercida e a classe da instalação.", "option_b": "Apenas a idade do trabalhador.", "option_c": "Somente o tempo de empresa.", "option_d": "Apenas o cargo administrativo.", "correct_option": "A"},
    ],
    "NR-26 Sinalização de segurança": [
        {"text": "Qual é o principal objetivo da NR-26?",
         "option_a": "Estabelecer regras para trabalho em altura.", "option_b": "Estabelecer medidas relacionadas à sinalização e identificação de segurança nos locais de trabalho.", "option_c": "Regulamentar exclusivamente o uso de EPIs.", "option_d": "Estabelecer normas para prevenção de incêndios.", "correct_option": "B"},
        {"text": "As cores utilizadas nos locais de trabalho têm como finalidade:",
         "option_a": "Apenas deixar o ambiente mais organizado.", "option_b": "Identificar os funcionários de cada setor.", "option_c": "Indicar e advertir sobre perigos e riscos existentes.", "option_d": "Substituir todos os equipamentos de proteção.", "correct_option": "C"},
        {"text": "A utilização de cores na segurança do trabalho:",
         "option_a": "Dispensa outras medidas de prevenção.", "option_b": "Deve substituir o uso de placas de segurança.", "option_c": "Não dispensa outras formas de prevenção de acidentes.", "option_d": "É obrigatória em todos os objetos existentes na empresa.", "correct_option": "C"},
        {"text": "Por que o uso de cores deve ser reduzido ao necessário?",
         "option_a": "Para economizar tinta.", "option_b": "Para evitar distração, confusão e fadiga ao trabalhador.", "option_c": "Para facilitar a limpeza.", "option_d": "Para diminuir os custos da empresa.", "correct_option": "B"},
        {"text": "A NR-26 estabelece que os produtos químicos utilizados no local de trabalho devem ser classificados considerando:",
         "option_a": "Apenas o preço do produto.", "option_b": "Os perigos para a segurança e a saúde dos trabalhadores, conforme os critérios do GHS.", "option_c": "Somente a cor da embalagem.", "option_d": "Apenas o fabricante do produto.", "correct_option": "B"},
        {"text": "O que significa GHS?",
         "option_a": "Guia de Higiene e Segurança.", "option_b": "Gestão de Higiene Sanitária.", "option_c": "Sistema Globalmente Harmonizado de Classificação e Rotulagem de Produtos Químicos.", "option_d": "Grupo de Higiene e Saúde.", "correct_option": "C"},
        {"text": "Qual das opções apresenta elementos previstos na rotulagem preventiva de um produto químico perigoso?",
         "option_a": "Nome do funcionário, setor e horário de trabalho.", "option_b": "Identificação do produto, pictogramas de perigo, palavra de advertência e frases de perigo e precaução.", "option_c": "Apenas nome comercial e preço.", "option_d": "Somente código de barras.", "correct_option": "B"},
        {"text": "Ao encontrar um produto químico sem identificação adequada, o trabalhador deve:",
         "option_a": "Utilizá-lo normalmente, desde que conheça sua aparência.", "option_b": "Misturá-lo com outro produto para descobrir sua composição.", "option_c": "Seguir os procedimentos de segurança da empresa e não utilizar o produto sem identificação adequada.", "option_d": "Transferi-lo para outra embalagem sem identificação.", "correct_option": "C"},
        {"text": "Os pictogramas presentes nos rótulos de produtos químicos têm a função de:",
         "option_a": "Informar o preço do produto.", "option_b": "Representar graficamente determinados perigos associados ao produto.", "option_c": "Identificar o setor responsável pela compra.", "option_d": "Informar a quantidade disponível no estoque.", "correct_option": "B"},
        {"text": "O que deve ser feito antes de utilizar um produto químico desconhecido?",
         "option_a": "Cheirar o produto para identificar sua composição.", "option_b": "Consultar as informações de segurança disponíveis e seguir os procedimentos estabelecidos.", "option_c": "Misturá-lo com água.", "option_d": "Perguntar a outro trabalhador e utilizar imediatamente.", "correct_option": "B"},
    ],
}


def _seed_nr_quiz_questions(db):
    """Perguntas dos questionários de NR que a Iza mandou em .docx —
    idempotente por texto da pergunta (não recria se já existe), então é
    seguro rodar em todo boot. Cada pergunta cai no primeiro módulo do
    curso (aqui todo curso é vídeo único) com timestamp=0: sem saber a
    duração real de cada vídeo, 0 garante que a pergunta sempre aparece
    logo no início em vez de arriscar um timestamp maior que a duração,
    o que deixaria o módulo impossível de concluir (a pergunta nunca
    apareceria pro aluno)."""
    import models
    for course_title, questions in _NR_QUIZ_DATA.items():
        course = db.query(models.Course).filter(models.Course.title == course_title).first()
        if not course:
            continue  # curso ainda não existe nesse ambiente
        module = db.query(models.Module).filter(models.Module.course_id == course.id).order_by(models.Module.order).first()
        if not module:
            continue  # curso sem módulo/vídeo ainda — nada pra anexar a pergunta
        existing_texts = {row.text for row in db.query(models.Question.text).filter(models.Question.module_id == module.id).all()}
        for q in questions:
            if q["text"] in existing_texts:
                continue
            db.add(models.Question(
                module_id=module.id,
                text=q["text"],
                option_a=q["option_a"],
                option_b=q["option_b"],
                option_c=q["option_c"],
                option_d=q["option_d"],
                correct_option=q["correct_option"],
                timestamp=0,
            ))
