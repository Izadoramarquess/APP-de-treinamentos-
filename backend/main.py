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

import models, database, auth

app = FastAPI(title="GeoTrilha LMS API")

# CORS Configuration
origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# ---------------- Admin: User Management ----------------
@app.get("/admin/users", response_model=List[models.UserSchema])
def list_users(db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin", "lideranca"]))):
    if current_user.role == "admin":
        return db.query(models.User).all()
    # Liderança só vê membros da própria equipe
    return db.query(models.User).filter(models.User.team_id == current_user.team_id).all()

@app.post("/admin/users/{user_id}/status")
def update_user_status(user_id: int, new_status: str = Form(None), role: str = Form(None), team_id: int = Form(None), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if new_status: user.status = new_status
    if role: user.role = role
    if team_id is not None: user.team_id = team_id if team_id != 0 else None
    db.commit()
    return {"message": "User updated"}

@app.post("/admin/users", response_model=models.UserSchema)
def create_user_admin(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("usuario"),
    team_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin", "lideranca"]))
):
    # Se for líder, força a equipe dele e a role 'usuario'
    if current_user.role == "lideranca":
        team_id = current_user.team_id
        role = "usuario"
    
    from auth import get_password_hash
    db_user = models.User(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        role=role,
        team_id=team_id,
        status="approved"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

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

# ---------------- Learning Paths ----------------
@app.get("/paths", response_model=List[models.LearningPathSchema])
def list_paths(db: Session = Depends(get_db)):
    return db.query(models.LearningPath).all()

@app.post("/paths", response_model=models.LearningPathSchema)
def create_path(title: str = Form(...), description: str = Form(""), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    path = models.LearningPath(title=title, description=description)
    db.add(path)
    db.commit()
    db.refresh(path)
    return path

# ---------------- Courses (Modules) ----------------
@app.post("/courses/upload/init")
def init_upload(filename: str, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    upload_dir = "uploads/temp"
    if not os.path.exists(upload_dir): os.makedirs(upload_dir)
    upload_id = str(uuid.uuid4())
    temp_file_path = os.path.join(upload_dir, f"{upload_id}_{filename}")
    with open(temp_file_path, "wb") as f: pass
    return {"upload_id": upload_id, "filename": filename}

@app.post("/courses/upload/chunk")
def upload_chunk(upload_id: str = Form(...), filename: str = Form(...), chunk_index: int = Form(...), chunk: UploadFile = File(...), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    temp_file_path = os.path.join("uploads/temp", f"{upload_id}_{filename}")
    if not os.path.exists(temp_file_path):
        raise HTTPException(status_code=404, detail="Upload init not found")
    with open(temp_file_path, "ab") as f:
        f.write(chunk.file.read())
    return {"status": "success", "chunk_index": chunk_index}

@app.post("/paths/{path_id}/courses", response_model=models.CourseSchema)
def create_course(
    path_id: int,
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

    course = models.Course(
        path_id=path_id,
        order=order,
        title=title, 
        description=description, 
        video_url=video_url,
        thumbnail_url=thumbnail_path,
        certificate_template_url=cert_path,
        validity_months=validity_months
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course

# ---------------- Streaming ----------------
def send_bytes_range_requests(file_obj, start: int, end: int, chunk_size: int = 10_000_000):
    with file_obj as f:
        f.seek(start)
        while (pos := f.tell()) <= end:
            read_size = min(chunk_size, end + 1 - pos)
            yield f.read(read_size)

@app.get("/video/{filename}")
def get_video(filename: str, range: str = Header(None)):
    video_path = os.path.join("uploads", filename)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video not found")
    file_size = os.stat(video_path).st_size

    if range is None:
        return StreamingResponse(open(video_path, "rb"), media_type="video/mp4")

    try:
        byte1, byte2 = 0, None
        match = range.replace("bytes=", "").split("-")
        if match[0]: byte1 = int(match[0])
        if len(match) > 1 and match[1]: byte2 = int(match[1])

        start = byte1
        end = byte2 if byte2 else file_size - 1
        if start >= file_size or end >= file_size or start > end:
            raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable")
        
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
            "Content-Type": "video/mp4",
        }
        return StreamingResponse(send_bytes_range_requests(open(video_path, "rb"), start, end), headers=headers, status_code=206)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Range Header")

# ---------------- Quizzes & Exams ----------------
@app.post("/courses/{course_id}/questions", response_model=models.QuestionSchema)
def add_question(
    course_id: int, 
    question_data: dict, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    db_question = models.Question(
        course_id=course_id,
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
def create_team(name: str = Form(...), description: str = Form(""), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    team = models.Team(name=name, description=description)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team
uploads_path = "uploads"
if not os.path.exists(uploads_path): os.makedirs(uploads_path)
app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    database.init_db()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
