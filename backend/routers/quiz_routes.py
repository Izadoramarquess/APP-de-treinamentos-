"""Quizzes: perguntas inline durante o vídeo.

ATENCAO: nenhum endpoint aqui deve devolver correct_option para quem não é
admin, é isso que garante que a resposta certa nunca chega ao navegador
do aluno antes dele responder.
"""
import datetime
from typing import List

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

import models
from deps import get_db, get_current_user, authorize, require_super_admin, require_enrolled_in_module

router = APIRouter()

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
    current_user: models.User = Depends(require_super_admin)
):
    """Mesma lista de cima, mas com o gabarito, usada só na tela de edição
    do quiz, pra mostrar a resposta certa junto de cada pergunta já salva."""
    module = db.query(models.Module).filter(models.Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Módulo não encontrado")
    return db.query(models.Question).filter(models.Question.module_id == module_id).all()

@router.post("/modules/{module_id}/questions", response_model=models.QuestionSchema)
def add_question(
    module_id: int,
    question_data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_super_admin)
):
    module = db.query(models.Module).filter(models.Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Módulo não encontrado")

    db_question = models.Question(
        module_id=module_id,
        text=question_data["text"],
        option_a=question_data["option_a"],
        option_b=question_data["option_b"],
        option_c=question_data["option_c"],
        option_d=question_data["option_d"],
        correct_option=question_data["correct_option"],
        timestamp=question_data.get("timestamp"),
    )
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return db_question

@router.delete("/questions/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_super_admin)
):
    question = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada")
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
    """Corrige uma pergunta no servidor e devolve só se acertou ou não, o
    gabarito em si nunca sai daqui. Usado pelo quiz inline (feedback
    imediato durante o vídeo)."""
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
        # só grava o acerto, um erro numa nova tentativa não desfaz um
        # acerto anterior já registrado.
        attempt.is_correct = True
    attempt.answered_at = datetime.datetime.utcnow()
    db.commit()

    return {"correct": is_correct}
