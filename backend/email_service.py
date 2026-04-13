import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import datetime
from sqlalchemy.orm import Session
from models import EmailLog

# Env vars
MS_CLIENT_ID = os.getenv("MS_CLIENT_ID")
MS_TENANT_ID = os.getenv("MS_TENANT_ID")
MS_CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")
SMTP_USER = os.getenv("SMTP_USER", "no-reply@geobiogas.tech")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587

SENDER_EMAIL = "esg@geobiogas.tech"
CC_EMAIL = "izadora.silva@geobiogas.tech"
COMPANY_NAME = "GeoBiogás"

def get_ms_graph_token():
    if not all([MS_CLIENT_ID, MS_TENANT_ID, MS_CLIENT_SECRET]):
        return None
    url = f"https://login.microsoftonline.com/{MS_TENANT_ID}/oauth2/v2.0/token"
    payload = {
        "client_id": MS_CLIENT_ID,
        "scope": "https://graph.microsoft.com/.default",
        "client_secret": MS_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None

def send_via_graph_api(to_email: str, subject: str, html_content: str, token: str):
    url = f"https://graph.microsoft.com/v1.0/users/{SENDER_EMAIL}/sendMail"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": html_content
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": to_email
                    }
                }
            ],
            "ccRecipients": [
                {
                    "emailAddress": {
                        "address": CC_EMAIL
                    }
                }
            ]
        }
    }
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 202:
        raise Exception(f"Graph API Error {resp.status_code}: {resp.text}")

def send_via_smtp(to_email: str, subject: str, html_content: str):
    if not all([SMTP_USER, SMTP_PASS]):
        raise Exception("SMTP credentials missing.")
        
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg["Cc"] = CC_EMAIL

    msg.attach(MIMEText(html_content, "html"))

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SMTP_USER, SMTP_PASS)
    # SMTP send required list of all recipients (To + Cc)
    server.sendmail(SENDER_EMAIL, [to_email, CC_EMAIL], msg.as_string())
    server.quit()

def log_email(db: Session, to_email: str, email_type: str, status: str, error_message: str = None):
    log = EmailLog(
        recipient_email=to_email,
        email_type=email_type,
        status=status,
        error_message=error_message
    )
    db.add(log)
    db.commit()

def render_template(template_name: str, context: dict):
    # Procura em backend/templates
    filepath = os.path.join(os.path.dirname(__file__), "templates", template_name)
    if not os.path.exists(filepath):
        # Fallback inline
        if "invite" in template_name:
            return f"<h1>Convite para a plataforma {context.get('nome_empresa')}</h1><p>Olá,</p><p>Você foi convidado para a equipe <strong>{context.get('nome_equipe')}</strong> e há treinamentos liberados: {context.get('lista_treinamentos')}</p><p>Acesse aqui: <a href='{context.get('link_convite')}'>{context.get('link_convite')}</a></p>"
        else:
            return f"<h1>Atualização da {context.get('nome_empresa')}</h1><p>Olá,</p><p>Você foi adicionado à equipe <strong>{context.get('nome_equipe')}</strong> e tem novos treinamentos: {context.get('lista_treinamentos')}</p><p>Acesse pelo sistema.</p>"

    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    context["nome_empresa"] = COMPANY_NAME
    for k, v in context.items():
        if v is None: v = ''
        html = html.replace(f"{{{{{k}}}}}", str(v))
    return html

def send_transactional_email(db: Session, to_email: str, subject: str, template_name: str, context: dict, email_type: str):
    html_content = render_template(template_name, context)
    
    try:
        token = get_ms_graph_token()
        if token:
            send_via_graph_api(to_email, subject, html_content, token)
        else:
            send_via_smtp(to_email, subject, html_content)
            
        log_email(db, to_email, email_type, "SUCESSO")
        print(f"[E-MAIL] SUCESSO: Enviado para {to_email} (CC: {CC_EMAIL})")
        return True
    except Exception as e:
        error_msg = str(e)
        log_email(db, to_email, email_type, "ERRO", error_msg)
        print(f"[E-MAIL] ERRO: Falha ao enviar para {to_email}. Motivo: {error_msg}")
        return False
