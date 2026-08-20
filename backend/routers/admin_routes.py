"""Administração: usuários, convites, equipes, matrículas, métricas do dashboard."""
import datetime
import os
import secrets
import shutil
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

import models
import auth
import email_utils
from auth import get_password_hash
from deps import (
    get_db, authorize, iso_utc, DEFAULT_DEPARTMENT, check_upload_size, resolve_company_id, check_same_company,
    ALLOWED_IMAGE_EXT, safe_filename, UPLOADS_DIR, get_led_team_ids, ensure_leader_has_team,
)

router = APIRouter()

# ---------------- Dashboard & Metrics ----------------
@router.get("/dashboard/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin", "lideranca"]))
):
    users_q    = db.query(models.User).filter(models.User.status == "ativo")
    pending_q  = db.query(models.User).filter(models.User.status == "pending")
    courses_q  = db.query(models.Course)
    modules_q  = db.query(models.Module).join(models.Course)
    certs_q    = db.query(models.Certificate).join(models.Course)
    invites_q  = db.query(models.User).filter(models.User.status == "convite_pendente")
    if current_user.role == "admin":
        users_q   = users_q.filter(models.User.company_id == current_user.company_id)
        pending_q = pending_q.filter(models.User.company_id == current_user.company_id)
        invites_q = invites_q.filter(models.User.company_id == current_user.company_id)
    elif current_user.role == "lideranca":
        # Mesmo recorte de list_users: liderança só vê as equipes que lidera.
        led_ids = get_led_team_ids(db, current_user.id)
        users_q   = users_q.filter(models.User.team_id.in_(led_ids))
        pending_q = pending_q.filter(models.User.team_id.in_(led_ids))
        invites_q = invites_q.filter(models.User.team_id.in_(led_ids))
    if current_user.role != "super_admin":
        # Cursos/módulos/certificados nunca são vistos fora da própria empresa,
        # nem por admin nem por liderança (não são recortados por equipe).
        courses_q = courses_q.filter(models.Course.company_id == current_user.company_id)
        modules_q = modules_q.filter(models.Course.company_id == current_user.company_id)
        certs_q   = certs_q.filter(models.Course.company_id == current_user.company_id)
    return {
        "total_users": users_q.count(),
        "pending_users": pending_q.count(),
        "total_courses": courses_q.count(),
        "total_modules": modules_q.count(),
        # Progresso é medido em curso concluído (certificado emitido), não em
        # módulo assistido — um curso só "conta" quando termina de verdade.
        "courses_completed": certs_q.count(),
        "pending_invites": invites_q.count()
    }

@router.get("/dashboard/certificates-monthly")
def certificates_monthly(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin", "lideranca"]))
):
    """Certificados emitidos nos últimos 6 meses, um balde por mês — sempre
    os 6 meses, com 0 explícito onde não teve nenhum (série de tamanho
    fixo pro gráfico, não esparsa). Agrupa em Python em vez de usar função
    de data do banco pra não depender de SQLite vs Postgres se comportarem
    igual (já tivemos diferença entre os dois nesta mesma base de código)."""
    today = datetime.date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    months.reverse()
    range_start = datetime.datetime(months[0][0], months[0][1], 1)

    certs_q = db.query(models.Certificate).join(models.Course).filter(models.Certificate.issued_at >= range_start)
    if current_user.role == "lideranca":
        led_ids = get_led_team_ids(db, current_user.id)
        certs_q = certs_q.join(models.User, models.User.id == models.Certificate.user_id).filter(models.User.team_id.in_(led_ids))
    elif current_user.role != "super_admin":
        certs_q = certs_q.filter(models.Course.company_id == current_user.company_id)

    counts = {ym: 0 for ym in months}
    for cert in certs_q.all():
        key = (cert.issued_at.year, cert.issued_at.month)
        if key in counts:
            counts[key] += 1

    meses_pt = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    return {
        "labels": [f"{meses_pt[m]}/{str(y)[2:]}" for (y, m) in months],
        "values": [counts[ym] for ym in months]
    }

