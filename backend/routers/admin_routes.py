"""Administração: usuários, convites, equipes, matrículas, métricas do dashboard."""
import datetime
import os
import secrets
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

import models
import auth
import email_utils
from auth import get_password_hash
from deps import get_db, authorize, iso_utc, DEFAULT_DEPARTMENT

router = APIRouter()

# ---------------- Dashboard & Metrics ----------------
@router.get("/dashboard/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin", "lideranca"]))
):
    total_users    = db.query(models.User).filter(models.User.status == "ativo").count()
    pending_users  = db.query(models.User).filter(models.User.status == "pending").count()
    total_paths    = db.query(models.LearningPath).count()
    total_modules  = db.query(models.Module).count()
    completions    = db.query(models.ModuleProgress).filter(models.ModuleProgress.is_completed == True).count()
    pending_invites= db.query(models.User).filter(models.User.status == "convite_pendente").count()
    return {
        "total_users": total_users,
        "pending_users": pending_users,
        "total_paths": total_paths,
        "total_modules": total_modules,
        "completions": completions,
        "pending_invites": pending_invites
    }

# ---------------- Admin: User Management ----------------
@router.get("/admin/users", response_model=List[models.UserSchema])
def list_users(db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin", "lideranca"]))):
    if current_user.role == "admin":
        # Garante que o endpoint retorne TODOS os usuários, incluindo os com status 'pending'
        return db.query(models.User).all()
    # Liderança só vê membros da própria equipe
    return db.query(models.User).filter(models.User.team_id == current_user.team_id).all()

@router.post("/admin/users/{user_id}/status")
def update_user_status(user_id: int, new_status: str = Form(None), role: str = Form(None), team_id: int = Form(None), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if role == "admin" and not auth.is_allowed_email_domain(user.email):
        raise HTTPException(status_code=400, detail="Apenas e-mails corporativos @geobiogas.tech podem ser administradores.")
    if new_status: user.status = new_status
    if role: user.role = role
    # Time é obrigatório: 0/ausência de escolha vai para o time padrão, nunca para nulo.
    if team_id is not None: user.team_id = team_id if team_id != 0 else auth.get_default_team(db).id
    db.commit()
    return {"message": "User updated"}

@router.post("/admin/users/{user_id}/role")
def update_user_role(user_id: int, role: str = Form(...), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if role == "admin" and not auth.is_allowed_email_domain(user.email):
        raise HTTPException(status_code=400, detail="Apenas e-mails corporativos @geobiogas.tech podem ser administradores.")
    user.role = role
    db.commit()
    return {"message": "Role atualizado com sucesso"}

@router.post("/admin/users/{user_id}/reset-password")
def admin_reset_password(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = get_password_hash("Mudar@123")
    user.must_change_password = True

    # ✅ BUG 2 CORRIGIDO: garante que o usuário fique "ativo" ao ter senha resetada pelo admin,
    # pois o próprio ato de reset implica aprovação do acesso.
    if user.status in ["pending", "convite_pendente", "convite_expirado"]:
        user.status = "ativo"

    reset_token = secrets.token_urlsafe(32)
    user.reset_token = reset_token
    user.reset_token_expires = datetime.datetime.utcnow() + datetime.timedelta(hours=24)

    db.commit()

    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    reset_link = f"{base_url}/?view=reset&token={reset_token}"

    email_sent = email_utils.send_email(
        db, user.email, "Redefinição de senha — GeoTrilha",
        email_utils.render_template("reset_password.html", link_redefinicao=reset_link),
        "reset_password"
    )

    return {"reset_link": reset_link, "status_updated": user.status, "email_sent": email_sent}

@router.delete("/admin/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Você não pode excluir seu próprio usuário.")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Clean up dependent records
    db.query(models.Enrollment).filter(models.Enrollment.user_id == user.id).delete()
    db.query(models.ModuleProgress).filter(models.ModuleProgress.user_id == user.id).delete()
    db.query(models.Certificate).filter(models.Certificate.user_id == user.id).delete()

    # Unlink invited_by gracefully
    db.query(models.User).filter(models.User.invited_by_id == user.id).update({"invited_by_id": None})

    db.delete(user)
    db.commit()
    return {"message": "Usuário excluído com sucesso"}

@router.post("/admin/users/invite")
def invite_user_admin(
    username: str = Form(...),
    email: str = Form(...),
    role: str = Form("usuario"),
    department: Optional[str] = Form(None),
    team_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin", "lideranca"]))
):
    if current_user.role == "lideranca":
        team_id = current_user.team_id
        role = "usuario"

    if role == "admin" and not auth.is_allowed_email_domain(email):
        raise HTTPException(status_code=400, detail="Apenas e-mails corporativos @geobiogas.tech podem ser administradores.")

    existing_user = db.query(models.User).filter(models.User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado no sistema.")

    invite_token = secrets.token_urlsafe(32)

    db_user = models.User(
        username=username,
        email=email,
        hashed_password=get_password_hash(uuid.uuid4().hex),
        role=role,
        department=(department or "").strip() or DEFAULT_DEPARTMENT,
        team_id=team_id if team_id else auth.get_default_team(db).id,
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

    email_sent = email_utils.send_email(
        db, email, "Convite — Plataforma GeoTrilha",
        email_utils.render_template("invite_generic.html", link_convite=invite_link),
        "invite"
    )

    return {"invite_link": invite_link, "email_sent": email_sent}

@router.post("/enrollments", response_model=models.EnrollmentSchema)
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

@router.post("/admin/users/{user_id}/resend_invite")
def resend_invite(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin", "lideranca"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)

    # Validação para liderança
    if current_user.role == "lideranca" and user.team_id != current_user.team_id:
        raise HTTPException(status_code=403, detail="Você só pode reenviar convites para membros da sua própria equipe.")

    if not auth.is_allowed_email_domain(user.email): raise HTTPException(status_code=400, detail="Domínio inválido.")

    invite_token = secrets.token_urlsafe(32)
    user.invite_token = invite_token
    user.invite_expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    user.status = "convite_pendente"
    user.invited_by_id = current_user.id
    db.commit()

    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    invite_link = f"{base_url}/?view=convite&token={invite_token}"

    email_sent = email_utils.send_email(
        db, user.email, "Convite — Plataforma GeoTrilha",
        email_utils.render_template("invite_generic.html", link_convite=invite_link),
        "invite"
    )

    return {"message": "Reenviado com sucesso", "invite_link": invite_link, "email_sent": email_sent}

@router.post("/admin/users/{user_id}/cancel_invite")
def cancel_invite(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)
    user.invite_token = None
    user.status = "convite_expirado"
    db.commit()
    return {"message": "Cancelado"}

@router.post("/admin/users/{user_id}/activate_manual")
def activate_manual(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)
    user.status = "ativo"
    db.commit()
    return {"message": "Ativado"}

@router.post("/admin/users/{user_id}/remove_team")
def remove_team(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)
    user.team_id = auth.get_default_team(db).id  # Time é obrigatório: volta para o time padrão em vez de nulo.
    if user.role == "lideranca": user.role = "usuario"
    db.commit()
    return {"message": "Removido"}

@router.get("/admin/invites")
def list_invites(db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin", "lideranca"]))):
    query = db.query(models.User)
    if current_user.role != "admin":
        # Liderança só vê convites/usuários da própria equipe (mesmo filtro de list_users).
        query = query.filter(models.User.team_id == current_user.team_id)
    users = query.all()
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
            "invite_date": iso_utc(u.invite_expires_at - datetime.timedelta(days=7)) if u.invite_expires_at else None,
            "last_email_date": iso_utc(last_log.sent_at) if last_log else None,
            "last_email_status": last_log.status if last_log else None
        })
    return out

# ---------------- Teams ----------------
@router.get("/teams", response_model=List[models.TeamSchema])
def list_teams(db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin", "lideranca"]))):
    return db.query(models.Team).all()

@router.post("/teams", response_model=models.TeamSchema)
def create_team(name: str = Form(...), description: str = Form(""), emails: str = Form(""), team_admin_email: str = Form(...), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    if not auth.is_allowed_email_domain(team_admin_email):
        raise HTTPException(status_code=400, detail="Apenas e-mails corporativos @geobiogas.tech podem ser administradores.")

    team = models.Team(name=name, description=description)
    db.add(team)
    db.commit()
    db.refresh(team)

    # Calculado antes do dispatch para poder citar nos e-mails de convite/aviso.
    standard_paths = db.query(models.LearningPath).filter(models.LearningPath.is_standard_training == True).all()
    training_names = ", ".join(p.title for p in standard_paths) or "nenhum treinamento obrigatório definido ainda"
    base_url = os.getenv("BASE_URL", "http://localhost:8000")

    team_members_ids = []

    def dispatch_team_member(email_addr, is_admin):
        if not auth.is_allowed_email_domain(email_addr):
            raise HTTPException(status_code=400, detail="Apenas usuários com e-mail corporativo @geobiogas.tech podem acessar a plataforma.")
        user = db.query(models.User).filter(models.User.email == email_addr).first()
        if user:
            # BUG 3 CORRIGIDO: admin é o papel mais alto — nunca pode ser vinculado como membro de equipe
            if user.role == "admin":
                return  # ignora silenciosamente sem erro
            user.team_id = team.id
            if is_admin: user.role = "lideranca"
            team_members_ids.append(user.id)
            db.commit()  # persiste o novo team_id antes do e-mail sair (send_email também comita, mas é bom deixar explícito aqui)
            email_utils.send_email(
                db, user.email, f"Você foi adicionado à equipe {team.name} — GeoTrilha",
                email_utils.render_template("team_added.html", nome_equipe=team.name, lista_treinamentos=training_names),
                "team_added"
            )
        else:
            random_pass = uuid.uuid4().hex
            invite_t = secrets.token_urlsafe(32)
            new_user = models.User(
                username=email_addr,
                email=email_addr,
                hashed_password=get_password_hash(random_pass),
                role="lideranca" if is_admin else "usuario",
                status="convite_pendente",
                department=DEFAULT_DEPARTMENT,
                team_id=team.id,
                invite_token=invite_t,
                invite_expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
                invited_by_id=current_user.id
            )
            db.add(new_user)
            db.flush()
            team_members_ids.append(new_user.id)
            invite_link = f"{base_url}/?view=convite&token={invite_t}"
            email_utils.send_email(
                db, email_addr, f"Convite — Equipe {team.name} na GeoTrilha",
                email_utils.render_template("invite.html", nome_equipe=team.name, lista_treinamentos=training_names, link_convite=invite_link),
                "invite"
            )

    dispatch_team_member(team_admin_email, True)

    if emails:
        email_list = [e.strip() for e in emails.split(",") if e.strip()]
        for email in email_list:
            if email == team_admin_email: continue
            dispatch_team_member(email, False)

    # Matricula os membros nos treinamentos padrão
    for spath in standard_paths:
        for member_id in team_members_ids:
            existing_enrollment = db.query(models.Enrollment).filter(models.Enrollment.user_id == member_id, models.Enrollment.path_id == spath.id).first()
            if not existing_enrollment:
                encl = models.Enrollment(user_id=member_id, path_id=spath.id)
                db.add(encl)

    db.commit()
    db.refresh(team)

    return team
