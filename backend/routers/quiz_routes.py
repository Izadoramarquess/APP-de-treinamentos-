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
from deps import get_db, get_current_user, authorize, _mark_module_complete, require_enrolled_in_module, check_same_company

router = APIRouter()

@router.get("/modules/{module_id}/questions", response_model=List[models.QuestionPublicSchema])
def list_questions(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    require_enrolled_in_module(db, current_user.id, module_id)
    return db.query(models.Question).filter(models.Question.module_id == module_id).all()

@router.post("/modules/{module_id}/questions", response_model=models.QuestionSchema)
def add_question(
    module_id: int,
    question_data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
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
        is_final_exam=question_data.get("is_final_exam", False)
    )
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question

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
    a nota da prova em si só é computada por /modules/{id}/exam-submit."""
    question = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada")
    require_enrolled_in_module(db, current_user.id, question.module_id)
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

@router.post("/modules/{module_id}/exam-submit")
def submit_exam(
    module_id: int,
    answers: List[dict],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Corrige a prova final inteira no servidor a partir das respostas
    enviadas ({question_id, selected_option}) e só marca o módulo como
    concluído (com a nota calculada aqui, nunca a que o cliente mandar) se
    a nota real bater o mínimo de aprovação."""
    require_enrolled_in_module(db, current_user.id, module_id)
    exam_questions = db.query(models.Question).filter(
        models.Question.module_id == module_id,
        models.Question.is_final_exam == True
    ).all()
    if not exam_questions:
        raise HTTPException(status_code=400, detail="Este módulo não tem prova final.")

    valid_ids = {q.id for q in exam_questions}
    correct_by_id = {q.id: (q.correct_option or "").strip().upper() for q in exam_questions}

    answered = {}
    for a in answers:
        qid = a.get("question_id")
        if qid in valid_ids:  # ignora respostas de perguntas de outro módulo
            answered[qid] = str(a.get("selected_option", "")).strip().upper()

    total = len(exam_questions)
    correct_count = sum(1 for qid, correct in correct_by_id.items() if answered.get(qid) == correct)
    score = round((correct_count / total) * 100) if total else 0
    passed = score >= 80

    certificate_issued = False
    if passed:
        certificate_issued = _mark_module_complete(db, current_user.id, module_id, float(score))

    return {"score": score, "passed": passed, "correct_count": correct_count, "total": total, "certificate_issued": certificate_issued}