# ---------------- Admin: User Management ----------------
def _attach_led_team_ids(db: Session, users: List[models.User]) -> List[models.User]:
    """Anexa led_team_ids (não é coluna, é lido à parte) em cada User antes
    de servir como UserSchema — só busca no banco se algum for líder."""
    leader_ids = [u.id for u in users if u.role == "lideranca"]
    leader_map = {}
    if leader_ids:
        for tl in db.query(models.TeamLeader).filter(models.TeamLeader.user_id.in_(leader_ids)).all():
            leader_map.setdefault(tl.user_id, []).append(tl.team_id)
    for u in users:
        u.led_team_ids = leader_map.get(u.id, [])
    return users

@router.get("/admin/users", response_model=List[models.UserSchema])
def list_users(db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin", "lideranca"]))):
    if current_user.role == "super_admin":
        users = db.query(models.User).all()
    elif current_user.role == "admin":
        # Garante que o endpoint retorne TODOS os usuários da empresa, incluindo os com status 'pending'
        users = db.query(models.User).filter(models.User.company_id == current_user.company_id).all()
    else:
        # Liderança vê membros de toda equipe que lidera
        users = db.query(models.User).filter(models.User.team_id.in_(get_led_team_ids(db, current_user.id))).all()
    return _attach_led_team_ids(db, users)

@router.post("/admin/users/{user_id}/status")
def update_user_status(user_id: int, new_status: str = Form(None), role: str = Form(None), team_id: int = Form(None), db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    check_same_company(current_user, user.company_id, "usuário")
    if role == "admin" and not auth.is_allowed_email_domain(user.email):
        raise HTTPException(status_code=400, detail="Apenas e-mails corporativos @geobiogas.tech podem ser administradores.")
    if new_status: user.status = new_status
    if role: user.role = role
    # Time é obrigatório: 0/ausência de escolha vai para o time padrão, nunca para nulo.
    if team_id is not None:
        if team_id != 0:
            team = db.query(models.Team).filter(models.Team.id == team_id).first()
            if not team or team.company_id != user.company_id:
                raise HTTPException(status_code=404, detail="Equipe não encontrada")
            user.team_id = team.id
        else:
            user.team_id = auth.get_default_team(db, user.company_id).id
    db.commit()
    # Esse endpoint também pode promover a lideranca (via o campo role acima)
    # sem passar pela tela dedicada de "equipes lideradas" — sem isso, virava
    # um segundo jeito de criar um líder sem nenhuma equipe atribuída.
    ensure_leader_has_team(db, user)
    return {"message": "User updated"}

@router.post("/admin/users/{user_id}/role")
def update_user_role(
    user_id: int,
    role: str = Form(...),
    team_id: Optional[int] = Form(None),
    company_id: Optional[int] = Form(None),
    led_team_ids: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    check_same_company(current_user, user.company_id, "usuário")
    if role == "admin" and not auth.is_allowed_email_domain(user.email):
        raise HTTPException(status_code=400, detail="Apenas e-mails corporativos @geobiogas.tech podem ser administradores.")
    # Só super_admin move gente entre empresas — um admin comum nunca deve
    # conseguir tirar alguém da própria empresa nem "roubar" de outra.
    if company_id and current_user.role == "super_admin" and company_id != user.company_id:
        company = db.query(models.Company).filter(models.Company.id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Empresa não encontrada")
        user.company_id = company_id
        # O time antigo pertence à empresa anterior — se nenhum time novo
        # vier explícito abaixo, cai no time padrão da empresa nova.
        user.team_id = auth.get_default_team(db, company_id).id
    user.role = role
    # team_id vem vazio quando a opção selecionada é "Sem Equipe (padrão)" —
    # cai no mesmo time padrão usado em qualquer outro fluxo (convite, etc.),
    # nunca fica sem time (Time é obrigatório em User).
    if team_id:
        team = db.query(models.Team).filter(models.Team.id == team_id).first()
        if not team or team.company_id != user.company_id:
            raise HTTPException(status_code=404, detail="Equipe não encontrada")
        user.team_id = team.id
    else:
        user.team_id = auth.get_default_team(db, user.company_id).id

    # Equipes lideradas — separado da equipe-base (team_id) acima, porque
    # um líder pode liderar mais de uma. Só mexe nisso se o papel final for
    # lideranca; virou outro papel, perde toda liderança (simétrico ao que
    # remove_team já faz ao tirar alguém da equipe).
    if role == "lideranca":
        if led_team_ids is not None:
            ids = [int(x) for x in led_team_ids.split(",") if x.strip()]
            valid_teams = db.query(models.Team).filter(models.Team.id.in_(ids), models.Team.company_id == user.company_id).all()
            if len(valid_teams) != len(ids):
                raise HTTPException(status_code=400, detail="Uma ou mais equipes não pertencem à empresa do usuário.")
            db.query(models.TeamLeader).filter(models.TeamLeader.user_id == user.id).delete()
            for tid in ids:
                db.add(models.TeamLeader(user_id=user.id, team_id=tid))
    else:
        db.query(models.TeamLeader).filter(models.TeamLeader.user_id == user.id).delete()

    db.commit()
    ensure_leader_has_team(db, user)
    return {"message": "Role atualizado com sucesso"}

@router.post("/admin/users/{user_id}/reset-password")
def admin_reset_password(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    check_same_company(current_user, user.company_id, "usuário")
    user.hashed_password = get_password_hash(auth.TEMP_PASSWORD)
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
    check_same_company(current_user, user.company_id, "usuário")

    # Clean up dependent records
    db.query(models.Enrollment).filter(models.Enrollment.user_id == user.id).delete()
    db.query(models.ModuleProgress).filter(models.ModuleProgress.user_id == user.id).delete()
    db.query(models.Certificate).filter(models.Certificate.user_id == user.id).delete()
    db.query(models.QuestionAttempt).filter(models.QuestionAttempt.user_id == user.id).delete()
    db.query(models.TeamLeader).filter(models.TeamLeader.user_id == user.id).delete()

    # Unlink invited_by gracefully
    db.query(models.User).filter(models.User.invited_by_id == user.id).update({"invited_by_id": None})

    db.delete(user)
    db.commit()
    return {"message": "Usuário excluído com sucesso"}

def _create_invite_record(db: Session, username: str, email: str, role: str, department: Optional[str], team_id: Optional[int], invited_by_id: int, company_id: int) -> dict:
    """Núcleo compartilhado entre o convite avulso (/admin/users/invite) e a
    importação em lote (/admin/users/bulk-invite) — mesma validação, mesmo
    e-mail, um único lugar pra manter certo."""
    if role == "admin" and not auth.is_allowed_email_domain(email):
        raise ValueError("Apenas e-mails corporativos @geobiogas.tech podem ser administradores.")

    existing_user = db.query(models.User).filter(models.User.email == email).first()
    if existing_user:
        raise ValueError("E-mail já cadastrado no sistema.")

    if team_id:
        team = db.query(models.Team).filter(models.Team.id == team_id).first()
        if not team or team.company_id != company_id:
            raise ValueError("Equipe não encontrada nesta empresa.")

    invite_token = secrets.token_urlsafe(32)
    db_user = models.User(
        username=username,
        email=email,
        hashed_password=get_password_hash(uuid.uuid4().hex),
        role=role,
        department=(department or "").strip() or DEFAULT_DEPARTMENT,
        team_id=team_id if team_id else auth.get_default_team(db, company_id).id,
        company_id=company_id,
        status="convite_pendente",
        invite_token=invite_token,
        invite_expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
        invited_by_id=invited_by_id
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


@router.post("/admin/users/invite")
def invite_user_admin(
    username: str = Form(...),
    email: str = Form(...),
    role: str = Form("usuario"),
    department: Optional[str] = Form(None),
    team_id: Optional[int] = Form(None),
    company_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin", "lideranca"]))
):
    if current_user.role == "lideranca":
        led_ids = get_led_team_ids(db, current_user.id)
        if team_id is not None and team_id not in led_ids:
            raise HTTPException(status_code=403, detail="Você só pode convidar para uma equipe que você lidera.")
        if team_id is None:
            if len(led_ids) == 1:
                team_id = led_ids[0]
            else:
                raise HTTPException(status_code=400, detail="Você lidera mais de uma equipe — informe para qual delas é o convite.")
        role = "usuario"
    resolved_company_id = resolve_company_id(current_user, company_id)
    try:
        return _create_invite_record(db, username, email, role, department, team_id, current_user.id, resolved_company_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/users/bulk-invite")
async def bulk_invite_users(
    file: UploadFile = File(...),
    company_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    """CSV com colunas username,email,department,role,team (team e role são
    opcionais — role vira 'usuario' e team vira a equipe padrão se vazios).
    Processa linha a linha; uma linha com erro não derruba as outras."""
    import csv
    import io

    resolved_company_id = resolve_company_id(current_user, company_id)
    check_upload_size(file.size or 0)
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    required_cols = {"username", "email"}
    if not reader.fieldnames or not required_cols.issubset({f.strip().lower() for f in reader.fieldnames}):
        raise HTTPException(status_code=400, detail="CSV precisa ter, no mínimo, as colunas: username,email")

    # Escopado por empresa — nome de time não é mais globalmente único, então
    # resolver só por nome colidiria entre empresas diferentes.
    teams_by_name = {t.name.strip().lower(): t.id for t in db.query(models.Team).filter(models.Team.company_id == resolved_company_id).all()}
    results = []
    for i, row in enumerate(reader, start=2):  # linha 1 é o cabeçalho
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        username = row.get("username", "")
        email = row.get("email", "")
        if not username or not email:
            results.append({"line": i, "email": email or "—", "status": "erro", "detail": "username e email são obrigatórios"})
            continue
        role = row.get("role") or "usuario"
        team_id = teams_by_name.get((row.get("team") or "").strip().lower())
        try:
            invite = _create_invite_record(db, username, email, role, row.get("department"), team_id, current_user.id, resolved_company_id)
            results.append({"line": i, "email": email, "status": "ok", "invite_link": invite["invite_link"], "email_sent": invite["email_sent"]})
        except ValueError as e:
            results.append({"line": i, "email": email, "status": "erro", "detail": str(e)})

    ok_count = sum(1 for r in results if r["status"] == "ok")
    return {"total": len(results), "created": ok_count, "errors": len(results) - ok_count, "results": results}

@router.post("/enrollments", response_model=models.EnrollmentSchema)
def enroll_user(
    user_id: int = Form(...),
    course_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin", "lideranca"]))
):
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user: raise HTTPException(status_code=404, detail="User not found")
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course: raise HTTPException(status_code=404, detail="Curso não encontrado")

    # Validação de equipe e empresa para líderes — curso também precisa ser
    # da mesma empresa do líder, senão dava pra matricular em curso alheio
    # informando o course_id de outra empresa direto na API.
    if current_user.role == "lideranca" and (target_user.team_id not in get_led_team_ids(db, current_user.id) or course.company_id != current_user.company_id):
        raise HTTPException(status_code=403, detail="Você só pode atribuir cursos da sua empresa a membros da sua equipe.")
    # Validação de empresa para admin — nem usuário nem curso podem ser de outra empresa.
    if current_user.role == "admin" and (target_user.company_id != current_user.company_id or course.company_id != current_user.company_id):
        raise HTTPException(status_code=403, detail="Você só pode atribuir cursos da sua empresa a usuários da sua empresa.")

    enrollment = models.Enrollment(user_id=user_id, course_id=course_id)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment

@router.post("/admin/users/{user_id}/resend_invite")
def resend_invite(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin", "lideranca"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)

    # Validação para liderança
    if current_user.role == "lideranca" and user.team_id not in get_led_team_ids(db, current_user.id):
        raise HTTPException(status_code=403, detail="Você só pode reenviar convites para membros da sua própria equipe.")
    check_same_company(current_user, user.company_id, "usuário")

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
    check_same_company(current_user, user.company_id, "usuário")
    user.invite_token = None
    user.status = "convite_expirado"
    db.commit()
    return {"message": "Cancelado"}

@router.post("/admin/users/{user_id}/activate_manual")
def activate_manual(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)
    check_same_company(current_user, user.company_id, "usuário")
    user.status = "ativo"
    db.commit()
    return {"message": "Ativado"}

@router.post("/admin/users/{user_id}/remove_team")
def remove_team(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin"]))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404)
    check_same_company(current_user, user.company_id, "usuário")
    user.team_id = auth.get_default_team(db, user.company_id).id  # Time é obrigatório: volta para o time padrão em vez de nulo.
    if user.role == "lideranca":
        user.role = "usuario"
        db.query(models.TeamLeader).filter(models.TeamLeader.user_id == user.id).delete()
    db.commit()
    return {"message": "Removido"}

@router.get("/admin/invites")
def list_invites(db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin", "lideranca"]))):
    query = db.query(models.User)
    if current_user.role == "admin":
        query = query.filter(models.User.company_id == current_user.company_id)
    elif current_user.role != "super_admin":
        # Liderança só vê convites/usuários da própria equipe (mesmo filtro de list_users).
        query = query.filter(models.User.team_id.in_(get_led_team_ids(db, current_user.id)))
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

def _attach_team_leaders(db: Session, teams: List[models.Team]) -> List[models.Team]:
    """Anexa leaders (não é coluna, é lido à parte) em cada Team antes de
    servir como TeamSchema."""
    if not teams:
        return teams
    rows = db.query(models.TeamLeader, models.User).join(
        models.User, models.User.id == models.TeamLeader.user_id
    ).filter(models.TeamLeader.team_id.in_([t.id for t in teams])).all()
    leaders_map = {}
    for tl, u in rows:
        leaders_map.setdefault(tl.team_id, []).append(u)
    for t in teams:
        t.leaders = leaders_map.get(t.id, [])
    return teams

# ---------------- Teams ----------------
@router.get("/teams", response_model=List[models.TeamSchema])
def list_teams(db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["admin", "lideranca"]))):
    if current_user.role == "super_admin":
        teams = db.query(models.Team).all()
    else:
        # admin e liderança só veem as equipes da própria empresa — antes deste
        # endpoint não filtrava nada, nem por empresa nem por qualquer outro critério.
        # (liderança continua vendo TODAS as equipes da empresa, não só as que
        # lidera — usado pra escolher em qual das próprias equipes matricular
        # alguém e pro filtro "Líder" do admin; não é sobra, é dependência.)
        teams = db.query(models.Team).filter(models.Team.company_id == current_user.company_id).all()
    return _attach_team_leaders(db, teams)

@router.post("/teams")
def create_team(
    name: str = Form(...),
    description: str = Form(""),
    emails: str = Form(""),
    team_admin_email: str = Form(...),
    company_id: Optional[int] = Form(None),
    move_home_team: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["admin"]))
):
    if not auth.is_allowed_email_domain(team_admin_email):
        raise HTTPException(status_code=400, detail="Apenas e-mails corporativos @geobiogas.tech podem ser administradores.")

    resolved_company_id = resolve_company_id(current_user, company_id)

    # Nome de equipe não é mais globalmente único, mas continua único dentro
    # da mesma empresa.
    existing_team = db.query(models.Team).filter(models.Team.name == name, models.Team.company_id == resolved_company_id).first()
    if existing_team:
        raise HTTPException(status_code=400, detail="Já existe uma equipe com esse nome nesta empresa.")

    team = models.Team(name=name, description=description, company_id=resolved_company_id)
    db.add(team)
    db.commit()
    db.refresh(team)

    # Calculado antes do dispatch para poder citar nos e-mails de convite/aviso.
    standard_courses = db.query(models.Course).filter(
        models.Course.is_standard_training == True,
        models.Course.company_id == resolved_company_id
    ).all()
    training_names = ", ".join(c.title for c in standard_courses) or "nenhum treinamento obrigatório definido ainda"
    base_url = os.getenv("BASE_URL", "http://localhost:8000")

    team_members_ids = []
    result_state = {"home_team_changed": False}

    def dispatch_team_member(email_addr, is_admin):
        if not auth.is_allowed_email_domain(email_addr):
            raise HTTPException(status_code=400, detail="Apenas usuários com e-mail corporativo @geobiogas.tech podem acessar a plataforma.")
        user = db.query(models.User).filter(models.User.email == email_addr).first()
        if user:
            # BUG 3 CORRIGIDO: admin/super_admin são os papéis mais altos — nunca podem ser vinculados como membro de equipe
            if user.role in ("admin", "super_admin"):
                return  # ignora silenciosamente sem erro
            # Pessoa já pertence a outra empresa — não realoca silenciosamente,
            # isso mudaria a empresa dela sem ninguém ter pedido isso de propósito.
            if user.company_id != resolved_company_id:
                raise HTTPException(status_code=400, detail=f"{email_addr} já pertence a outra empresa.")
            if is_admin:
                user.role = "lideranca"
                # Só move a equipe-base (team_id) se a pessoa ainda não tinha
                # nenhuma de verdade (estava na "Sem Equipe" padrão) — senão,
                # liderar essa equipe nova não deve tirar a pessoa da equipe
                # que já era dela. move_home_team força a troca mesmo assim.
                default_team = auth.get_default_team(db, resolved_company_id)
                if user.team_id == default_team.id or move_home_team:
                    user.team_id = team.id
                    result_state["home_team_changed"] = True
                    team_members_ids.append(user.id)
                already_leader = db.query(models.TeamLeader).filter(
                    models.TeamLeader.user_id == user.id, models.TeamLeader.team_id == team.id
                ).first()
                if not already_leader:
                    db.add(models.TeamLeader(user_id=user.id, team_id=team.id))
            else:
                user.team_id = team.id
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
                company_id=resolved_company_id,
                invite_token=invite_t,
                invite_expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
                invited_by_id=current_user.id
            )
            db.add(new_user)
            db.flush()
            team_members_ids.append(new_user.id)
            result_state["home_team_changed"] = True
            if is_admin:
                db.add(models.TeamLeader(user_id=new_user.id, team_id=team.id))
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

    # Matricula os membros nos treinamentos padrão (só os da própria empresa)
    for scourse in standard_courses:
        for member_id in team_members_ids:
            existing_enrollment = db.query(models.Enrollment).filter(models.Enrollment.user_id == member_id, models.Enrollment.course_id == scourse.id).first()
            if not existing_enrollment:
                encl = models.Enrollment(user_id=member_id, course_id=scourse.id)
                db.add(encl)

    db.commit()
    db.refresh(team)
    _attach_team_leaders(db, [team])

    return {**models.TeamSchema.model_validate(team).model_dump(), "home_team_changed": result_state["home_team_changed"]}

# ---------------- Empresas (super_admin) ----------------
@router.get("/companies", response_model=List[models.CompanySchema])
def list_companies(db: Session = Depends(get_db), current_user: models.User = Depends(authorize(["super_admin"]))):
    return db.query(models.Company).order_by(models.Company.name).all()

@router.get("/companies/public")
def list_companies_public(db: Session = Depends(get_db)):
    """Só id+nome, sem exigir login — usado pela tela de autocadastro
    público e pela tela de convite, onde a pessoa escolhe a própria empresa."""
    return [{"id": c.id, "name": c.name} for c in db.query(models.Company).order_by(models.Company.name).all()]

@router.post("/companies", response_model=models.CompanySchema)
def create_company(
    name: str = Form(...),
    logo: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["super_admin"]))
):
    logo_path = None
    if logo and logo.filename:
        check_upload_size(logo.size or 0)
        logo_filename = f"company_logo_{safe_filename(logo.filename, ALLOWED_IMAGE_EXT)}"
        with open(os.path.join(UPLOADS_DIR, logo_filename), "wb") as buffer:
            shutil.copyfileobj(logo.file, buffer)
        logo_path = f"/uploads/{logo_filename}"

    company = models.Company(name=name, logo_url=logo_path)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company

@router.put("/companies/{company_id}", response_model=models.CompanySchema)
def update_company(
    company_id: int,
    name: str = Form(...),
    logo: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(authorize(["super_admin"]))
):
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    company.name = name
    if logo and logo.filename:
        check_upload_size(logo.size or 0)
        logo_filename = f"company_logo_{safe_filename(logo.filename, ALLOWED_IMAGE_EXT)}"
        with open(os.path.join(UPLOADS_DIR, logo_filename), "wb") as buffer:
            shutil.copyfileobj(logo.file, buffer)
        company.logo_url = f"/uploads/{logo_filename}"
    db.commit()
    db.refresh(company)
    return company
