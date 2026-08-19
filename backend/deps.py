"""Dependências e helpers compartilhados entre os routers (backend/routers/*)."""
import datetime
import mimetypes
import os
import re
import uuid
from typing import List, Optional

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

import models
import database
import auth

# ---------------- Sessão de banco ----------------
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- Autenticação / autorização ----------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        from jose import jwt
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def authorize(allowed_roles: List[str]):
    def decorator(current_user: models.User = Depends(get_current_user)):
        # admin sempre acessa rotas de papel mais baixo (ex.: lideranca);
        # super_admin (enxerga todas as empresas) tem o mesmo bypass.
        if current_user.role in ("admin", "super_admin"):
            return current_user
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Você não tem permissão para realizar esta ação.")
        return current_user
    return decorator

def require_enrolled(db: Session, user_id: int, course_id: int):
    """Fronteira de autorização de quem pode ver/responder quiz e progresso
    de um módulo: estar matriculado no curso. Sem isso, qualquer usuário
    autenticado conseguia ver pergunta e completar módulo de curso alheio
    (inclusive de outra empresa) só sabendo o ID."""
    enrolled = db.query(models.Enrollment).filter(
        models.Enrollment.user_id == user_id,
        models.Enrollment.course_id == course_id
    ).first()
    if not enrolled:
        raise HTTPException(status_code=403, detail="Você não está matriculado neste curso.")

def require_enrolled_in_module(db: Session, user_id: int, module_id: int):
    module = db.query(models.Module).filter(models.Module.id == module_id).first()
    if not module or not module.course_id:
        raise HTTPException(status_code=404, detail="Módulo não encontrado")
    require_enrolled(db, user_id, module.course_id)

# ---------------- Multi-empresa ----------------
def resolve_company_id(current_user: models.User, requested_company_id: Optional[int] = None) -> int:
    """admin/lideranca sempre usam a própria empresa (ignora qualquer valor
    enviado); super_admin não tem empresa própria, então precisa informar
    qual — sem isso não daria pra saber onde criar o recurso."""
    if current_user.role == "super_admin":
        if not requested_company_id:
            raise HTTPException(status_code=400, detail="Informe a empresa (company_id).")
        return requested_company_id
    return current_user.company_id

def check_same_company(current_user: models.User, entity_company_id: int, what: str = "recurso"):
    if current_user.role != "super_admin" and entity_company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail=f"Este {what} não pertence à sua empresa.")

# ---------------- Constantes de domínio ----------------
UPLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "uploads"))
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOADS_DIR, "temp"), exist_ok=True)

# Department é obrigatório em User; usado quando um fluxo de criação
# (convite do admin, adição pela liderança) não coleta esse dado.
DEFAULT_DEPARTMENT = "Não informado"

def iso_utc(dt: Optional[datetime.datetime]) -> Optional[str]:
    """Serializa um datetime ingênuo (armazenado em UTC) com o sufixo 'Z',
    para que o JavaScript do frontend interprete corretamente como UTC em
    vez de horário local do navegador."""
    if dt is None:
        return None
    return dt.replace(tzinfo=datetime.timezone.utc).isoformat()

def _check_and_issue_course_certificate(db: Session, user_id: int, course_id: int):
    """Confere se todos os módulos do curso estão concluídos e, se sim,
    emite o certificado (um por usuário+curso) — chamado automaticamente
    por _mark_module_complete, nunca precisa ser disparado manualmente pelo
    frontend. Devolve o Certificate se emitiu/já existia, ou None se ainda
    faltam módulos."""
    modules = db.query(models.Module).filter(models.Module.course_id == course_id).all()
    if not modules:
        return None
    module_ids = [m.id for m in modules]
    done_count = db.query(models.ModuleProgress).filter(
        models.ModuleProgress.user_id == user_id,
        models.ModuleProgress.module_id.in_(module_ids),
        models.ModuleProgress.is_completed == True
    ).count()
    if done_count < len(modules):
        return None

    existing = db.query(models.Certificate).filter(
        models.Certificate.user_id == user_id,
        models.Certificate.course_id == course_id
    ).first()
    if existing:
        return existing

    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    from dateutil.relativedelta import relativedelta
    months = (course.validity_months if course and course.validity_months else None) or int(os.getenv("CERT_DEFAULT_VALIDITY_MONTHS", "12"))
    cert = models.Certificate(
        user_id=user_id,
        course_id=course_id,
        file_url="",
        expires_at=datetime.datetime.utcnow() + relativedelta(months=months)
    )
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return cert

