"""Envio de e-mail via SMTP genérico, configurado no .env.

Não é obrigatório configurar: se SMTP_HOST não estiver definido, send_email
não tenta conectar em lugar nenhum — só registra em EmailLog e devolve
False. Todo chamador continua funcionando normalmente nesse caso (o link
de convite/reset sempre é devolvido na resposta da API, então a UI sempre
tem o link pra copiar manualmente como já fazia antes de existir isso).
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

import models

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


def is_configured() -> bool:
    return bool(os.getenv("SMTP_HOST", "").strip())


def render_template(filename: str, **kwargs) -> str:
    with open(os.path.join(TEMPLATES_DIR, filename), "r", encoding="utf-8") as f:
        html = f.read()
    for key, value in kwargs.items():
        html = html.replace("{{" + key + "}}", str(value))
    return html


def send_email(db: Session, to_email: str, subject: str, html_body: str, email_type: str) -> bool:
    """Tenta enviar; nunca levanta exceção. Sempre grava o resultado em
    EmailLog (SUCESSO/ERRO) para aparecer na tela de Convites do admin."""
    status = "ERRO"
    error_message = None

    if not is_configured():
        error_message = "SMTP não configurado (defina SMTP_HOST no .env para ativar o envio real)"
    else:
        host = os.getenv("SMTP_HOST")
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER") or None
        password = os.getenv("SMTP_PASSWORD") or None
        sender = os.getenv("SMTP_FROM") or user or "no-reply@geobiogas.tech"
        use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() != "false"
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = to_email
            msg.attach(MIMEText(html_body, "html", "utf-8"))
            with smtplib.SMTP(host, port, timeout=10) as server:
                if use_tls:
                    server.starttls()
                if user and password:
                    server.login(user, password)
                server.sendmail(sender, [to_email], msg.as_string())
            status = "SUCESSO"
        except Exception as e:
            error_message = str(e)

    log = models.EmailLog(
        recipient_email=to_email,
        email_type=email_type,
        status=status,
        error_message=error_message,
    )
    db.add(log)
    db.commit()
    return status == "SUCESSO"
