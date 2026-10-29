"""Geração do PDF do certificado — sob demanda, não fica nada gerado em
disco (o registro no banco já tem tudo que precisa: usuário, curso, datas).
Se o curso tiver certificate_template_url (imagem enviada pelo admin), ela
vira o fundo da página e o texto é sobreposto; senão usa o layout padrão
(faixas onduladas com degradê, alinhado à esquerda — modelo pedido pela
Iza, copiando um certificado de referência que ela mandou)."""
import os
import re
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
# Cores tiradas com conta-gotas da própria imagem de referência (não são
# achismo) — a primeira tentativa usou rosa/azul vivos demais; o gradiente
# real é um lilás bem dessaturado, quase acinzentado.
WAVE_A = HexColor("#9aa7ce")  # ponta mais fria/azulada
WAVE_B = HexColor("#a59dc9")  # meio
WAVE_C = HexColor("#b292c2")  # ponta mais quente/rosada
SHADOW = HexColor("#94a3b8")

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")

# Margens e âncoras verticais medidas pixel a pixel no certificado de
# referência que a Iza mandou (não são estéticas "a olho" — vieram de
# varrer a imagem procurando onde o texto e a onda realmente começam).
LEFT_MARGIN_FRAC = 0.185
RIGHT_MARGIN_FRAC = 0.19
TITLE_Y_FRAC = 0.749
INTRO_Y_FRAC = 0.649
NAME_Y_FRAC = 0.582
PARA_START_Y_FRAC = 0.519
PARA_PITCH_FRAC = 0.033
SIG_NAME_Y_FRAC = 0.285
SIG_ROLE_Y_FRAC = 0.260
DATE_Y_FRAC = 0.177
LOGO_BOTTOM_Y_FRAC = 0.03
LOGO_H_FRAC = 0.10

