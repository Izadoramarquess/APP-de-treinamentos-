"""Progresso do aluno: conclusão de módulo, cursos matriculados, certificados."""
import datetime
import os

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

import models
from deps import get_db, get_current_user, authorize, iso_utc, _mark_module_complete, _check_and_issue_course_certificate, require_enrolled, require_enrolled_in_module
from certificate_pdf import generate_certificate_pdf

router = APIRouter()

# ---------------- Progress Tracking ----------------
@router.post("/modules/{module_id}/complete")
def complete_module(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    require_enrolled_in_module(db, current_user.id, module_id)
    # Perguntas inline (durante o vídeo) precisam ter sido respondidas
    # certo — o player já bloqueia isso na tela, mas só no navegador: dava
    # pra arrastar a barra de progresso do vídeo e pular a pergunta sem
    # nunca respondê-la. Aqui é a checagem que não dá pra burlar.
    inline_questions = db.query(models.Question).filter(
        models.Question.module_id == module_id,
        models.Question.is_final_exam == False
    ).all()
    if inline_questions:
        correct_ids = {
            a.question_id for a in db.query(models.QuestionAttempt).filter(
                models.QuestionAttempt.user_id == current_user.id,
                models.QuestionAttempt.question_id.in_([q.id for q in inline_questions]),
                models.QuestionAttempt.is_correct == True
            ).all()
        }
        if any(q.id not in correct_ids for q in inline_questions):
            raise HTTPException(status_code=400, detail="Responda corretamente todas as perguntas do vídeo antes de concluir o módulo.")
    # Módulo não tem nota própria a apurar (a prova, se houver, é do curso
    # inteiro — ver /courses/{id}/exam-submit), score é fixo.
    certificate_issued = _mark_module_complete(db, current_user.id, module_id, 100.0)
    return {"message": "Módulo concluído!", "completed": True, "certificate_issued": certificate_issued}

@router.get("/courses/{course_id}/progress")
def get_course_progress(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Progresso módulo a módulo (usado pela tela de módulos do aluno)."""
    require_enrolled(db, current_user.id, course_id)
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
    require_enrolled(db, current_user.id, course_id)
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
    if current_user.role == "super_admin":
        members = db.query(models.User).filter(
            models.User.status == "ativo"
        ).all()
    elif current_user.role == "admin":
        members = db.query(models.User).filter(
            models.User.status == "ativo",
            models.User.company_id == current_user.company_id
        ).all()
    else:
        members = db.query(models.User).filter(
            models.User.team_id == current_user.team_id,
            models.User.status == "ativo"
        ).all()

    team_names = {t.id: t.name for t in db.query(models.Team).all()}

    result = []
    for member in members:
        enrollments = db.query(models.Enrollment).filter(
            models.Enrollment.user_id == member.id
        ).all()

        # Detalhe por curso — inclui todo módulo do curso, mesmo o que a
        # pessoa nunca abriu (sem isso, "total" só contava módulo já
        # iniciado, e um curso com 5 módulos onde só o 1º foi assistido
        # aparecia como 100% concluído/1 de 1 — bug real encontrado em
        # produção). O agregado abaixo soma esse detalhe correto.
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
                "certificate_id": cert.id if cert else None,
                "certificate_expires_at": iso_utc(cert.expires_at) if cert else None,
            })

        total = sum(c["total"] for c in courses_detail)
        done = sum(c["completed"] for c in courses_detail)
        result.append({
            "user_id": member.id,
            "username": member.username,
            "email": member.email,
            "role": member.role,
            "team_id": member.team_id,
            "team_name": team_names.get(member.team_id, "—"),
            "company_id": member.company_id,
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

@router.get("/certificates/{certificate_id}/download")
def download_certificate(
    certificate_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """PDF gerado na hora a partir dos dados do certificado — não fica nada
    persistido em disco. Dono do certificado sempre pode baixar; admin pode
    baixar qualquer um; liderança só os da própria equipe."""
    cert = db.query(models.Certificate).filter(models.Certificate.id == certificate_id).first()
    if not cert:
        raise HTTPException(404, "Certificado não encontrado")

    owner = db.query(models.User).filter(models.User.id == cert.user_id).first()
    is_owner = current_user.id == cert.user_id
    is_super_admin = current_user.role == "super_admin"
    is_admin = current_user.role == "admin" and owner and owner.company_id == current_user.company_id
    is_leader_of_owner = current_user.role == "lideranca" and owner and owner.team_id == current_user.team_id
    if not (is_owner or is_super_admin or is_admin or is_leader_of_owner):
        raise HTTPException(403, "Sem permissão para baixar este certificado")

    course = db.query(models.Course).filter(models.Course.id == cert.course_id).first()
    company_logo_url = course.company.logo_url if course and course.company else None
    company_name = course.company.name if course and course.company else None
    pdf_bytes = generate_certificate_pdf(
        username=owner.username if owner else "—",
        course_title=course.title if course else "—",
        issued_at=cert.issued_at,
        expires_at=cert.expires_at,
        certificate_template_url=course.certificate_template_url if course else None,
        company_logo_url=company_logo_url,
        company_name=company_name,
    )
    safe_course_name = "".join(ch if ch.isalnum() else "_" for ch in (course.title if course else "certificado"))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificado_{safe_course_name}.pdf"'}
    )
