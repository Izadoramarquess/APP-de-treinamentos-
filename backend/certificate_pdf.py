"""Geração do PDF do certificado — sob demanda, não fica nada gerado em
disco (o registro no banco já tem tudo que precisa: usuário, curso, datas).
Se o curso tiver certificate_template_url (imagem enviada pelo admin), ela
vira o fundo da página e o texto é sobreposto; senão usa o layout padrão
(faixas onduladas com degradê, alinhado à esquerda — modelo pedido pela
Iza, copiando um certificado de referência que ela mandou)."""
import os
from io import BytesIO

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from deps import UPLOADS_DIR

PRIMARY = HexColor("#3730a3")
ACCENT = HexColor("#7c3aed")
TEXT_DIM = HexColor("#475569")
TEXT_MAIN = HexColor("#1e293b")
WAVE_PURPLE = HexColor("#9b8ecb")
WAVE_PINK = HexColor("#dba3c9")
WAVE_BLUE = HexColor("#a9c6e8")

LEFT_MARGIN = 2.3 * cm
BAND_FRACTION = 0.28  # altura de cada faixa (topo/base) como fração de h
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")

DIAS_SEMANA_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES_PT = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

# Mesma fonte usada no resto do app (frontend carrega "Outfit" do Google
# Fonts) — Helvetica do reportlab deixava o certificado com cara de
# formulário genérico, bem diferente da referência que a Iza mandou.
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
_FONT_DIR = os.path.join(ASSETS_DIR, "fonts")
try:
    pdfmetrics.registerFont(TTFont("Outfit", os.path.join(_FONT_DIR, "Outfit-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Outfit-Bold", os.path.join(_FONT_DIR, "Outfit-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Outfit-SemiBold", os.path.join(_FONT_DIR, "Outfit-SemiBold.ttf")))
    FONT_REGULAR = "Outfit"
    FONT_BOLD = "Outfit-Bold"
except Exception:
    pass  # sem os arquivos de fonte, cai no Helvetica padrão do reportlab


def _template_path(url):
    """Resolve uma URL tipo /uploads/xxx.png pro caminho físico do arquivo
    — usado tanto pro template de certificado do curso quanto pra logo da
    empresa, que ficam salvos no mesmo diretório de uploads."""
    if not url:
        return None
    path = os.path.join(UPLOADS_DIR, os.path.basename(url))
    return path if os.path.isfile(path) else None


def _wrap_rich(c, segments, size, max_width):
    """Quebra de linha com trechos em negrito misturados no meio do texto
    (ex.: "pela conclusão do curso **X**, com carga horária de Yh") — o
    canvas do reportlab não tem Paragraph com <b>, só desenha string simples,
    então a quebra de linha e a troca de fonte por palavra são manuais."""
    words = []
    for text, bold in segments:
        for word in text.split():
            words.append((word, bold))
    space_w = c.stringWidth(" ", FONT_REGULAR, size)
    lines, current, current_w = [], [], 0
    for word, bold in words:
        font = FONT_BOLD if bold else FONT_REGULAR
        word_w = c.stringWidth(word, font, size)
        added = word_w if not current else word_w + space_w
        if current and current_w + added > max_width:
            lines.append(current)
            current, current_w = [(word, bold)], word_w
        else:
            current.append((word, bold))
            current_w += added
    if current:
        lines.append(current)
    return lines


def _draw_rich_line(c, x, y, line, size, color_regular, color_bold):
    space_w = c.stringWidth(" ", FONT_REGULAR, size)
    cx = x
    for i, (word, bold) in enumerate(line):
        font = FONT_BOLD if bold else FONT_REGULAR
        c.setFont(font, size)
        c.setFillColor(color_bold if bold else color_regular)
        c.drawString(cx, y, word)
        cx += c.stringWidth(word, font, size)
        if i < len(line) - 1:
            cx += space_w


def _wrap_text(c, text, font_name, font_size, max_width):
    words = (text or "").split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if c.stringWidth(trial, font_name, font_size) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_certificate_pdf(username: str, course_title: str, issued_at, expires_at,
                              certificate_template_url=None, company_logo_url=None, company_name=None,
                              workload_hours=None, course_content=None,
                              signatory_name=None, signatory_role=None, city=None) -> bytes:
    buf = BytesIO()
    page_size = landscape(A4)
    w, h = page_size
    c = canvas.Canvas(buf, pagesize=page_size)

    template_path = _template_path(certificate_template_url)
    if template_path:
        c.drawImage(template_path, 0, 0, width=w, height=h, preserveAspectRatio=False)
    else:
        _draw_wave_background(c, w, h)

    _draw_text(c, w, h, username, course_title, issued_at, expires_at, company_name,
               workload_hours, course_content, signatory_name, signatory_role, city)
    _draw_logo(c, w, h, company_logo_url)

    c.showPage()
    c.save()
    return buf.getvalue()


def _wave_band(c, w, h, band_h, top: bool):
    """Faixa colorida com borda ondulada (curva em S) — topo ou base da
    página. O degradê é diagonal (linearGradient) recortado pelo formato
    da onda via clipPath."""
    if top:
        y_wave = h - band_h
        p = c.beginPath()
        p.moveTo(0, h)
        p.lineTo(0, y_wave + band_h * 0.25)
        p.curveTo(w * 0.22, y_wave - band_h * 0.35, w * 0.30, y_wave + band_h * 0.55, w * 0.52, y_wave + band_h * 0.15)
        p.curveTo(w * 0.70, y_wave - band_h * 0.25, w * 0.82, y_wave + band_h * 0.35, w, y_wave + band_h * 0.05)
        p.lineTo(w, h)
        p.close()
    else:
        y_wave = band_h
        p = c.beginPath()
        p.moveTo(0, 0)
        p.lineTo(0, y_wave - band_h * 0.25)
        p.curveTo(w * 0.20, y_wave + band_h * 0.30, w * 0.35, y_wave - band_h * 0.5, w * 0.55, y_wave - band_h * 0.1)
        p.curveTo(w * 0.72, y_wave + band_h * 0.25, w * 0.85, y_wave - band_h * 0.3, w, y_wave - band_h * 0.05)
        p.lineTo(w, 0)
        p.close()
    c.saveState()
    c.clipPath(p, stroke=0, fill=0)
    if top:
        c.linearGradient(0, h, w, y_wave, [WAVE_PURPLE, WAVE_PINK, WAVE_BLUE])
    else:
        c.linearGradient(0, 0, w, band_h, [WAVE_BLUE, WAVE_PINK, WAVE_PURPLE])
    c.restoreState()


def _draw_wave_background(c, w, h):
    c.setFillColor(HexColor("#ffffff"))
    c.rect(0, 0, w, h, fill=1, stroke=0)
    band_h = h * BAND_FRACTION
    _wave_band(c, w, h, band_h, top=True)
    _wave_band(c, w, h, band_h, top=False)


def _draw_logo(c, w, h, company_logo_url):
    # Logo da empresa do aluno, canto inferior esquerdo — fica abaixo do
    # início da onda de baixo (que na borda esquerda começa mais alta),
    # então sempre cai sobre fundo branco.
    logo_path = _template_path(company_logo_url) or (LOGO_PATH if os.path.isfile(LOGO_PATH) else None)
    if not logo_path:
        return
    img = ImageReader(logo_path)
    iw, ih = img.getSize()
    logo_h = 1.5 * cm
    logo_w = logo_h * (iw / ih)
    c.drawImage(img, LEFT_MARGIN, 1.3 * cm, width=logo_w, height=logo_h,
                preserveAspectRatio=True, mask="auto")


def _draw_text(c, w, h, username, course_title, issued_at, expires_at, company_name,
               workload_hours, course_content, signatory_name, signatory_role, city):
    max_width = w - LEFT_MARGIN - 2.3 * cm
    band_h = h * BAND_FRACTION
    y = h - band_h - 1.15 * cm

    # Marquinha decorativa antes do título, igual referência.
    c.setFillColor(ACCENT)
    c.rect(LEFT_MARGIN, y - 0.42 * cm, 0.15 * cm, 0.62 * cm, fill=1, stroke=0)
    c.setFillColor(PRIMARY)
    c.setFont(FONT_BOLD, 24)
    c.drawString(LEFT_MARGIN + 0.4 * cm, y, "CERTIFICADO DE CONCLUSÃO")
    y -= 1.2 * cm

    c.setFillColor(TEXT_DIM)
    c.setFont(FONT_REGULAR, 12.5)
    c.drawString(LEFT_MARGIN, y, f"A {company_name or 'GeoTrilha'} confere certificado a")
    y -= 0.95 * cm

    c.setFillColor(TEXT_MAIN)
    c.setFont(FONT_BOLD, 21)
    c.drawString(LEFT_MARGIN, y, username)
    y -= 1.05 * cm

    # Parágrafo único, com o nome do curso em negrito no meio do texto —
    # igual à referência ("pela participação na **Evento X**...").
    segments = [("pela conclusão do curso ", False), (course_title, True)]
    if workload_hours:
        segments.append((f", com carga horária de {workload_hours} horas,", False))
    segments.append((" através da plataforma GeoTrilha.", False))
    for line in _wrap_rich(c, segments, 12.5, max_width):
        _draw_rich_line(c, LEFT_MARGIN, y, line, 12.5, TEXT_DIM, ACCENT)
        y -= 0.62 * cm

    if course_content:
        y -= 0.15 * cm
        max_lines = 3
        lines = _wrap_text(c, course_content, FONT_REGULAR, 9.5, max_width)
        truncated = len(lines) > max_lines
        lines = lines[:max_lines]
        if truncated and lines:
            last = lines[-1]
            while last and c.stringWidth(last + "…", FONT_REGULAR, 9.5) > max_width:
                last = last[:-1]
            lines[-1] = last + "…"
        c.setFillColor(TEXT_DIM)
        c.setFont(FONT_BOLD, 9.5)
        c.drawString(LEFT_MARGIN, y, "Conteúdo programático")
        y -= 0.4 * cm
        c.setFont(FONT_REGULAR, 9.5)
        for line in lines:
            c.drawString(LEFT_MARGIN, y, line)
            y -= 0.38 * cm

    # Assinatura e data — por padrão ancoradas perto da faixa de baixo
    # (visual consistente com a referência), mas se o conteúdo do curso
    # empurrou o cursor pra baixo desse ponto, usa o cursor mesmo pra
    # nunca sobrepor o texto de cima.
    anchor_y = band_h + 2.6 * cm
    y = min(y - 0.4 * cm, anchor_y)

    if signatory_name:
        c.setFillColor(TEXT_MAIN)
        c.setFont(FONT_BOLD, 12)
        c.drawString(LEFT_MARGIN, y, signatory_name)
        y -= 0.45 * cm
    if signatory_role:
        c.setFillColor(TEXT_DIM)
        c.setFont(FONT_REGULAR, 10)
        c.drawString(LEFT_MARGIN, y, signatory_role)
        y -= 0.45 * cm

    date_y = min(y - 0.3 * cm, band_h + 0.9 * cm)
    issued_str = _data_extenso(issued_at, city)
    c.setFillColor(TEXT_DIM)
    c.setFont(FONT_REGULAR, 10.5)
    c.drawString(LEFT_MARGIN, date_y, issued_str)

    if expires_at:
        c.setFont(FONT_REGULAR, 8.5)
        c.drawString(LEFT_MARGIN, date_y - 0.42 * cm, f"Válido até {expires_at.strftime('%d/%m/%Y')}")


def _data_extenso(issued_at, city):
    if not issued_at:
        base = "Data não disponível"
    else:
        dia_semana = DIAS_SEMANA_PT[issued_at.weekday()]
        base = f"{dia_semana}, {issued_at.day} de {MESES_PT[issued_at.month]} de {issued_at.year}"
    return f"{city}, {base}" if city else base.capitalize()