# Contorno da faixa ondulada, rastreado pixel a pixel na imagem de
# referência (fração de largura, fração de altura-a-partir-do-topo da
# borda entre a cor e o branco). Reproduz a forma assimétrica real —
# funda e estreita à esquerda no topo, funda e estreita à direita embaixo
# — que uma curva em S simétrica não chegava perto de imitar.
TOP_WAVE_TRACE = [
    (0.0, 0.4608), (0.0072, 0.4304), (0.0143, 0.4063), (0.0215, 0.3848), (0.0286, 0.3671),
    (0.0358, 0.3506), (0.043, 0.3342), (0.0501, 0.3203), (0.0573, 0.3063), (0.0645, 0.2937),
    (0.0716, 0.281), (0.0788, 0.2696), (0.0859, 0.2595), (0.0931, 0.2494), (0.1003, 0.2392),
    (0.1074, 0.2291), (0.1146, 0.2203), (0.1218, 0.2114), (0.1289, 0.2038), (0.1361, 0.1949),
    (0.1432, 0.1873), (0.1504, 0.1797), (0.1576, 0.1734), (0.1647, 0.1658), (0.1719, 0.1595),
    (0.1791, 0.1532), (0.1862, 0.1468), (0.1934, 0.1418), (0.2005, 0.1354), (0.2077, 0.1304),
    (0.2149, 0.1241), (0.222, 0.119), (0.2292, 0.1139), (0.2363, 0.1101), (0.2435, 0.1089),
    (0.2507, 0.1114), (0.2578, 0.1152), (0.265, 0.1177), (0.2722, 0.1215), (0.2793, 0.1241),
    (0.2865, 0.1278), (0.2936, 0.1304), (0.3008, 0.1342), (0.308, 0.1367), (0.3151, 0.1392),
    (0.3223, 0.143), (0.3295, 0.1456), (0.3366, 0.1494), (0.3438, 0.1519), (0.3509, 0.1557),
    (0.3581, 0.1582), (0.3653, 0.162), (0.3724, 0.1646), (0.3796, 0.1684), (0.3868, 0.1709),
    (0.3939, 0.1747), (0.4011, 0.1772), (0.4082, 0.181), (0.4154, 0.1835), (0.4226, 0.1861),
    (0.4297, 0.1899), (0.4369, 0.1911), (0.444, 0.1848), (0.4512, 0.1785), (0.4584, 0.1722),
    (0.4655, 0.1658), (0.4727, 0.1595), (0.4799, 0.1519), (0.487, 0.1456), (0.4942, 0.1392),
    (0.5013, 0.1329), (0.5085, 0.1266), (0.5157, 0.119), (0.5228, 0.1127), (0.53, 0.1063),
    (0.5372, 0.1), (0.5443, 0.0937), (0.5515, 0.0861), (0.5586, 0.0797), (0.5658, 0.0734),
    (0.573, 0.0671), (0.5801, 0.0608), (0.5873, 0.0532), (0.5944, 0.0468), (0.6016, 0.0405),
    (0.6088, 0.0342), (0.6159, 0.0278), (0.6231, 0.0203), (0.6303, 0.0139), (0.6374, 0.0076),
    (0.6446, 0.0013), (1.0, 0.0013),
]
BOTTOM_WAVE_TRACE = [
    (0.0, 0.9987), (0.38, 0.9987), (0.3868, 0.9962), (0.3939, 0.9886), (0.4011, 0.9823),
    (0.4082, 0.9759), (0.4154, 0.9696), (0.4226, 0.962), (0.4297, 0.9557), (0.4369, 0.9494),
    (0.444, 0.943), (0.4512, 0.9367), (0.4584, 0.9291), (0.4655, 0.9228), (0.4727, 0.9165),
    (0.4799, 0.9101), (0.487, 0.9025), (0.4942, 0.8962), (0.5013, 0.8899), (0.5085, 0.8835),
    (0.5157, 0.8772), (0.5228, 0.8696), (0.53, 0.8684), (0.5372, 0.8722), (0.5443, 0.8747),
    (0.5515, 0.8785), (0.5586, 0.881), (0.5658, 0.8835), (0.573, 0.8873), (0.5801, 0.8899),
    (0.5873, 0.8937), (0.5944, 0.8962), (0.6016, 0.9), (0.6088, 0.9025), (0.6159, 0.9063),
    (0.6231, 0.9089), (0.6303, 0.9127), (0.6374, 0.9152), (0.6446, 0.919), (0.6517, 0.9215),
    (0.6589, 0.9253), (0.6661, 0.9278), (0.6732, 0.9304), (0.6804, 0.9342), (0.6876, 0.9367),
    (0.6947, 0.9405), (0.7019, 0.943), (0.709, 0.9468), (0.7162, 0.9494), (0.7234, 0.9532),
    (0.7305, 0.9557), (0.7377, 0.9595), (0.7449, 0.957), (0.752, 0.9532), (0.7592, 0.9481),
    (0.7663, 0.9443), (0.7735, 0.9392), (0.7807, 0.9342), (0.7878, 0.9291), (0.795, 0.9241),
    (0.8021, 0.919), (0.8093, 0.9127), (0.8165, 0.9063), (0.8236, 0.9), (0.8308, 0.8937),
    (0.838, 0.8861), (0.8451, 0.8797), (0.8523, 0.8722), (0.8594, 0.8633), (0.8666, 0.8557),
    (0.8738, 0.8468), (0.8809, 0.8367), (0.8881, 0.8278), (0.8953, 0.8177), (0.9024, 0.8076),
    (0.9096, 0.7962), (0.9167, 0.7848), (0.9239, 0.7722), (0.9311, 0.7595), (0.9382, 0.7456),
    (0.9454, 0.7316), (0.9526, 0.7165), (0.9597, 0.7), (0.9669, 0.6823), (0.974, 0.6633),
    (0.9812, 0.643), (0.9884, 0.6203), (0.9955, 0.5949), (1.0, 0.585),
]

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


def _boundary_path(c, w, h, trace, top: bool, closed: bool):
    """Caminho do contorno traçado — usado tanto pra recortar o
    preenchimento (fechado, com as bordas da página) quanto pra riscar a
    sombra/o brilho ao longo da própria curva (aberto, só a onda)."""
    p = c.beginPath()
    pts = [(xf * w, h - yf * h) for xf, yf in trace]
    if closed:
        p.moveTo(0, h if top else 0)
        for x, y in pts:
            p.lineTo(x, y)
        p.lineTo(w, h if top else 0)
        p.close()
    else:
        p.moveTo(*pts[0])
        for x, y in pts[1:]:
            p.lineTo(x, y)
    return p


