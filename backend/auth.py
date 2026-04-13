from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel
from sqlalchemy.orm import Session
import models

# Security settings
SECRET_KEY = "super-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

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
        if existing_user.status == "convite_pendente":
            existing_user.username = user.username
            existing_user.hashed_password = get_password_hash(user.password)
            existing_user.department = user.department
            existing_user.status = "ativo"
            db.commit()
            return {"message": "Cadastro concluído. Seu convite foi aceito automaticamente!"}
        else:
            return {"error": "E-mail já cadastrado."}

    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        department=user.department,
        role="usuario",
        status="pendente"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": "Cadastro criado com sucesso. Aguardando aprovação."}

def login_for_access_token(db: Session, form_data: LoginRequest):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        return {"error": "Usuário ou senha incorretos"}
        
    if user.status not in ["ativo", "approved"]:
        return {"error": "Cadastro pendente ou convite expirado."}
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, 
        expires_delta=access_token_expires
    )
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "user": {"username": user.username, "role": user.role}
    }
