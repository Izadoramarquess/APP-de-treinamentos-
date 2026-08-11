"""Progresso do aluno: conclusão de módulo, trilhas matriculadas, certificados."""
import datetime
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
from deps import get_db, get_current_user, authorize, iso_utc, _mark_module_complete

router = APIRouter()

# ---------------- Progress Tracking ----------------
@router.post("/modules/{module_id}/complete")
def complete_module(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Módulos com prova final só podem ser concluídos via /modules/{id}/exam-submit,
    # que corrige as respostas no servidor. Isso fecha o atalho de marcar
    # "concluído" direto sem nunca ter respondido a prova.
    has_final_exam = db.query(models.Question).filter(
        models.Question.module_id == module_id,
        models.Question.is_final_exam == True
    ).first() is not None
    if has_final_exam:
        raise HTTPException(status_code=400, detail="Este módulo tem prova final — conclua respondendo a prova.")
    # Sem prova (só vídeo): não há nota a apurar, então o score é fixo — nunca vindo do cliente.
    _mark_module_complete(db, current_user.id, module_id, 100.0)
    return {"message": "Módulo concluído!", "completed": True}

@router.get("/paths/{path_id}/progress")
def get_path_progress(
    path_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    path = db.query(models.LearningPath).filter(models.LearningPath.id == path_id).first()
    if not path: raise HTTPException(404, "Trilha não encontrada")
    total_modules = 0
    completed_modules = 0
    for course in path.courses:
        for module in course.modules:
            total_modules += 1
            progress = db.query(models.ModuleProgress).filter(
                models.ModuleProgress.module_id == module.id,
                models.ModuleProgress.user_id == current_user.id,
                models.ModuleProgress.is_completed == True
            ).first()
            if progress: completed_modules += 1
    pct = round((completed_modules / total_modules * 100) if total_modules > 0 else 0)
    return {"total": total_modules, "completed": completed_modules, "percent": pct}

@router.get("/courses/{course_id}/progress")
def get_course_progress(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    progresses = db.query(models.ModuleProgress).join(models.Module).filter(
        models.Module.course_id == course_id,
        models.ModuleProgress.user_id == current_user.id
    ).all()
    return [{"module_id": p.module_id, "completed": p.is_completed, "score": p.score_final} for p in progresses]

@router.get("/my-paths")
def get_my_paths(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    enrollments = db.query(models.Enrollment).filter(
        models.Enrollment.user_id == current_user.id
    ).all()
    path_ids = [e.path_id for e in enrollments]
    if not path_ids:
        return []
    paths = db.query(models.LearningPath).filter(
        models.LearningPath.id.in_(path_ids)
    ).all()
    return paths

@router.get("/team/progress")
def get_team_progress(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin", "lideranca"]))
):
    if current_user.role == "admin":
        members = db.query(models.User).filter(
            models.User.status == "ativo"
        ).all()
    else:
        members = db.query(models.User).filter(
            models.User.team_id == current_user.team_id,
            models.User.status == "ativo"
        ).all()

    result = []
    for member in members:
        total = db.query(models.ModuleProgress).filter(
            models.ModuleProgress.user_id == member.id
        ).count()
        done = db.query(models.ModuleProgress).filter(
            models.ModuleProgress.user_id == member.id,
            models.ModuleProgress.is_completed == True
        ).count()
        enrollments = db.query(models.Enrollment).filter(
            models.Enrollment.user_id == member.id
        ).count()
        result.append({
            "user_id": member.id,
            "username": member.username,
            "email": member.email,
            "role": member.role,
            "enrollments": enrollments,
            "modules_total": total,
            "modules_done": done,
            "percent": round((done / total * 100) if total > 0 else 0)
        })
    return result

@router.post("/modules/{module_id}/certificate")
def issue_certificate(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Verificar se o módulo foi concluído
    progress = db.query(models.ModuleProgress).filter(
        models.ModuleProgress.module_id == module_id,
        models.ModuleProgress.user_id == current_user.id,
        models.ModuleProgress.is_completed == True
    ).first()
    if not progress:
        raise HTTPException(400, "Módulo não concluído.")

    # Verificar se já tem certificado
    existing = db.query(models.Certificate).filter(
        models.Certificate.module_id == module_id,
        models.Certificate.user_id == current_user.id
    ).first()
    if existing:
        return {"message": "Certificado já emitido.", "certificate_id": existing.id, "issued_at": iso_utc(existing.issued_at), "expires_at": iso_utc(existing.expires_at)}

    # Certificado sempre tem validade: usa a do módulo, ou um padrão configurável se o módulo não definir uma.
    module = db.query(models.Module).filter(models.Module.id == module_id).first()
    from dateutil.relativedelta import relativedelta
    months = (module.validity_months if module and module.validity_months else None) or int(os.getenv("CERT_DEFAULT_VALIDITY_MONTHS", "12"))
    expires_at = datetime.datetime.utcnow() + relativedelta(months=months)

    cert = models.Certificate(
        user_id=current_user.id,
        module_id=module_id,
        file_url="",
        expires_at=expires_at
    )
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return {"message": "Certificado emitido!", "certificate_id": cert.id, "issued_at": iso_utc(cert.issued_at), "expires_at": iso_utc(cert.expires_at)}

@router.get("/my-certificates")
def get_my_certificates(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    certs = db.query(models.Certificate).filter(
        models.Certificate.user_id == current_user.id
    ).all()
    result = []
    for c in certs:
        module = db.query(models.Module).filter(models.Module.id == c.module_id).first()
        result.append({
            "certificate_id": c.id,
            "module_id": c.module_id,
            "module_title": module.title if module else "—",
            "issued_at": iso_utc(c.issued_at),
            "expires_at": iso_utc(c.expires_at),
            "file_url": c.file_url
        })
    return result