def _draw_wave_shadow(c, w, h, trace, top: bool):
    """Sombra suave da onda sobre a página — riscos concêntricos ao longo
    da própria curva, cada vez mais largos e mais transparentes, imitando
    o blur que o reportlab não tem nativo. Desenhado ANTES do
    preenchimento, pra só sobrar visível do lado branco (o preenchimento
    por cima cobre a metade que caiu do lado colorido)."""
    path = _boundary_path(c, w, h, trace, top, closed=False)
    c.saveState()
    c.setStrokeColor(SHADOW)
    for width_pt, alpha in ((14, 0.05), (9, 0.07), (5, 0.10), (2.2, 0.14)):
        c.setLineWidth(width_pt)
        c.setStrokeAlpha(alpha)
        c.drawPath(path, stroke=1, fill=0)
    c.restoreState()


def _draw_wave_gloss(c, w, h, trace, top: bool):
    """Brilho/sheen suave próximo à parte mais fina da onda — sem isso o
    gradiente fica chapado; um traço branco translúcido ao longo da borda
    (do lado colorido) dá a sensação de luz refletindo numa dobra, tipo
    seda. Desenhado DEPOIS do preenchimento, recortado pelo mesmo clip."""
    fill_path = _boundary_path(c, w, h, trace, top, closed=True)
    edge_path = _boundary_path(c, w, h, trace, top, closed=False)
    c.saveState()
    c.clipPath(fill_path, stroke=0, fill=0)
    c.setStrokeColor(HexColor("#ffffff"))
    offset = 1 if top else -1
    c.saveState()
    c.transform(1, 0, 0, 1, 0, offset * (0.012 * h))
    for width_pt, alpha in ((10, 0.05), (5, 0.09), (2, 0.16)):
        c.setLineWidth(width_pt)
        c.setStrokeAlpha(alpha)
        c.drawPath(edge_path, stroke=1, fill=0)
    c.restoreState()
    c.restoreState()


def _wave_band(c, w, h, trace, top: bool):
    """Faixa colorida cujo contorno é o traçado real (pixel a pixel) do
    certificado de referência — não uma curva desenhada de olho. O degradê
    é diagonal (linearGradient) recortado pelo formato via clipPath, com
    sombra por baixo e brilho por cima pra não ficar chapado (efeito "3D"
    que a Iza pediu)."""
    _draw_wave_shadow(c, w, h, trace, top)
    fill_path = _boundary_path(c, w, h, trace, top, closed=True)
    c.saveState()
    c.clipPath(fill_path, stroke=0, fill=0)
    if top:
        c.linearGradient(0, h, w * 0.68, h * 0.55, [WAVE_A, WAVE_B, WAVE_C])
    else:
        c.linearGradient(w, 0, w * 0.32, h * 0.45, [WAVE_A, WAVE_B, WAVE_C])
    c.restoreState()
    _draw_wave_gloss(c, w, h, trace, top)


def _draw_wave_background(c, w, h):
    c.setFillColor(HexColor("#ffffff"))
    c.rect(0, 0, w, h, fill=1, stroke=0)
    _wave_band(c, w, h, TOP_WAVE_TRACE, top=True)
    _wave_band(c, w, h, BOTTOM_WAVE_TRACE, top=False)


def _draw_logo(c, w, h, company_logo_url):
    # Canto inferior esquerdo, igual referência — nessa região a onda de
    # baixo não chega nem perto (só começa a partir de ~38% da largura),
    # então a logo sempre cai sobre fundo branco.
    logo_path = _template_path(company_logo_url) or (LOGO_PATH if os.path.isfile(LOGO_PATH) else None)
    if not logo_path:
        return
    img = ImageReader(logo_path)
    iw, ih = img.getSize()
    logo_h = h * LOGO_H_FRAC
    logo_w = logo_h * (iw / ih)
    # A onda de baixo só começa a partir de ~38% da largura — uma logo
    # bem larga (wordmark horizontal) não pode invadir essa área.
    max_logo_w = w * 0.32
    if logo_w > max_logo_w:
        logo_w = max_logo_w
        logo_h = logo_w * (ih / iw)
    c.drawImage(img, LEFT_MARGIN_FRAC * w, LOGO_BOTTOM_Y_FRAC * h, width=logo_w, height=logo_h,
                preserveAspectRatio=True, mask="auto")


