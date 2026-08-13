"""Progresso do aluno: conclusão de módulo, cursos matriculados, certificados."""
import datetime
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
from deps import get_db, get_current_user, authorize, iso_utc, _mark_module_complete, _check_and_issue_course_certificate

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
    certificate_issued = _mark_module_complete(db, current_user.id, module_id, 100.0)
    return {"message": "Módulo concluído!", "completed": True, "certificate_issued": certificate_issued}

@router.get("/courses/{course_id}/progress")
def get_course_progress(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Progresso módulo a módulo (usado pela tela de módulos do aluno)."""
    progresses = db.query(models.ModuleProgress).join(models.Module).filter(
        models.Module.course_id == course_id,
        models.ModuleProgress.user_id == current_user.id
    ).all()
    return [{"module_id": p.module_id, "completed": p.is_completed, "score": p.score_final} for p in progresses]

@router.get("/courses/{course_id}/progress-summary")
def get_course_progress_summary(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Percentual agregado do curso (substitui o antigo /paths/{id}/progress —
    fica mais simples agora porque não precisa mais somar vários cursos de
    uma trilha, o curso já é o próprio nível de topo)."""
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course: raise HTTPException(404, "Curso não encontrado")
    modules = db.query(models.Module).filter(models.Module.course_id == course_id).all()
    total = len(modules)
    completed = 0
    if total:
        module_ids = [m.id for m in modules]
        completed = db.query(models.ModuleProgress).filter(
            models.ModuleProgress.module_id.in_(module_ids),
            models.ModuleProgress.user_id == current_user.id,
            models.ModuleProgress.is_completed == True
        ).count()
    pct = round((completed / total * 100) if total > 0 else 0)
    return {"total": total, "completed": completed, "percent": pct}

@router.get("/my-courses")
def get_my_courses(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    enrollments = db.query(models.Enrollment).filter(
        models.Enrollment.user_id == current_user.id
    ).all()
    course_ids = [e.course_id for e in enrollments]
    if not course_ids:
        return []
    courses = db.query(models.Course).filter(
        models.Course.id.in_(course_ids)
    ).all()
    return courses

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

    team_names = {t.id: t.name for t in db.query(models.Team).all()}

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
        ).all()

        # Detalhe por curso — o agregado acima soma tudo, mas quem acompanha
        # precisa saber EM QUAL curso a pessoa travou, não só o total.
        courses_detail = []
        for enr in enrollments:
            course = db.query(models.Course).filter(models.Course.id == enr.course_id).first()
            if not course:
                continue
            module_ids = [m.id for m in db.query(models.Module.id).filter(models.Module.course_id == course.id).all()]
            c_total = len(module_ids)
            c_done = db.query(models.ModuleProgress).filter(
                models.ModuleProgress.module_id.in_(module_ids),
                models.ModuleProgress.user_id == member.id,
                models.ModuleProgress.is_completed == True
            ).count() if module_ids else 0
            cert = db.query(models.Certificate).filter(
                models.Certificate.user_id == member.id,
                models.Certificate.course_id == course.id
            ).first()
            # Status do curso — progresso não é "quantos módulos assistiu",
            # é em qual desses 3 estados o curso está pra essa pessoa.
            if c_done == 0:
                course_status = "matriculado"
            elif c_done < c_total:
                course_status = "em_andamento"
            else:
                course_status = "finalizado"
            courses_detail.append({
                "course_id": course.id,
                "course_title": course.title,
                "total": c_total,
                "completed": c_done,
                "percent": round((c_done / c_total * 100) if c_total > 0 else 0),
                "status": course_status,
                "certificate_issued": cert is not None,
                "certificate_expires_at": iso_utc(cert.expires_at) if cert else None,
            })

        result.append({
            "user_id": member.id,
            "username": member.username,
            "email": member.email,
            "role": member.role,
            "team_id": member.team_id,
            "team_name": team_names.get(member.team_id, "—"),
            "enrollments": len(enrollments),
            "modules_total": total,
            "modules_done": done,
            "percent": round((done / total * 100) if total > 0 else 0),
            "courses": courses_detail,
        })
    return result

@router.post("/courses/{course_id}/certificate")
def issue_certificate(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Gatilho manual idempotente — a emissão normalmente já acontece
    sozinha em _mark_module_complete quando o último módulo do curso é
    concluído. Existe pra permitir reconferir/reemitir sem quebrar nada se
    chamado de novo."""
    cert = _check_and_issue_course_certificate(db, current_user.id, course_id)
    if not cert:
        raise HTTPException(400, "Curso ainda não foi concluído (nem todos os módulos estão completos).")
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
        course = db.query(models.Course).filter(models.Course.id == c.course_id).first()
        result.append({
            "certificate_id": c.id,
            "course_id": c.course_id,
            "course_title": course.title if course else "—",
            "issued_at": iso_utc(c.issued_at),
            "expires_at": iso_utc(c.expires_at),
            "file_url": c.file_url
        })
    return result
