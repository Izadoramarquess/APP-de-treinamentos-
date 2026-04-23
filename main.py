from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Header
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from typing import List, Optional
import uvicorn
import os
import shutil
import uuid
import datetime
import secrets

import models, database, auth
from auth import get_password_hash
from auth_reset import reset_router
from dotenv import load_dotenv

load_dotenv()



app = FastAPI(title="GeoTrilha LMS API")

# CORS Configuration
origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
if "" in origins: origins.remove("")
if not origins: origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True if origins != ["*"] else False, # Credentials not allowed with wildcard
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reset_router)

# Cache Middleware for Static Assets
@app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/uploads"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif request.url.path.endswith((".js", ".css", ".ico")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
print(f"DEBUG: Serving frontend from: {frontend_path}")

@app.get("/")
async def serve_index():
    index_path = os.path.join(frontend_path, "index.html")
    print(f"DEBUG: Index requested. Path: {index_path} - Exists: {os.path.exists(index_path)}")
    if os.path.exists(index_path):
        from fastapi.responses import FileResponse
        return FileResponse(index_path, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return {"message": "Frontend not found"}

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        from jose import jwt
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def authorize(allowed_roles: List[str]):
    def decorator(current_user: models.User = Depends(get_current_user)):
        if current_user.role == "admin":
            return current_user
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Você não tem permissão para realizar esta ação.")
        return current_user
    return decorator

# ---------------- Auth ----------------
@app.post("/register")
def register(user: auth.UserCreate, db: Session = Depends(get_db)):
    return auth.register_user(db, user)

@app.post("/login")
def login(form_data: auth.LoginRequest, db: Session = Depends(get_db)):
    return auth.login_for_access_token(db, form_data)

@app.get("/users/me", response_model=models.UserSchema)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@app.post("/auth/change-password")
def change_password(
    password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin", "lideranca", "colaborador", "usuario", "user"]))
):
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="A senha deve ter pelo menos 6 caracteres.")
    if password == "Mudar@123":
        raise HTTPException(status_code=400, detail="Escolha uma senha diferente da temporária.")
    current_user.hashed_password = get_password_hash(password)
    current_user.must_change_password = False
    db.commit()
    return {"message": "Senha alterada com sucesso!"}