def _draw_text(c, w, h, username, course_title, issued_at, expires_at, company_name,
               workload_hours, course_content, signatory_name, signatory_role, city):
    left = LEFT_MARGIN_FRAC * w
    max_width = w - left - RIGHT_MARGIN_FRAC * w
    para_pitch = PARA_PITCH_FRAC * h
    y = TITLE_Y_FRAC * h

    # Marquinha decorativa antes do título, igual referência.
    c.setFillColor(ACCENT)
    c.rect(left - 0.35 * cm, y - 0.05 * cm, 0.09 * cm, 0.5 * cm, fill=1, stroke=0)
    c.setFillColor(PRIMARY)
    c.setFont(FONT_BOLD, 26)
    c.drawString(left, y, "CERTIFICADO DE CONCLUSÃO")

    c.setFillColor(TEXT_DIM)
    c.setFont(FONT_REGULAR, 13)
    c.drawString(left, INTRO_Y_FRAC * h, f"A {company_name or 'GeoTrilha'} confere certificado a")

    c.setFillColor(TEXT_MAIN)
    c.setFont(FONT_BOLD, 22)
    c.drawString(left, NAME_Y_FRAC * h, username)

    # Parágrafo único, com o nome do curso em negrito no meio do texto —
    # igual à referência ("pela participação na **Evento X**...").
    segments = [("pela conclusão do curso ", False), (course_title, True)]
    if workload_hours:
        segments.append((f", com carga horária de {workload_hours} horas,", False))
    segments.append((" através da plataforma GeoTrilha.", False))
    y = PARA_START_Y_FRAC * h
    for line in _wrap_rich(c, segments, 13, max_width):
        _draw_rich_line(c, left, y, line, 13, TEXT_DIM, ACCENT)
        y -= para_pitch

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
        c.drawString(left, y, "Conteúdo programático")
        y -= 0.4 * cm
        c.setFont(FONT_REGULAR, 9.5)
        for line in lines:
            c.drawString(left, y, line)
            y -= 0.38 * cm

    # Assinatura e data — por padrão ancoradas nas posições medidas na
    # referência, mas se o conteúdo do curso empurrou o cursor pra baixo
    # desse ponto, usa o cursor mesmo pra nunca sobrepor o texto de cima.
    y = min(y - 0.35 * cm, SIG_NAME_Y_FRAC * h)

    if signatory_name:
        c.setFillColor(TEXT_MAIN)
        c.setFont(FONT_BOLD, 13)
        c.drawString(left, y, signatory_name)
        y = min(y - 0.5 * cm, SIG_ROLE_Y_FRAC * h)
    if signatory_role:
        c.setFillColor(TEXT_DIM)
        c.setFont(FONT_REGULAR, 10.5)
        c.drawString(left, y, signatory_role)
        y -= 0.5 * cm

    date_y = min(y - 0.3 * cm, DATE_Y_FRAC * h)
    issued_str = _data_extenso(issued_at, city)
    c.setFillColor(TEXT_DIM)
    c.setFont(FONT_REGULAR, 11)
    c.drawString(left, date_y, issued_str)

    if expires_at:
        c.setFont(FONT_REGULAR, 8.5)
        c.drawString(left, date_y - 0.42 * cm, f"Válido até {expires_at.strftime('%d/%m/%Y')}")


def _data_extenso(issued_at, city):
    if not issued_at:
        base = "Data não disponível"
    else:
        dia_semana = DIAS_SEMANA_PT[issued_at.weekday()]
        base = f"{dia_semana}, {issued_at.day} de {MESES_PT[issued_at.month]} de {issued_at.year}"
    return f"{city}, {base}" if city else base.capitalize()


