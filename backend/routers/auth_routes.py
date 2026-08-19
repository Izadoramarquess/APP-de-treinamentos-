"""Identidade e sessão: cadastro, login, perfil, troca de senha, aceite de convite."""
import datetime

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

import models
import auth
from auth import get_password_hash
from deps import get_db, get_current_user, authorize

router = APIRouter()

@router.post("/register")
def register(user: auth.UserCreate, db: Session = Depends(get_db)):
    return auth.register_user(db, user)

@router.post("/login")
def login(form_data: auth.LoginRequest, db: Session = Depends(get_db)):
    return auth.login_for_access_token(db, form_data)

@router.get("/users/me", response_model=models.UserSchema)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@router.post("/auth/change-password")
def change_password(
    new_password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin", "lideranca", "colaborador", "usuario", "user"]))
):
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="A senha deve ter pelo menos 6 caracteres.")
    if new_password == auth.TEMP_PASSWORD:
        raise HTTPException(status_code=400, detail="Escolha uma senha diferente da temporária.")
    current_user.hashed_password = get_password_hash(new_password)
    current_user.must_change_password = False
    db.commit()
    return {"message": "Senha alterada com sucesso!"}

@router.post("/invite/accept")
def accept_invite(token: str = Form(...), db: Session = Depends(get_db)):
    """Ativa a conta com a senha temporária padrão (Mudar@123*) — a pessoa
    não escolhe senha própria aqui, só confirma que quer ativar o acesso.
    No primeiro login, must_change_password força a troca (mesmo fluxo já
    usado quando um admin reseta a senha de alguém)."""
    user = db.query(models.User).filter(models.User.invite_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Token inválido.")
    if user.invite_expires_at and user.invite_expires_at < datetime.datetime.utcnow():
        user.status = "convite_expirado"
        db.commit()
        raise HTTPException(status_code=400, detail="Token expirado.")
    user.hashed_password = get_password_hash(auth.TEMP_PASSWORD)
    user.status = "ativo"
    user.invite_token = None
    user.invite_expires_at = None
    user.must_change_password = True

    db.commit()
    return {"message": "Conta ativada com sucesso!", "temp_password": auth.TEMP_PASSWORD}