def _mark_module_complete(db: Session, user_id: int, module_id: int, score: float):
    """Único ponto que grava conclusão de módulo — score sempre calculado
    pelo servidor (nunca recebido pronto do cliente). Reaproveitado pelo
    router de progresso (módulo sem prova) e pelo de quiz (prova corrigida).
    Ao final, confere automaticamente se isso completou o curso inteiro e
    emite o certificado — o frontend não precisa chamar isso à parte."""
    progress = db.query(models.ModuleProgress).filter(
        models.ModuleProgress.module_id == module_id,
        models.ModuleProgress.user_id == user_id
    ).first()
    if not progress:
        progress = models.ModuleProgress(user_id=user_id, module_id=module_id)
        db.add(progress)
    progress.is_completed = True
    progress.score_final = score
    progress.completed_at = datetime.datetime.utcnow()
    db.commit()

    module = db.query(models.Module).filter(models.Module.id == module_id).first()
    certificate_issued = False
    if module and module.course_id:
        was_new = db.query(models.Certificate).filter(
            models.Certificate.user_id == user_id,
            models.Certificate.course_id == module.course_id
        ).first() is None
        cert = _check_and_issue_course_certificate(db, user_id, module.course_id)
        certificate_issued = bool(cert) and was_new
    return certificate_issued

# ---------------- Upload: nome de arquivo seguro + limites ----------------
# .mkv fora de propósito: mesmo com upload aceito, esse container não toca
# inline em Chrome/Safari (que não têm suporte nativo a Matroska no <video>),
# então o vídeo "sobe certinho" mas nunca funciona pra quem assiste. .mov e
# .webm ficam porque tocam na maioria dos casos reais (H.264/AAC ou VP8/VP9).
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".webm"}
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}

# Content-Type explícito por extensão — não confia no mimetypes.guess_type()
# do SO, que varia entre Windows (dev) e a imagem Debian slim do container
# de produção e pode faltar mapeamento pra algumas extensões de vídeo.
for _ext, _mime in {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}.items():
    mimetypes.add_type(_mime, _ext)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "2000")) * 1024 * 1024
_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")

def sanitize_filename(name: str, allowed_ext: set) -> str:
    """Nunca usar o nome de arquivo enviado pelo cliente direto num
    os.path.join — ele pode conter '../', separadores de caminho, etc.
    Extrai só o basename, remove caracteres fora de um allowlist e valida
    a extensão contra a lista permitida para o tipo de upload. Determinístico
    (mesma entrada → mesma saída) — o upload em chunks precisa bater o mesmo
    nome sanitizado entre init/chunk/create_module; a aleatoriedade vem do
    upload_id (uuid gerado uma vez em init_upload), não deste helper."""
    base = os.path.basename((name or "").strip())
    base = _SAFE_CHARS.sub("_", base)
    ext = os.path.splitext(base)[1].lower()
    if not base or ext not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"Tipo de arquivo não permitido. Use: {', '.join(sorted(allowed_ext))}")
    return base

def safe_filename(name: str, allowed_ext: set) -> str:
    """Para uploads de arquivo único (uma requisição só): sanitiza e prefixa
    com um uuid novo, garantindo nome final imprevisível e sem colisão."""
    return f"{uuid.uuid4()}_{sanitize_filename(name, allowed_ext)}"

def check_upload_size(size_bytes: int):
    if size_bytes > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Arquivo excede o limite de {MAX_UPLOAD_BYTES // (1024*1024)}MB.")