# ---------------- Admin: User Management ----------------
@app.get("/admin/users", response_model=List[models.UserSchema])
def list_users(db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin", "lideranca"]))):
    if current_user.role == "admin":
        # Garante que o endpoint retorne TODOS os usuários, incluindo os com status 'pending'
        return db.query(models.User).all()
    # Liderança só vê membros da própria equipe
    return db.query(models.User).filter(models.User.team_id == current_user.team_id).all()

@app.post("/admin/users/{user_id}/status")
def update_user_status(user_id: int, new_status: str = Form(None), role: str = Form(None), team_id: int = Form(None), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if role == "admin" and not user.email.endswith("@geobiogas.tech"):
        raise HTTPException(status_code=400, detail="Apenas e-mails corporativos @geobiogas.tech podem ser administradores.")
    if new_status: user.status = new_status
    if role: user.role = role
    if team_id is not None: user.team_id = team_id if team_id != 0 else None
    db.commit()
    return {"message": "User updated"}

@app.post("/admin/users/{user_id}/role")
def update_user_role(user_id: int, role: str = Form(...), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if role == "admin" and not user.email.endswith("@geobiogas.tech"):
        raise HTTPException(status_code=400, detail="Apenas e-mails corporativos @geobiogas.tech podem ser administradores.")
    user.role = role
    db.commit()
    return {"message": "Role atualizado com sucesso"}

@app.post("/admin/users/{user_id}/reset-password")
def admin_reset_password(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = get_password_hash("Mudar@123")
    user.must_change_password = True
    
    reset_token = secrets.token_urlsafe(32)
    user.reset_token = reset_token
    user.reset_token_expires = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    
    db.commit()
    
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    reset_link = f"{base_url}/?view=reset&token={reset_token}"
    
    return {"reset_link": reset_link}

@app.delete("/admin/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Voc no pode excluir seu prprio usurio.")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usurio no encontrado")
    
    # Clean up dependent records
    db.query(models.Enrollment).filter(models.Enrollment.user_id == user.id).delete()
    db.query(models.ModuleProgress).filter(models.ModuleProgress.user_id == user.id).delete()
    db.query(models.Certificate).filter(models.Certificate.user_id == user.id).delete()
    
    # Unlink invited_by gracefully
    db.query(models.User).filter(models.User.invited_by_id == user.id).update({"invited_by_id": None})
    
    db.delete(user)
    db.commit()
    return {"message": "Usurio excludo com sucesso"}

@app.post("/admin/users/invite")
def invite_user_admin(
    username: str = Form(...),
    email: str = Form(...),
    role: str = Form("usuario"),
    team_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin", "lideranca"]))
):
    if current_user.role == "lideranca":
        team_id = current_user.team_id
        role = "usuario"
    
    if role == "admin" and not email.endswith("@geobiogas.tech"):
        raise HTTPException(status_code=400, detail="Apenas e-mails corporativos @geobiogas.tech podem ser administradores.")

    existing_user = db.query(models.User).filter(models.User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado no sistema.")

    invite_token = secrets.token_urlsafe(32)
    
    from auth import get_password_hash
    db_user = models.User(
        username=username,
        email=email,
        hashed_password=get_password_hash(uuid.uuid4().hex),
        role=role,
        team_id=team_id,
        status="convite_pendente",
        invite_token=invite_token,
        invite_expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
        invited_by_id=current_user.id
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    invite_link = f"{base_url}/?view=convite&token={invite_token}"
    
    return {"invite_link": invite_link}

@app.post("/enrollments", response_model=models.EnrollmentSchema)
def enroll_user(
    user_id: int = Form(...),
    path_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin", "lideranca"]))
):
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user: raise HTTPException(status_code=404, detail="User not found")
    
    # Validação de equipe para líderes
    if current_user.role == "lideranca" and target_user.team_id != current_user.team_id:
        raise HTTPException(status_code=403, detail="Você só pode atribuir trilhas a membros da sua equipe.")
        
    enrollment = models.Enrollment(user_id=user_id, path_id=path_id)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment

@app.post("/admin/users/{user_id}/resend_invite")
def resend_invite(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin", "lideranca"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)
    
    # Validação para liderança
    if current_user.role == "lideranca" and user.team_id != current_user.team_id:
        raise HTTPException(status_code=403, detail="Você só pode reenviar convites para membros da sua própria equipe.")
        
    if not user.email.endswith("@geobiogas.tech"): raise HTTPException(status_code=400, detail="Domínio inválido.")
    
    invite_token = secrets.token_urlsafe(32)
    user.invite_token = invite_token
    user.invite_expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    user.status = "convite_pendente"
    user.invited_by_id = current_user.id
    db.commit()
    
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    invite_link = f"{base_url}/?view=convite&token={invite_token}"
    
    return {"message": "Reenviado com sucesso", "invite_link": invite_link}

@app.post("/admin/users/{user_id}/cancel_invite")
def cancel_invite(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)
    user.invite_token = None
    user.status = "convite_expirado"
    db.commit()
    return {"message": "Cancelado"}

@app.post("/admin/users/{user_id}/activate_manual")
def activate_manual(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)
    user.status = "ativo"
    db.commit()
    return {"message": "Ativado"}

@app.post("/admin/users/{user_id}/remove_team")
def remove_team(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)
    user.team_id = None
    if user.role == "lideranca": user.role = "usuario"
    db.commit()
    return {"message": "Removido"}

@app.post("/invite/accept")
def accept_invite(token: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.invite_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Token invlido.")
    if user.invite_expires_at and user.invite_expires_at < datetime.datetime.utcnow():
        user.status = "convite_expirado"
        db.commit()
        raise HTTPException(status_code=400, detail="Token expirado.")
    user.hashed_password = get_password_hash(password)
    user.status = "ativo"
    user.invite_token = None
    user.invite_expires_at = None
    
    # If they are accepting via UI, we should still allow standard pw but normally they'd type it.
    if password == "Mudar@123":
        user.must_change_password = True
    else:
        user.must_change_password = False
        
    db.commit()
    return {"message": "Conta ativada com sucesso!"}

@app.get("/admin/invites")
def list_invites(db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin", "lideranca"]))):
    users = db.query(models.User).all()
    out = []
    for u in users:
        inviter = u.invited_by.username if u.invited_by else None
        last_log = db.query(models.EmailLog).filter(models.EmailLog.recipient_email == u.email).order_by(models.EmailLog.sent_at.desc()).first()
        out.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "status": u.status,
            "team_id": u.team_id,
            "invited_by": inviter,
            "invite_date": (u.invite_expires_at - datetime.timedelta(days=7)).isoformat() if u.invite_expires_at else None,
            "last_email_date": last_log.sent_at.isoformat() if last_log else None,
            "last_email_status": last_log.status if last_log else None
        })
    return out

# ---------------- Learning Paths ----------------
@app.get("/paths", response_model=List[models.LearningPathSchema])
def list_paths(db: Session = Depends(get_db)):
    return db.query(models.LearningPath).all()

@app.post("/paths", response_model=models.LearningPathSchema)
def create_path(title: str = Form(...), description: str = Form(""), is_standard_training: bool = Form(False), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    path = models.LearningPath(title=title, description=description, is_standard_training=is_standard_training)
    db.add(path)
    db.commit()
    db.refresh(path)
    return path

@app.put("/paths/{path_id}", response_model=models.LearningPathSchema)
def update_path(path_id: int, title: str = Form(...), description: str = Form(""), is_standard_training: bool = Form(False), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    path = db.query(models.LearningPath).filter(models.LearningPath.id == path_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="Trilha no encontrada")
    path.title = title
    path.description = description
    path.is_standard_training = is_standard_training
    db.commit()
    db.refresh(path)
    return path

@app.delete("/paths/{path_id}")
def delete_path(path_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    path = db.query(models.LearningPath).filter(models.LearningPath.id == path_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="Trilha no encontrada")
    db.query(models.Enrollment).filter(models.Enrollment.path_id == path_id).delete()
    for course in db.query(models.Course).filter(models.Course.path_id == path.id).all():
        delete_course(course.id, db, current_user)
    db.delete(path)
    db.commit()
    return {"message": "Trilha excluda com sucesso"}

# ---------------- Courses ----------------
@app.get("/paths/{path_id}/courses", response_model=List[models.CourseSchema])
def list_courses(path_id: int, db: Session = Depends(get_db)):
    return db.query(models.Course).filter(models.Course.path_id == path_id).order_by(models.Course.order).all()

@app.post("/paths/{path_id}/courses", response_model=models.CourseSchema)
def create_course(path_id: int, title: str = Form(...), description: str = Form(...), order: int = Form(1), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    course = models.Course(path_id=path_id, title=title, description=description, order=order)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course

@app.put("/courses/{course_id}", response_model=models.CourseSchema)
def update_course(course_id: int, title: str = Form(...), description: str = Form(...), order: int = Form(1), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    course.title = title
    course.description = description
    course.order = order
    db.commit()
    db.refresh(course)
    return course

@app.delete("/courses/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    # Delete dependent modules
    for module in db.query(models.Module).filter(models.Module.course_id == course.id).all():
        delete_module(module.id, db, current_user)
    db.delete(course)
    db.commit()
    return {"message": "Curso excludo com sucesso"}

# ---------------- Modules (formerly Courses) ----------------
@app.get("/courses/{course_id}/modules", response_model=List[models.ModuleSchema])
def list_modules(course_id: int, db: Session = Depends(get_db)):
    return db.query(models.Module).filter(models.Module.course_id == course_id).order_by(models.Module.order).all()

@app.post("/modules/upload/init")
def init_upload(filename: str, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    upload_dir = "uploads/temp"
    if not os.path.exists(upload_dir): os.makedirs(upload_dir)
    upload_id = str(uuid.uuid4())
    temp_file_path = os.path.join(upload_dir, f"{upload_id}_{filename}")
    with open(temp_file_path, "wb") as f: pass
    return {"upload_id": upload_id, "filename": filename}

@app.post("/modules/upload/chunk")
def upload_chunk(upload_id: str = Form(...), filename: str = Form(...), chunk_index: int = Form(...), chunk: UploadFile = File(...), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    temp_file_path = os.path.join("uploads/temp", f"{upload_id}_{filename}")
    if not os.path.exists(temp_file_path):
        raise HTTPException(status_code=404, detail="Upload init not found")
    with open(temp_file_path, "ab") as f:
        f.write(chunk.file.read())
    return {"status": "success", "chunk_index": chunk_index}

@app.post("/courses/{course_id}/modules", response_model=models.ModuleSchema)
def create_module(
    course_id: int,
    title: str = Form(...), 
    description: str = Form(...), 
    order: int = Form(1),
    validity_months: int = Form(None),
    upload_id: str = Form(None), 
    filename: str = Form(None), 
    thumbnail: UploadFile = File(None),
    cert_template: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    video_url = None
    final_dir = "uploads"
    if not os.path.exists(final_dir): os.makedirs(final_dir)

    if upload_id and filename:
        temp_file_path = os.path.join("uploads/temp", f"{upload_id}_{filename}")
        if os.path.exists(temp_file_path):
            final_file_path = os.path.join(final_dir, filename)
            shutil.move(temp_file_path, final_file_path)
            video_url = f"/video/{filename}"
            
    thumbnail_path = None
    if thumbnail:
        thumbnail_filename = f"thumb_{uuid.uuid4()}_{thumbnail.filename}"
        with open(os.path.join(final_dir, thumbnail_filename), "wb") as buffer:
            shutil.copyfileobj(thumbnail.file, buffer)
        thumbnail_path = f"/uploads/{thumbnail_filename}"

    cert_path = None
    if cert_template:
        cert_filename = f"cert_tpl_{uuid.uuid4()}_{cert_template.filename}"
        with open(os.path.join(final_dir, cert_filename), "wb") as buffer:
            shutil.copyfileobj(cert_template.file, buffer)
        cert_path = f"/uploads/{cert_filename}"

    module = models.Module(
        course_id=course_id,
        order=order,
        title=title, 
        description=description, 
        video_url=video_url,
        thumbnail_url=thumbnail_path,
        certificate_template_url=cert_path,
        validity_months=validity_months
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    return module

@app.put("/modules/{module_id}", response_model=models.ModuleSchema)
def update_module(
    module_id: int,
    title: str = Form(...), 
    description: str = Form(...), 
    order: int = Form(1),
    validity_months: int = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    module = db.query(models.Module).filter(models.Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Mdulo no encontrado")
    
    module.title = title
    module.description = description
    module.order = order
    module.validity_months = validity_months
    
    db.commit()
    db.refresh(module)
    return module

@app.delete("/modules/{module_id}")
def delete_module(module_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    module = db.query(models.Module).filter(models.Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Mdulo no encontrado")
        
    db.query(models.Question).filter(models.Question.module_id == module.id).delete()
    db.query(models.Material).filter(models.Material.module_id == module.id).delete()
    db.query(models.ModuleProgress).filter(models.ModuleProgress.module_id == module.id).delete()
    db.query(models.Certificate).filter(models.Certificate.module_id == module.id).delete()
    
    db.delete(module)
    db.commit()
    return {"message": "Mdulo excludo com sucesso"}

# ---------------- Streaming ----------------
# A rota /video agora é servida automaticamente pelo StaticFiles montado ao final do arquivo,
# que já suporta Range Requests (Streaming) nativamente.


# ---------------- Quizzes & Exams ----------------
@app.post("/modules/{module_id}/questions", response_model=models.QuestionSchema)
def add_question(
    module_id: int, 
    question_data: dict, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
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

# ---------------- Teams ----------------
@app.get("/teams", response_model=List[models.TeamSchema])
def list_teams(db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin", "lideranca"]))):
    return db.query(models.Team).all()

@app.post("/teams", response_model=models.TeamSchema)
def create_team(name: str = Form(...), description: str = Form(""), emails: str = Form(""), team_admin_email: str = Form(...), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    if not team_admin_email.endswith("@geobiogas.tech"):
        raise HTTPException(status_code=400, detail="Apenas e-mails corporativos @geobiogas.tech podem ser administradores.")

    team = models.Team(name=name, description=description)
    db.add(team)
    db.commit()
    db.refresh(team)
    
    team_members_ids = []

    def dispatch_team_member(email_addr, is_admin):
        if not email_addr.endswith("@geobiogas.tech"):
            raise HTTPException(status_code=400, detail="Apenas usuários com e-mail corporativo @geobiogas.tech podem acessar a plataforma.")
        user = db.query(models.User).filter(models.User.email == email_addr).first()
        if user:
            user.team_id = team.id
            if is_admin: user.role = "lideranca"
            team_members_ids.append(user.id)
        else:
            random_pass = uuid.uuid4().hex
            invite_t = secrets.token_urlsafe(32)
            new_user = models.User(
                username=email_addr,
                email=email_addr,
                hashed_password=get_password_hash(random_pass),
                role="lideranca" if is_admin else "usuario",
                status="convite_pendente",
                team_id=team.id,
                invite_token=invite_t,
                invite_expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
                invited_by_id=current_user.id
            )
            db.add(new_user)
            db.flush()
            team_members_ids.append(new_user.id)

    dispatch_team_member(team_admin_email, True)
    
    if emails:
        email_list = [e.strip() for e in emails.split(",") if e.strip()]
        for email in email_list:
            if email == team_admin_email: continue
            dispatch_team_member(email, False)
    
    # Liberar treinamentos padrão
    standard_paths = db.query(models.LearningPath).filter(models.LearningPath.is_standard_training == True).all()
    for spath in standard_paths:
        for member_id in team_members_ids:
            existing_enrollment = db.query(models.Enrollment).filter(models.Enrollment.user_id == member_id, models.Enrollment.path_id == spath.id).first()
            if not existing_enrollment:
                encl = models.Enrollment(user_id=member_id, path_id=spath.id)
                db.add(encl)

    db.commit()
    db.refresh(team)

    return team
# Caminhos corrigidos para a raiz do projeto
root_uploads = os.path.join(os.path.dirname(__file__), "..", "uploads")
if not os.path.exists(root_uploads): os.makedirs(root_uploads)

app.mount("/uploads", StaticFiles(directory=root_uploads), name="uploads")
app.mount("/video", StaticFiles(directory=root_uploads), name="video")

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    # Mount everything else EXCEPT the root which is handled by serve_index
    app.mount("/", StaticFiles(directory=frontend_path, html=False), name="frontend")

if __name__ == "__main__":
    database.init_db()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
