from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, Float, DateTime
from sqlalchemy.orm import relationship
import datetime
from database import Base
from pydantic import BaseModel
from typing import List, Optional

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)

    members = relationship("User", back_populates="team")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="usuario") # 'admin', 'lideranca', 'usuario'
    status = Column(String, default="pending") # 'pendente', 'ativo', 'convite_pendente', 'convite_expirado'
    department = Column(String, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    invite_token = Column(String, nullable=True)
    invite_expires_at = Column(DateTime, nullable=True)
    invited_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    must_change_password = Column(Boolean, default=False)

    team = relationship("Team", back_populates="members")
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

    modules = relationship("Module", back_populates="course", order_by="Module.order")
    enrollments = relationship("Enrollment", back_populates="course")
    certificates = relationship("Certificate", back_populates="course")

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
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("modules.id"))
    text = Column(Text)
    option_a = Column(String)
    option_b = Column(String)
    option_c = Column(String)
    option_d = Column(String)
    correct_option = Column(String)
    is_final_exam = Column(Boolean, default=False)
    timestamp = Column(Float, nullable=True)
    
    module = relationship("Module", back_populates="questions")

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
    invite_expires_at: Optional[datetime.datetime] = None
    invited_by_id: Optional[int] = None
    must_change_password: bool = False
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

class TeamSchema(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    members: List[UserSchema] = []
    class Config: from_attributes = True
