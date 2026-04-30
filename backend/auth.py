from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel
from sqlalchemy.orm import Session
import models
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

# Security settings
SECRET_KEY = "super-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    department: Optional[str] = None
    invite_token: Optional[str] = None  # ← token de convite opcional no cadastro

class LoginRequest(BaseModel):
    username: str
    password: str

def get_password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def register_user(db: Session, user: UserCreate):
    if not user.email.endswith("@geobiogas.tech"):
        return {"error": "Apenas usuários com e-mail corporativo @geobiogas.tech podem acessar a plataforma."}

    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        # ✅ BUG 1 CORRIGIDO: só ativa automaticamente se vier com token de convite válido
        if existing_user.status == "convite_pendente":
            # Verifica se o token de convite foi fornecido e corresponde ao do usuário
            if (
                user.invite_token
                and existing_user.invite_token
                and user.invite_token == existing_user.invite_token
                and existing_user.invite_expires_at
                and existing_user.invite_expires_at > datetime.utcnow()
            ):
                existing_user.username = user.username
                existing_user.hashed_password = get_password_hash(user.password)
                existing_user.department = user.department
                existing_user.status = "ativo"
                existing_user.invite_token = None  # invalida o token após uso
                db.commit()
                return {"message": "Cadastro concluído. Seu convite foi aceito!"}
            elif user.invite_token and existing_user.invite_expires_at and existing_user.invite_expires_at <= datetime.utcnow():
                return {"error": "Token de convite expirado. Solicite um novo convite ao administrador."}
            else:
                # E-mail com convite pendente mas sem token válido → não ativa
                return {"error": "E-mail com convite pendente. Use o link de convite enviado pelo administrador."}
        else:
            return {"error": "E-mail já cadastrado."}

    # Cadastro novo (sem convite) → sempre fica como "pending" aguardando aprovação do admin
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        department=user.department,
        role="colaborador",
        status="pending"  # ← nunca "ativo" sem aprovação
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": "Cadastro criado com sucesso. Aguardando aprovação do administrador."}

def login_for_access_token(db: Session, form_data: LoginRequest):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        return {"error": "Usuário ou senha incorretos"}

    if user.status not in ["ativo", "approved"]:
        return {"error": "Cadastro pendente de aprovação ou convite não aceito."}

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "username": user.username,
            "role": user.role,
            "must_change_password": user.must_change_password  # ← envia flag para o frontend
        }
    }

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(lambda: None)):
    # Note: To avoid circular imports, get_db is passed at runtime via dependency overrides or closure.
    pass  # Will be implemented back in main.py instead, reverting this change!