# ============================================================
# Modelo "nr" — cópia do certificado formal que já era usado pra
# treinamento de Normas Regulamentadoras antes do GeoTrilha existir
# (fundo com textura sutil, selo amarelo NR-XX, fitas douradas nos
# cantos, conteúdo programático em página própria). Reconstruído a
# partir do .docx real que a Iza mandou (imagens extraídas direto do
# arquivo, posições/tamanhos lidos do XML do documento) — não foi
# possível renderizar o .docx original pra conferir pixel a pixel (sem
# LibreOffice neste ambiente), então o layout é uma reconstrução fiel
# aos elementos e à estrutura do texto, não uma cópia certificadamente
# exata posição-a-posição.
NR_YELLOW = HexColor("#f5ca00")
NR_RED = HexColor("#b50102")
NR_BLACK = HexColor("#1a1a1a")
NR_TEXT = HexColor("#1a1a1a")
NR_BG_PATH = os.path.join(ASSETS_DIR, "nr_certificate_bg.jpg")
NR_RIBBON_PATH = os.path.join(ASSETS_DIR, "nr_ribbon.png")


def _nr_code_from_title(course_title):
    m = re.search(r"NR-?\s?(\d+)", course_title or "", re.IGNORECASE)
    return m.group(1) if m else None


def _draw_nr_badge(c, cx, cy, size, nr_number):
    r = size / 2
    p = c.beginPath()
    p.moveTo(cx, cy + r)
    p.lineTo(cx + r, cy)
    p.lineTo(cx, cy - r)
    p.lineTo(cx - r, cy)
    p.close()
    c.setFillColor(NR_YELLOW)
    c.setStrokeColor(NR_BLACK)
    c.setLineWidth(size * 0.05)
    c.drawPath(p, fill=1, stroke=1)
    c.setFillColor(NR_BLACK)
    c.setFont(FONT_BOLD, size * 0.30)
    c.drawCentredString(cx, cy + size * 0.05, "NR")
    if nr_number:
        c.setFillColor(NR_RED)
        c.setFont(FONT_BOLD, size * 0.32)
        c.drawCentredString(cx, cy - size * 0.30, nr_number)


def _draw_nr_background(c, w, h, nr_number):
    if os.path.isfile(NR_BG_PATH):
        c.drawImage(NR_BG_PATH, 0, 0, width=w, height=h, preserveAspectRatio=False)
    else:
        c.setFillColor(HexColor("#ffffff"))
        c.rect(0, 0, w, h, fill=1, stroke=0)
    if os.path.isfile(NR_RIBBON_PATH):
        ribbon = ImageReader(NR_RIBBON_PATH)
        rs = 4.2 * cm
        c.drawImage(ribbon, 0.2 * cm, 0.2 * cm, width=rs, height=rs, mask="auto", preserveAspectRatio=True)
        c.saveState()
        c.translate(w, 0)
        c.scale(-1, 1)
        c.drawImage(ribbon, 0.2 * cm, 0.2 * cm, width=rs, height=rs, mask="auto", preserveAspectRatio=True)
        c.restoreState()
    _draw_nr_badge(c, 3.85 * cm, h - 2.1 * cm, 2.6 * cm, nr_number)


def _draw_nr_logo(c, w, h, company_logo_url):
    logo_path = _template_path(company_logo_url) or (LOGO_PATH if os.path.isfile(LOGO_PATH) else None)
    if not logo_path:
        return
    img = ImageReader(logo_path)
    iw, ih = img.getSize()
    logo_h = 2.2 * cm
    logo_w = min(logo_h * (iw / ih), 6.5 * cm)
    logo_h = logo_w * (ih / iw)
    c.drawImage(img, w - logo_w - 1.2 * cm, h - logo_h - 0.6 * cm, width=logo_w, height=logo_h,
                preserveAspectRatio=True, mask="auto")


