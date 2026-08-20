"""Quizzes e prova final.

ATENÇÃO: nenhum endpoint aqui deve devolver correct_option para quem não é
admin — é isso que garante que a resposta certa nunca chega ao navegador
do aluno antes dele responder. A nota da prova é sempre calculada aqui a
partir das respostas enviadas, nunca recebida pronta do cliente.
"""
import datetime
from typing import List

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

import models
from deps import get_db, get_current_user, authorize, _check_and_issue_course_certificate, require_enrolled, require_enrolled_in_module, check_same_company

router = APIRouter()

# ---------------- Perguntas inline (por módulo) ----------------
@router.get("/modules/{module_id}/questions", response_model=List[models.QuestionPublicSchema])
def list_questions(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    require_enrolled_in_module(db, current_user.id, module_id)
    return db.query(models.Question).filter(models.Question.module_id == module_id).all()

@router.get("/admin/modules/{module_id}/questions", response_model=List[models.QuestionSchema])
def list_questions_admin(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    """Mesma lista de cima, mas com o gabarito — usada só na tela de edição
    do quiz, pra mostrar a resposta certa junto de cada pergunta já salva."""
    module = db.query(models.Module).filter(models.Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Módulo não encontrado")
    if module.course:
        check_same_company(current_user, module.course.company_id, "módulo")
    return db.query(models.Question).filter(models.Question.module_id == module_id).all()

@router.post("/modules/{module_id}/questions", response_model=models.QuestionSchema)
def add_question(
    module_id: int,
    question_data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    """Pergunta inline, presa a um momento do vídeo desse módulo. A prova
    final é um recurso separado, do curso inteiro — ver /courses/{id}/exam-questions."""
    module = db.query(models.Module).filter(models.Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Módulo não encontrado")
    if module.course:
        check_same_company(current_user, module.course.company_id, "módulo")

    db_question = models.Question(
        module_id=module_id,
        text=question_data["text"],
        option_a=question_data["option_a"],
        option_b=question_data["option_b"],
        option_c=question_data["option_c"],
        option_d=question_data["option_d"],
        correct_option=question_data["correct_option"],
        timestamp=question_data.get("timestamp"),
        is_final_exam=False
    )
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question

# ---------------- Prova final (por curso, cobre todos os módulos) ----------------
@router.get("/courses/{course_id}/exam-questions", response_model=List[models.QuestionPublicSchema])
def list_exam_questions(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    require_enrolled(db, current_user.id, course_id)
    return db.query(models.Question).filter(
        models.Question.course_id == course_id, models.Question.is_final_exam == True
    ).all()

@router.get("/admin/courses/{course_id}/exam-questions", response_model=List[models.QuestionSchema])
def list_exam_questions_admin(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso não encontrado")
    check_same_company(current_user, course.company_id, "curso")
    return db.query(models.Question).filter(
        models.Question.course_id == course_id, models.Question.is_final_exam == True
    ).all()

@router.post("/courses/{course_id}/exam-questions", response_model=models.QuestionSchema)
def add_exam_question(
    course_id: int,
    question_data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso não encontrado")
    check_same_company(current_user, course.company_id, "curso")

    db_question = models.Question(
        course_id=course_id,
        text=question_data["text"],
        option_a=question_data["option_a"],
        option_b=question_data["option_b"],
        option_c=question_data["option_c"],
        option_d=question_data["option_d"],
        correct_option=question_data["correct_option"],
        is_final_exam=True
    )
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question

@router.delete("/questions/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    question = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada")
    company_id = question.module.course.company_id if question.module and question.module.course else (question.course.company_id if question.course else None)
    if company_id is not None:
        check_same_company(current_user, company_id, "pergunta")
    db.query(models.QuestionAttempt).filter(models.QuestionAttempt.question_id == question_id).delete()
    db.delete(question)
    db.commit()
    return {"message": "Pergunta excluída"}

@router.post("/questions/{question_id}/check")
def check_question_answer(
    question_id: int,
    selected_option: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Corrige uma pergunta no servidor e devolve só se acertou ou não —
    o gabarito em si nunca sai daqui. Usado pelo quiz inline (feedback
    imediato) e, pergunta a pergunta, pela prova final (feedback visual);
    a nota da prova em si só é computada por /courses/{id}/exam-submit."""
    question = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada")
    if question.module_id:
        require_enrolled_in_module(db, current_user.id, question.module_id)
    else:
        require_enrolled(db, current_user.id, question.course_id)
    is_correct = selected_option.strip().upper() == (question.correct_option or "").strip().upper()

    attempt = db.query(models.QuestionAttempt).filter(
        models.QuestionAttempt.user_id == current_user.id,
        models.QuestionAttempt.question_id == question_id
    ).first()
    if not attempt:
        attempt = models.QuestionAttempt(user_id=current_user.id, question_id=question_id)
        db.add(attempt)
    if is_correct:
        # só grava o acerto; um erro numa nova tentativa não desfaz um
        # acerto anterior já registrado.
        attempt.is_correct = True
    attempt.answered_at = datetime.datetime.utcnow()
    db.commit()

    return {"correct": is_correct}

@router.post("/courses/{course_id}/exam-submit")
def submit_exam(
    course_id: int,
    answers: List[dict],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Corrige a prova final do curso inteiro no servidor a partir das
    respostas enviadas ({question_id, selected_option}) e emite o
    certificado (com a nota calculada aqui, nunca a que o cliente mandar)
    se a nota real bater o mínimo de aprovação. Só libera a prova depois
    que todo módulo do curso já foi concluído — a prova cobre o curso
    inteiro, não faz sentido responder antes de assistir tudo."""
    require_enrolled(db, current_user.id, course_id)
    modules = db.query(models.Module).filter(models.Module.course_id == course_id).all()
    if modules:
        module_ids = [m.id for m in modules]
        done_count = db.query(models.ModuleProgress).filter(
            models.ModuleProgress.module_id.in_(module_ids),
            models.ModuleProgress.user_id == current_user.id,
            models.ModuleProgress.is_completed == True
        ).count()
        if done_count < len(modules):
            raise HTTPException(status_code=400, detail="Conclua todos os módulos do curso antes de fazer a prova final.")

    exam_questions = db.query(models.Question).filter(
        models.Question.course_id == course_id,
        models.Question.is_final_exam == True
    ).all()
    if not exam_questions:
        raise HTTPException(status_code=400, detail="Este curso não tem prova final.")

    valid_ids = {q.id for q in exam_questions}
    correct_by_id = {q.id: (q.correct_option or "").strip().upper() for q in exam_questions}

    answered = {}
    for a in answers:
        qid = a.get("question_id")
        if qid in valid_ids:  # ignora respostas de perguntas de outro curso
            answered[qid] = str(a.get("selected_option", "")).strip().upper()

    total = len(exam_questions)
    correct_count = sum(1 for qid, correct in correct_by_id.items() if answered.get(qid) == correct)
    score = round((correct_count / total) * 100) if total else 0
    passed = score >= 80

    certificate_issued = False
    if passed:
        was_new = db.query(models.Certificate).filter(
            models.Certificate.user_id == current_user.id,
            models.Certificate.course_id == course_id
        ).first() is None
        cert = _check_and_issue_course_certificate(db, current_user.id, course_id, exam_passed=True)
        certificate_issued = bool(cert) and was_new

    return {"score": score, "passed": passed, "correct_count": correct_count, "total": total, "certificate_issued": certificate_issued}
