"""Geração do PDF do certificado — sob demanda, não fica nada gerado em
disco (o registro no banco já tem tudo que precisa: usuário, curso, datas).
Se o curso tiver certificate_template_url (imagem enviada pelo admin), ela
vira o fundo da página e o texto é sobreposto; senão usa um layout padrão."""
import os
from io import BytesIO

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from deps import UPLOADS_DIR

PRIMARY = HexColor("#1e3a8a")
ACCENT = HexColor("#2563eb")
TEXT_DIM = HexColor("#475569")
SIGNATURE_LINE = HexColor("#94a3b8")

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")


def _template_path(url):
    """Resolve uma URL tipo /uploads/xxx.png pro caminho físico do arquivo
    — usado tanto pro template de certificado do curso quanto pra logo da
    empresa, que ficam salvos no mesmo diretório de uploads."""
    if not url:
        return None
    path = os.path.join(UPLOADS_DIR, os.path.basename(url))
    return path if os.path.isfile(path) else None


def generate_certificate_pdf(username: str, course_title: str, issued_at, expires_at,
                              certificate_template_url=None, company_logo_url=None, company_name=None) -> bytes:
    buf = BytesIO()
    page_size = landscape(A4)
    w, h = page_size
    c = canvas.Canvas(buf, pagesize=page_size)

    template_path = _template_path(certificate_template_url)
    if template_path:
        c.drawImage(template_path, 0, 0, width=w, height=h, preserveAspectRatio=False)
    else:
        _draw_default_background(c, w, h)

    _draw_logo(c, w, h, company_logo_url)
    _draw_text(c, w, h, username, course_title, issued_at, expires_at)
    _draw_signature_line(c, w, h, company_name)

    c.showPage()
    c.save()
    return buf.getvalue()


def _draw_logo(c, w, h, company_logo_url):
    # Logo da empresa do curso tem prioridade; sem ela, cai no fallback
    # fixo (útil pra empresa que ainda não subiu a própria logo).
    logo_path = _template_path(company_logo_url) or (LOGO_PATH if os.path.isfile(LOGO_PATH) else None)
    if not logo_path:
        return
    img = ImageReader(logo_path)
    iw, ih = img.getSize()
    logo_w = 3.2 * cm
    logo_h = logo_w * (ih / iw)
    c.drawImage(img, (w - logo_w) / 2, h - 1.9 * cm - logo_h, width=logo_w, height=logo_h,
                preserveAspectRatio=True, mask="auto")


def _draw_signature_line(c, w, h, company_name):
    """Espaço para assinatura — uma linha em branco pra assinar na mão (ou
    digitalmente depois) mais o nome da empresa responsável pelo treinamento."""
    line_y = 5.4 * cm
    line_w = 7 * cm
    line_x = (w - line_w) / 2
    c.setStrokeColor(SIGNATURE_LINE)
    c.setLineWidth(1)
    c.line(line_x, line_y, line_x + line_w, line_y)
    c.setFillColor(TEXT_DIM)
    c.setFont("Helvetica", 10)
    c.drawCentredString(w / 2, line_y - 0.5 * cm, company_name or "GeoTrilha")


def _draw_default_background(c, w, h):
    c.setFillColor(HexColor("#f8fafc"))
    c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setStrokeColor(PRIMARY)
    c.setLineWidth(3)
    c.rect(1 * cm, 1 * cm, w - 2 * cm, h - 2 * cm, fill=0, stroke=1)
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1)
    c.rect(1.3 * cm, 1.3 * cm, w - 2.6 * cm, h - 2.6 * cm, fill=0, stroke=1)


def _draw_text(c, w, h, username, course_title, issued_at, expires_at):
    c.setFillColor(PRIMARY)
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(w / 2, h - 5.0 * cm, "CERTIFICADO DE CONCLUSÃO")

    c.setFillColor(TEXT_DIM)
    c.setFont("Helvetica", 14)
    c.drawCentredString(w / 2, h - 6.8 * cm, "Certificamos que")

    c.setFillColor(PRIMARY)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(w / 2, h - 8.4 * cm, username)

    c.setFillColor(TEXT_DIM)
    c.setFont("Helvetica", 14)
    c.drawCentredString(w / 2, h - 10.0 * cm, "concluiu com êxito o curso")

    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(w / 2, h - 11.4 * cm, course_title)

    issued_str = issued_at.strftime("%d/%m/%Y") if issued_at else "—"
    expires_str = expires_at.strftime("%d/%m/%Y") if expires_at else "—"
    c.setFillColor(TEXT_DIM)
    c.setFont("Helvetica", 11)
    c.drawCentredString(w / 2, 3 * cm, f"Emitido em {issued_str}  ·  Válido até {expires_str}")
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(w / 2, 2.3 * cm, "GeoTrilha — Plataforma de Treinamentos")