def generate_nr_certificate_pdf(full_name, cpf, course_title, issued_at, workload_hours,
                                 company_name, company_cnpj, city,
                                 company_logo_url, instructor_name, instructor_role,
                                 instructor_registration, content_topics) -> bytes:
    buf = BytesIO()
    page_size = landscape(A4)
    w, h = page_size
    c = canvas.Canvas(buf, pagesize=page_size)
    nr_number = _nr_code_from_title(course_title)

    # ---- página 1: certificado ----
    _draw_nr_background(c, w, h, nr_number)
    _draw_nr_logo(c, w, h, company_logo_url)

    center = w / 2
    max_width = w - 7 * cm
    y = h - 5.2 * cm

    c.setFillColor(NR_TEXT)
    c.setFont(FONT_BOLD, 20)
    c.drawCentredString(center, y, "ESTE CERTIFICADO COMPROVA QUE")
    y -= 1.6 * cm

    c.setFont(FONT_BOLD, 26)
    c.drawCentredString(center, y, (full_name or "—").upper())
    y -= 1.5 * cm

    partes = []
    if cpf:
        partes.append(f"PORTADOR DO CPF: {cpf};")
    course_nr = f"NR-{nr_number}" if nr_number else ""
    data_str = ""
    if issued_at:
        data_str = f"{issued_at.day:02d} DE {MESES_PT[issued_at.month].upper()} DE {issued_at.year}"
    trecho = f'PARTICIPOU DO TREINAMENTO "{(course_title or "").upper()}"'
    if data_str:
        trecho += f" REALIZADO NO DIA {data_str}"
    if workload_hours:
        trecho += f" TOTALIZANDO {workload_hours:02d} HORAS"
    trecho += f" CONFORME REGE A NORMA REGULAMENTADORA – {course_nr}," if course_nr else ","
    if company_name:
        trecho += f" PROMOVIDO PELA EMPRESA {company_name.upper()}"
        if company_cnpj:
            trecho += f" (CNPJ: {company_cnpj})"
    trecho += "."
    partes.append(trecho)
    paragrafo = " ".join(partes)

    c.setFont(FONT_REGULAR, 13)
    for line in _wrap_text(c, paragrafo, FONT_REGULAR, 13, max_width):
        c.drawCentredString(center, y, line)
        y -= 0.62 * cm

    y -= 0.8 * cm
    if city or issued_at:
        c.setFont(FONT_REGULAR, 12)
        loc = f"{city.upper()}, " if city else ""
        c.drawCentredString(center, y, f"{loc}{data_str}" if data_str else loc.rstrip(", "))
    y -= 2.0 * cm

    if instructor_name:
        c.setFont(FONT_BOLD, 13)
        c.drawCentredString(center, y, instructor_name)
        y -= 0.55 * cm
    if instructor_role:
        c.setFont(FONT_REGULAR, 10.5)
        c.drawCentredString(center, y, instructor_role)
        y -= 0.45 * cm
    if instructor_registration:
        c.setFont(FONT_REGULAR, 10.5)
        c.drawCentredString(center, y, instructor_registration)

    c.setFont(FONT_REGULAR, 10)
    c.drawCentredString(center, 1.6 * cm, "Participante")

    # ---- página 2: conteúdo programático (só se tiver o que mostrar) ----
    topics = [t.strip(" -•;") for t in (content_topics or "").splitlines() if t.strip()]
    if topics:
        c.showPage()
        _draw_nr_background(c, w, h, nr_number)
        _draw_nr_logo(c, w, h, company_logo_url)
        c.setFillColor(NR_TEXT)
        c.setFont(FONT_BOLD, 18)
        c.drawCentredString(center, h - 4.5 * cm, "CONTEÚDO PROGRAMÁTICO")
        y = h - 6 * cm
        c.setFont(FONT_REGULAR, 12.5)
        for topic in topics:
            for line in _wrap_text(c, f"•  {topic}", FONT_REGULAR, 12.5, max_width):
                c.drawCentredString(center, y, line)
                y -= 0.65 * cm
            if y < 2 * cm:
                c.showPage()
                _draw_nr_background(c, w, h, nr_number)
                _draw_nr_logo(c, w, h, company_logo_url)
                y = h - 3 * cm

    c.showPage()
    c.save()
    return buf.getvalue()
