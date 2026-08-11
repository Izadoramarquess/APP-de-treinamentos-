"""Catálogo: cursos e módulos (sem "Trilha" por cima — Curso é o nível de
topo) e upload de vídeo/materiais."""
import os
import shutil
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

import models
from deps import (
    get_db, authorize,
    UPLOADS_DIR, ALLOWED_VIDEO_EXT, ALLOWED_IMAGE_EXT, MAX_UPLOAD_BYTES,
    sanitize_filename, safe_filename, check_upload_size,
)

router = APIRouter()

# ---------------- Courses ----------------
@router.get("/courses", response_model=List[models.CourseSchema])
def list_courses(db: Session = Depends(get_db)):
    return db.query(models.Course).order_by(models.Course.order).all()

@router.post("/courses", response_model=models.CourseSchema)
def create_course(
    title: str = Form(...),
    description: str = Form(""),
    order: int = Form(1),
    is_standard_training: bool = Form(False),
    validity_months: int = Form(None),
    certificate_template: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    cert_path = None
    if certificate_template and certificate_template.filename:
        check_upload_size(certificate_template.size or 0)
        cert_filename = f"cert_tpl_{safe_filename(certificate_template.filename, ALLOWED_IMAGE_EXT)}"
        with open(os.path.join(UPLOADS_DIR, cert_filename), "wb") as buffer:
            shutil.copyfileobj(certificate_template.file, buffer)
        cert_path = f"/uploads/{cert_filename}"

    course = models.Course(
        title=title, description=description, order=order,
        is_standard_training=is_standard_training,
        validity_months=validity_months,
        certificate_template_url=cert_path,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course

@router.put("/courses/{course_id}", response_model=models.CourseSchema)
def update_course(
    course_id: int,
    title: str = Form(...),
    description: str = Form(""),
    order: int = Form(1),
    is_standard_training: bool = Form(False),
    validity_months: int = Form(None),
    certificate_template: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso não encontrado")
    course.title = title
    course.description = description
    course.order = order
    course.is_standard_training = is_standard_training
    course.validity_months = validity_months

    if certificate_template and certificate_template.filename:
        check_upload_size(certificate_template.size or 0)
        cert_filename = f"cert_tpl_{safe_filename(certificate_template.filename, ALLOWED_IMAGE_EXT)}"
        with open(os.path.join(UPLOADS_DIR, cert_filename), "wb") as buffer:
            shutil.copyfileobj(certificate_template.file, buffer)
        course.certificate_template_url = f"/uploads/{cert_filename}"

    db.commit()
    db.refresh(course)
    return course

@router.delete("/courses/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Curso não encontrado")
    # Antes isso era responsabilidade do delete_path (que não existe mais) — o
    # Curso é o nível de topo agora, então ele mesmo limpa matrícula/certificado.
    db.query(models.Enrollment).filter(models.Enrollment.course_id == course_id).delete()
    db.query(models.Certificate).filter(models.Certificate.course_id == course_id).delete()
    for module in db.query(models.Module).filter(models.Module.course_id == course.id).all():
        delete_module(module.id, db, current_user)
    db.delete(course)
    db.commit()
    return {"message": "Curso excluído com sucesso"}

# ---------------- Modules ----------------
@router.get("/courses/{course_id}/modules", response_model=List[models.ModuleSchema])
def list_modules(course_id: int, db: Session = Depends(get_db)):
    return db.query(models.Module).filter(models.Module.course_id == course_id).order_by(models.Module.order).all()

@router.post("/modules/upload/init")
def init_upload(filename: str, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    safe_name = sanitize_filename(filename, ALLOWED_VIDEO_EXT)
    upload_dir = os.path.join(UPLOADS_DIR, "temp")
    os.makedirs(upload_dir, exist_ok=True)
    upload_id = str(uuid.uuid4())
    temp_file_path = os.path.join(upload_dir, f"{upload_id}_{safe_name}")
    with open(temp_file_path, "wb") as f: pass
    return {"upload_id": upload_id, "filename": safe_name}

@router.post("/modules/upload/chunk")
def upload_chunk(upload_id: str = Form(...), filename: str = Form(...), chunk_index: int = Form(...), chunk: UploadFile = File(...), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    safe_name = sanitize_filename(filename, ALLOWED_VIDEO_EXT)
    temp_file_path = os.path.join(UPLOADS_DIR, "temp", f"{upload_id}_{safe_name}")
    if not os.path.exists(temp_file_path):
        raise HTTPException(status_code=404, detail="Upload init not found")
    if os.path.getsize(temp_file_path) + chunk.size > MAX_UPLOAD_BYTES:
        os.remove(temp_file_path)
        raise HTTPException(status_code=413, detail=f"Arquivo excede o limite de {MAX_UPLOAD_BYTES // (1024*1024)}MB.")
    with open(temp_file_path, "ab") as f:
        f.write(chunk.file.read())
    return {"status": "success", "chunk_index": chunk_index}

@router.post("/courses/{course_id}/modules", response_model=models.ModuleSchema)
def create_module(
    course_id: int,
    title: str = Form(None),
    description: str = Form(""),
    order: int = Form(1),
    upload_id: str = Form(None),
    filename: str = Form(None),
    video: UploadFile = File(None),
    thumbnail: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    video_url = None
    final_dir = UPLOADS_DIR

    # Upload direto de arquivo de vídeo
    if video and video.filename:
        check_upload_size(video.size or 0)
        video_filename = safe_filename(video.filename, ALLOWED_VIDEO_EXT)
        video_path = os.path.join(final_dir, video_filename)
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
        video_url = f"/video/{video_filename}"

    # Upload via chunked (sobrescreve se os dois forem enviados)
    if upload_id and filename:
        safe_name = sanitize_filename(filename, ALLOWED_VIDEO_EXT)
        temp_file_path = os.path.join(UPLOADS_DIR, "temp", f"{upload_id}_{safe_name}")
        if os.path.exists(temp_file_path):
            final_filename = f"{upload_id}_{safe_name}"
            final_file_path = os.path.join(final_dir, final_filename)
            shutil.move(temp_file_path, final_file_path)
            video_url = f"/video/{final_filename}"

    thumbnail_path = None
    if thumbnail and thumbnail.filename:
        check_upload_size(thumbnail.size or 0)
        thumbnail_filename = f"thumb_{safe_filename(thumbnail.filename, ALLOWED_IMAGE_EXT)}"
        with open(os.path.join(final_dir, thumbnail_filename), "wb") as buffer:
            shutil.copyfileobj(thumbnail.file, buffer)
        thumbnail_path = f"/uploads/{thumbnail_filename}"

    # Título é opcional — sem ele, vira "Módulo N" (menos um campo pra
    # preencher em toda pergunta ao subir vários vídeos em sequência).
    final_title = (title or "").strip() or f"Módulo {order}"

    module = models.Module(
        course_id=course_id,
        order=order,
        title=final_title,
        description=description,
        video_url=video_url,
        thumbnail_url=thumbnail_path,
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    return module

@router.put("/modules/{module_id}", response_model=models.ModuleSchema)
def update_module(
    module_id: int,
    title: str = Form(None),
    description: str = Form(""),
    order: int = Form(1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    module = db.query(models.Module).filter(models.Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Módulo não encontrado")

    module.title = (title or "").strip() or f"Módulo {order}"
    module.description = description
    module.order = order

    db.commit()
    db.refresh(module)
    return module

@router.delete("/modules/{module_id}")
def delete_module(module_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    module = db.query(models.Module).filter(models.Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Módulo não encontrado")

    db.query(models.Question).filter(models.Question.module_id == module.id).delete()
    db.query(models.Material).filter(models.Material.module_id == module.id).delete()
    db.query(models.ModuleProgress).filter(models.ModuleProgress.module_id == module.id).delete()

    db.delete(module)
    db.commit()
    return {"message": "Módulo excluído com sucesso"}
