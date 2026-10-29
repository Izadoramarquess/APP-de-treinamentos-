"""Job diário em background: avisa por e-mail quando um certificado está
vencendo e quando uma matrícula ficou parada sem nenhum progresso.

Cada aviso só é mandado uma vez (flag reminder_sent/expiry_reminder_sent no
banco) — sem isso o job mandaria o mesmo e-mail de novo a cada execução.
Roda dentro do próprio processo da API (APScheduler), sem depender de cron
externo; em deploy com múltiplos workers gunicorn cada worker roda seu
próprio agendador, então existe uma janela rara de e-mail duplicado — o
mesmo tipo de limitação já documentada pro rate-limit de login em auth.py.
"""
import datetime
import os

from apscheduler.schedulers.background import BackgroundScheduler

import models
import email_utils
from database import SessionLocal

CERT_EXPIRY_WARNING_DAYS = int(os.getenv("CERT_EXPIRY_WARNING_DAYS", "30"))
COURSE_STALLED_REMINDER_DAYS = int(os.getenv("COURSE_STALLED_REMINDER_DAYS", "7"))


def _check_expiring_certificates(db):
    now = datetime.datetime.utcnow()
    warning_cutoff = now + datetime.timedelta(days=CERT_EXPIRY_WARNING_DAYS)
    certs = db.query(models.Certificate).filter(
        models.Certificate.expiry_reminder_sent == False,
        models.Certificate.expires_at <= warning_cutoff,
        models.Certificate.expires_at >= now,
    ).all()
    for cert in certs:
        user = db.query(models.User).filter(models.User.id == cert.user_id).first()
        course = db.query(models.Course).filter(models.Course.id == cert.course_id).first()
        if not user or not course:
            continue
        email_utils.send_email(
            db, user.email, f"Certificado vencendo — {course.title}",
            email_utils.render_template(
                "cert_expiring.html",
                username=user.username,
                curso=course.title,
                data_validade=cert.expires_at.strftime("%d/%m/%Y"),
            ),
            "cert_expiring"
        )
        cert.expiry_reminder_sent = True
        db.commit()


def _check_stalled_enrollments(db):
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=COURSE_STALLED_REMINDER_DAYS)
    enrollments = db.query(models.Enrollment).filter(
        models.Enrollment.reminder_sent == False,
        models.Enrollment.enrolled_at <= cutoff,
    ).all()
    for enr in enrollments:
        module_ids = [m.id for m in db.query(models.Module.id).filter(models.Module.course_id == enr.course_id).all()]
        has_progress = False
        if module_ids:
            has_progress = db.query(models.ModuleProgress).filter(
                models.ModuleProgress.user_id == enr.user_id,
                models.ModuleProgress.module_id.in_(module_ids),
            ).first() is not None
        if has_progress:
            enr.reminder_sent = True  # já começou — não é mais "parado", não precisa mais checar
            db.commit()
            continue
        user = db.query(models.User).filter(models.User.id == enr.user_id).first()
        course = db.query(models.Course).filter(models.Course.id == enr.course_id).first()
        if not user or not course:
            continue
        dias = (datetime.datetime.utcnow() - enr.enrolled_at).days
        email_utils.send_email(
            db, user.email, f"Curso pendente — {course.title}",
            email_utils.render_template(
                "course_reminder.html",
                username=user.username,
                curso=course.title,
                dias=dias,
            ),
            "course_reminder"
        )
        enr.reminder_sent = True
        db.commit()


def run_reminder_checks():
    db = SessionLocal()
    try:
        _check_expiring_certificates(db)
        _check_stalled_enrollments(db)
    finally:
        db.close()


_scheduler = None

def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(run_reminder_checks, "interval", hours=24, next_run_time=datetime.datetime.now())
    _scheduler.start()
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
