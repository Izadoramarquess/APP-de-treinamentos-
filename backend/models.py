from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, Float, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
import datetime
from database import Base
from pydantic import BaseModel
from typing import List, Optional

class Company(Base):
    """Empresa (tenant) — GeoTrilha passou a atender mais de uma empresa a
    partir do mesmo deploy/banco. Usuário/Equipe/Curso pertencem sempre a
    uma empresa; só o papel 'super_admin' não pertence a nenhuma (enxerga
    todas). logo_url é usado automaticamente na geração do certificado."""
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    logo_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    # Nome não é mais globalmente único (duas empresas podem ter uma
    # "Operações" cada) — unicidade passa a ser aplicada na aplicação,
    # escopada por (company_id, name).
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    members = relationship("User", back_populates="team")

class TeamLeader(Base):
    """Quem lidera qual equipe — separado de User.team_id (que é só a
    equipe-base/pertencimento da pessoa) porque um líder pode liderar mais
    de uma equipe ao mesmo tempo, mas só pertence (team_id) a uma."""
    __tablename__ = "team_leaders"
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint('team_id', 'user_id'),)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="usuario") # 'super_admin', 'admin', 'lideranca', 'usuario'
    status = Column(String, default="pending") # 'pendente', 'ativo', 'convite_pendente', 'convite_expirado'
    department = Column(String, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    # Nulo só para 'super_admin' — todo outro papel pertence a uma empresa.
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    invite_token = Column(String, nullable=True)
    invite_expires_at = Column(DateTime, nullable=True)
    invited_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    must_change_password = Column(Boolean, default=False)

    team = relationship("Team", back_populates="members")
    company = relationship("Company", foreign_keys=[company_id])
    enrollments = relationship("Enrollment", back_populates="user")
    certificates = relationship("Certificate", back_populates="user")
    course_progress = relationship("ModuleProgress", back_populates="user")
    invited_by = relationship("User", remote_side=[id])

class Course(Base):
    """Nível de topo do catálogo (antes havia uma LearningPath/"Trilha" por
    cima, removida por ser burocracia demais para o fluxo de subir conteúdo).
    Absorve o que antes vivia em LearningPath (is_standard_training) e em
    Module (validity_months, certificate_template_url) — o certificado
    agora é um por curso, não um por módulo."""
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    order = Column(Integer, default=1)
    title = Column(String, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_standard_training = Column(Boolean, default=False)
    validity_months = Column(Integer, nullable=True)
    certificate_template_url = Column(String, nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    modules = relationship("Module", back_populates="course", order_by="Module.order")
    enrollments = relationship("Enrollment", back_populates="course")
    certificates = relationship("Certificate", back_populates="course")
    company = relationship("Company", foreign_keys=[company_id])

class Module(Base):
    __tablename__ = "modules"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True) # Temporarily nullable for migration
    order = Column(Integer, default=1)
    title = Column(String, index=True)
    description = Column(Text)
    video_url = Column(String, nullable=True)
    thumbnail_url = Column(String, nullable=True)

    course = relationship("Course", back_populates="modules")
    materials = relationship("Material", back_populates="module")
    questions = relationship("Question", back_populates="module")
    progress = relationship("ModuleProgress", back_populates="module")

class Material(Base):
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("modules.id"))
    title = Column(String)
    file_url = Column(String)
    
    module = relationship("Module", back_populates="materials")

class Question(Base):
    """Pergunta inline (module_id preenchido, aparece num momento do vídeo)
    OU pergunta de prova final (course_id preenchido, module_id nulo — a
    prova cobre o curso inteiro, não um vídeo específico, e só fica
    disponível depois que todos os módulos do curso são concluídos)."""
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    text = Column(Text)
    option_a = Column(String)
    option_b = Column(String)
    option_c = Column(String)
    option_d = Column(String)
    correct_option = Column(String)
    is_final_exam = Column(Boolean, default=False)
    timestamp = Column(Float, nullable=True)

    module = relationship("Module", back_populates="questions")
    course = relationship("Course", foreign_keys=[course_id])

class QuestionAttempt(Base):
    """Registra se o usuário já respondeu certo uma pergunta — usado pra
    exigir, no servidor, que toda pergunta inline do vídeo tenha sido
    respondida corretamente antes de concluir o módulo (sem isso, dava pra
    arrastar a barra de progresso do vídeo e pular a pergunta sem
    responder, já que a validação só existia no player, no navegador)."""
    __tablename__ = "question_attempts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    is_correct = Column(Boolean, default=False)
    answered_at = Column(DateTime, default=datetime.datetime.utcnow)

class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    enrolled_at = Column(DateTime, default=datetime.datetime.utcnow)
    # Marca se já mandamos o lembrete de "curso parado" pra essa matrícula —
    # sem isso o job diário mandaria o mesmo e-mail toda vez que rodasse.
    reminder_sent = Column(Boolean, default=False)

    user = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")

class ModuleProgress(Base):
    __tablename__ = "module_progress"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    module_id = Column(Integer, ForeignKey("modules.id"))
    is_completed = Column(Boolean, default=False)
    score_final = Column(Float, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="course_progress")
    module = relationship("Module", back_populates="progress")

class Certificate(Base):
    """Um certificado por (usuário, curso) — emitido automaticamente quando
    todos os módulos do curso são concluídos (ver deps._check_and_issue_course_certificate)."""
    __tablename__ = "certificates"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    file_url = Column(String)
    issued_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    # Idem — evita reenviar o aviso de vencimento todo dia depois que já
    # entrou na janela de "vence em breve" uma vez.
    expiry_reminder_sent = Column(Boolean, default=False)

    user = relationship("User", back_populates="certificates")
    course = relationship("Course", back_populates="certificates")

class EmailLog(Base):
    __tablename__ = "email_logs"
    id = Column(Integer, primary_key=True, index=True)
    recipient_email = Column(String, index=True)
    sender_email = Column(String, default="esg@geobiogas.tech")
    cc_email = Column(String, default="izadora.silva@geobiogas.tech")
    email_type = Column(String)
    status = Column(String) # 'SUCESSO', 'ERRO'
    sent_at = Column(DateTime, default=datetime.datetime.utcnow)
    error_message = Column(Text, nullable=True)

# --- Pydantic Schemas ---

class MaterialSchema(BaseModel):
    id: int
    title: str
    file_url: str
    class Config: from_attributes = True

# Schema completo, COM o gabarito — só para respostas admin-only (ex: ao
# cadastrar uma pergunta). Nunca usar como response_model de algo que um
# aluno possa chamar antes de responder.
class QuestionSchema(BaseModel):
    id: int
    module_id: Optional[int] = None
    course_id: Optional[int] = None
    text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    is_final_exam: bool
    timestamp: Optional[float] = None
    class Config: from_attributes = True

# Schema público — sem correct_option. Usado em tudo que um aluno pode ver
# antes de responder (embutido em ModuleSchema, e no GET de perguntas).
class QuestionPublicSchema(BaseModel):
    id: int
    text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    is_final_exam: bool
    timestamp: Optional[float] = None
    class Config: from_attributes = True

class ModuleSchema(BaseModel):
    id: int
    course_id: Optional[int]
    order: int
    title: str
    description: str
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    materials: List[MaterialSchema] = []
    questions: List[QuestionPublicSchema] = []
    class Config: from_attributes = True

class CourseSchema(BaseModel):
    id: int
    order: int
    title: str
    description: str
    created_at: datetime.datetime
    is_standard_training: bool = False
    validity_months: Optional[int] = None
    certificate_template_url: Optional[str] = None
    company_id: int
    modules: List[ModuleSchema] = []
    class Config: from_attributes = True

class UserSchema(BaseModel):
    id: int
    username: str
    email: str
    role: str
    status: str
    department: str
    team_id: int
    company_id: Optional[int] = None
    invite_expires_at: Optional[datetime.datetime] = None
    invited_by_id: Optional[int] = None
    must_change_password: bool = False
    # Equipes que essa pessoa lidera (só relevante se role=="lideranca") —
    # preenchido à parte, não é uma coluna real (ver deps.get_led_team_ids).
    led_team_ids: List[int] = []
    class Config: from_attributes = True

class CompanySchema(BaseModel):
    id: int
    name: str
    logo_url: Optional[str] = None
    created_at: datetime.datetime
    class Config: from_attributes = True

class EmailLogSchema(BaseModel):
    id: int
    recipient_email: str
    sender_email: str
    cc_email: str
    email_type: str
    status: str
    sent_at: datetime.datetime
    error_message: Optional[str] = None
    class Config: from_attributes = True

class EnrollmentSchema(BaseModel):
    id: int
    user_id: int
    course_id: int
    enrolled_at: datetime.datetime
    class Config: from_attributes = True

class TeamLeaderInfo(BaseModel):
    id: int
    username: str
    class Config: from_attributes = True

class TeamSchema(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    # Na prática quase sempre int (equipe pertence a uma empresa) — mas o
    # super_admin (sem empresa própria) também precisa de um team_id não
    # nulo em User, e a "Sem Equipe" placeholder dele fica sem company_id.
    company_id: Optional[int] = None
    members: List[UserSchema] = []
    # Quem lidera essa equipe — não é o mesmo que "membro com role
    # lideranca" (um líder pode liderar uma equipe da qual não é
    # membro-base). Ver deps.get_led_team_ids / TeamLeader.
    leaders: List[TeamLeaderInfo] = []
    class Config: from_attributes = True
