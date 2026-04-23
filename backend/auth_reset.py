from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import os
import secrets
import datetime

from database import SessionLocal
import models
from auth import get_password_hash, verify_password

reset_router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@reset_router.post("/auth/reset-password")
def reset_password(token: str = Form(...), new_password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.reset_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Token invlido ou expirado.")
        
    if user.reset_token_expires and user.reset_token_expires < datetime.datetime.utcnow():
        user.reset_token = None
        user.reset_token_expires = None
        db.commit()
        raise HTTPException(status_code=400, detail="Token expirado.")
        
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="A senha deve ter pelo menos 6 caracteres.")
        
    user.hashed_password = get_password_hash(new_password)
    user.reset_token = None
    user.reset_token_expires = None
    user.must_change_password = False
    if user.status in ["convite_pendente", "convite_expirado"]:
        user.status = "ativo"
    
    db.commit()
    return {"message": "Senha redefinida com sucesso."}
