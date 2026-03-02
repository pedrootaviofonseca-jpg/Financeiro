import db_adapter
# ======================================================
# ADM DE OBRAS — SISTEMA DE CONTROLE (VERSÃO ORGANIZADA)
# UM ARQUIVO SÓ (MENU ÚNICO + PDF NO LUGAR CERTO + MATERIAIS FUNCIONANDO)
# ======================================================

import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, timedelta, datetime
import os

from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

# =========================
# PDF — GERAL (MÃO DE OBRA POR PERÍODO)
# (movido para fora do MENU para não quebrar o if/elif)
# =========================
def gerar_pdf_geral_mao_obra_periodo(df_periodo, periodo_num, periodo_ini, periodo_fim):
    """
    Gera PDF geral do período: obras + profissionais + totais (igual a interface).
    Recebe df_periodo já calculado (com colunas: obra_nome, profissional_nome, base, desconto_aditivo, total_final).
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    styles = getSampleStyleSheet()
    story = []

    def brl(v):
        try:
            return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return "R$ 0,00"

    # --- helper: ajusta larguras para caber exatamente na página ---
    def fit_width(widths_cm):
        avail = doc.width  # largura útil já considera margens
        widths = [w * cm for w in widths_cm]
        total = sum(widths)
        if total <= 0:
            return widths
        scale = avail / total
        return [w * scale for w in widths]

    # Título
    story.append(Paragraph("RELATÓRIO GERAL — MÃO DE OBRA", styles["Title"]))
    story.append(Paragraph(f"Período {periodo_num} ({iso_to_br(periodo_ini)} a {iso_to_br(periodo_fim)})", styles["Normal"]))
    story.append(Paragraph(f"Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    story.append(Spacer(1, 10))

    # Totais do período
    total_base = float(df_periodo["base"].sum())
    total_desc = float(df_periodo["desconto_aditivo"].sum())
    total_final = float(df_periodo["total_final"].sum())

    resumo = [
        ["TOTAL DO PERÍODO (Mão de Obra)", "DESCONTOS / ADITIVOS", "TOTAL + DESC/ADIT"],
        [brl(total_base), brl(total_desc), brl(total_final)],
    ]

    # (3 colunas proporcionais e auto-fit)
    tbl_resumo = Table(resumo, colWidths=fit_width([10.0, 8.5, 8.5]))
    tbl_resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
    ]))
    story.append(tbl_resumo)
    story.append(Spacer(1, 14))

    # Por obra
    obras_tot = (
        df_periodo.groupby(["obra_nome"], as_index=False)[["base", "desconto_aditivo", "total_final"]]
            .sum()
            .sort_values("total_final", ascending=False)
    )

    for _, ob in obras_tot.iterrows():
        obra_nome = ob["obra_nome"]
        story.append(Paragraph(f"Obra: <b>{obra_nome}</b>", styles["Heading2"]))
        story.append(Spacer(1, 6))

        df_o = df_periodo[df_periodo["obra_nome"] == obra_nome].copy()
        df_o = df_o.sort_values("total_final", ascending=False)

        data = [["Profissional", "Total no Período", "Desc/Adit", "Total + Desc/Adit"]]
        for _, r in df_o.iterrows():
            data.append([
                str(r["profissional_nome"]),
                brl(r["base"]),
                brl(r["desconto_aditivo"]),
                brl(r["total_final"]),
            ])

        # Total da obra
        data.append(["", "", "", ""])
        data.append([
            "TOTAL DA OBRA",
            brl(float(df_o["base"].sum())),
            brl(float(df_o["desconto_aditivo"].sum())),
            brl(float(df_o["total_final"].sum())),
        ])

        # (4 colunas proporcionais e auto-fit)
        tbl = Table(data, colWidths=fit_width([11.5, 5.5, 5.0, 5.3]), repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9d9d9")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -3), [colors.white, colors.HexColor("#f6f8fb")]),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e9eef6")),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 12))

    doc.build(story)
    buf.seek(0)
    return buf





# =========================
# PDF — PLANILHA (VALOR FECHADO / ACERTO / FECHAMENTO)
# =========================
def gerar_pdf_planilha_valor_fechado(
    df_planilha: pd.DataFrame,
    titulo: str,
    subtitulo: str = "",
):
    """Gera PDF (paisagem) da planilha: Profissional x Obra com
    Valor Fechado, Acerto e Fechamento.
    Espera colunas: Profissional, Obra, Valor Fechado, Acerto, Fechamento
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    styles = getSampleStyleSheet()
    story = []

    def brl(v):
        try:
            return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "R$ 0,00"

    # helper: ajusta larguras para caber exatamente na página
    def fit_width(widths_cm):
        avail = doc.width
        widths = [w * cm for w in widths_cm]
        total = sum(widths)
        if total <= 0:
            return widths
        scale = avail / total
        return [w * scale for w in widths]

    # Título
    story.append(Paragraph(str(titulo), styles["Title"]))
    if subtitulo:
        story.append(Paragraph(str(subtitulo), styles["Normal"]))
    story.append(Paragraph(f"Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    story.append(Spacer(1, 10))

    if df_planilha is None or df_planilha.empty:
        story.append(Paragraph("Sem dados para exibir.", styles["Normal"]))
        doc.build(story)
        buf.seek(0)
        return buf

    dfp = df_planilha.copy()

    # garante colunas
    for c in ["Profissional", "Obra", "Valor Fechado", "Acerto", "Fechamento"]:
        if c not in dfp.columns:
            dfp[c] = ""

    # numéricos
    dfp["Valor Fechado"] = pd.to_numeric(dfp["Valor Fechado"], errors="coerce").fillna(0.0)
    dfp["Acerto"] = pd.to_numeric(dfp["Acerto"], errors="coerce").fillna(0.0)
    dfp["Fechamento"] = pd.to_numeric(dfp["Fechamento"], errors="coerce").fillna(0.0)

    # Totais gerais
    total_vf = float(dfp["Valor Fechado"].sum())
    total_ac = float(dfp["Acerto"].sum())
    total_fech = float(dfp["Fechamento"].sum())

    resumo = [
        ["Valor Fechado (total)", "Acerto (total)", "Fechamento (total)"],
        [brl(total_vf), brl(total_ac), brl(total_fech)],
    ]

    tbl_resumo = Table(resumo, colWidths=fit_width([9.0, 9.0, 9.0]))
    tbl_resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
    ]))
    story.append(tbl_resumo)
    story.append(Spacer(1, 12))

    # Tabela principal
    data = [["Profissional", "Obra", "Valor Fechado", "Acerto", "Fechamento"]]

    for _, r in dfp.iterrows():
        data.append([
            str(r.get("Profissional", "") or ""),
            str(r.get("Obra", "") or ""),
            brl(r.get("Valor Fechado", 0.0)),
            brl(r.get("Acerto", 0.0)),
            brl(r.get("Fechamento", 0.0)),
        ])

    tbl = Table(data, colWidths=fit_width([10.5, 9.0, 5.5, 5.0, 5.5]), repeatRows=1)

    stl = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),

        ("ALIGN", (0, 0), (1, -1), "LEFT"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9d9d9")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fb")]),
    ])

    # destaca linhas TOTAL (Obra == "TOTAL")
    for i in range(1, len(data)):
        if str(data[i][1]).strip().upper() == "TOTAL":
            stl.add("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fff3cd"))
            stl.add("FONTNAME", (0, i), (-1, i), "Helvetica-Bold")

    tbl.setStyle(stl)
    story.append(tbl)

    doc.build(story)
    buf.seek(0)
    return buf


def gerar_pdf_recibos_mao_obra_por_obra_periodo(
    df_obra: pd.DataFrame,
    obra_nome: str,
    periodo_num: int,
    periodo_ini: str,
    periodo_fim: str,
    nome_empresa: str = "PEDRO FONSECA ENGENHARIA",
    logo_path: str = "logo.png",
):
    """Gera um PDF (A4 retrato) de recibos: 2 recibos por página com LOGO no topo."""
    if df_obra is None or df_obra.empty:
        return None

    from io import BytesIO
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    )
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from datetime import datetime
    import os

    def brl(v):
        try:
            return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "R$ 0,00"

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "rec_title",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=14,
        alignment=1,
        spaceAfter=6,
    )
    style_h = ParagraphStyle(
        "rec_h",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        spaceAfter=6,
    )
    style_n = ParagraphStyle(
        "rec_n",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=14,
        spaceAfter=4,
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
    )
    story = []

    df_print = df_obra.copy()
    if "Profissional" in df_print.columns:
        df_print["Profissional"] = df_print["Profissional"].astype(str)
        df_print = df_print.sort_values("Profissional")

    emissao_txt = datetime.now().strftime("%d/%m/%Y %H:%M")

    def montar_recibo_flowables(prof_nome: str, base: float):
        total = base

        dados = [
            ["Profissional", str(prof_nome)],
            ["Total no Período", brl(base)],
            ["TOTAL A RECEBER", brl(total)],
        ]
        tbl = Table(dados, colWidths=[6.0 * cm, 9.5 * cm])
        tbl.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfcfcf")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f5f7")),
            ("FONTNAME", (0, 0), (-1, -2), "Helvetica", 11),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold", 12),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fff3cd")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        bloco = []

        # LOGO + TÍTULO NA MESMA LINHA
        logo_element = ""
        if os.path.exists(logo_path):
            img = Image(logo_path)
            img.drawHeight = 2.2 * cm
            img.drawWidth = 4.0 * cm
            logo_element = img

        titulo_element = Paragraph(
            "RECIBO — PAGAMENTO DE MÃO DE OBRA",
            ParagraphStyle(
                "rec_title_right",
                parent=styles["Title"],
                fontName="Helvetica-Bold",
                fontSize=14,
                alignment=2,  # alinhado à direita
            ),
        )

        header_table = Table(
            [[logo_element, titulo_element]],
            colWidths=[5 * cm, None],
        )

        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

        bloco.append(header_table)
        bloco.append(Spacer(1, 8))

        bloco.append(Paragraph(f"<b>Empresa:</b> {nome_empresa}", style_n))
        bloco.append(Paragraph(f"<b>Obra:</b> {obra_nome}", style_n))
        bloco.append(Paragraph(
            f"<b>Período:</b> {periodo_num} ({iso_to_br(periodo_ini)} a {iso_to_br(periodo_fim)})",
            style_n
        ))
        bloco.append(Paragraph(f"<b>Emissão:</b> {emissao_txt}", style_n))
        bloco.append(Spacer(1, 6))

        bloco.append(Paragraph(
            f"Recebi de <b>{nome_empresa}</b> a importância abaixo referente aos serviços prestados:",
            style_n
        ))
        bloco.append(Spacer(1, 6))

        bloco.append(tbl)
        bloco.append(Spacer(1, 12))

        bloco.append(Paragraph("Assinatura do Profissional:", style_h))
        bloco.append(Spacer(1, 10))
        bloco.append(Paragraph("______________________________________________", style_n))
        bloco.append(Paragraph(f"{prof_nome}", style_n))

        return bloco

    recibos_pendentes = []

    for r in df_print.itertuples(index=False):
        prof_nome = getattr(r, "Profissional", "")
        base = float(getattr(r, "base", 0.0) or 0.0)

        recibos_pendentes.append(montar_recibo_flowables(prof_nome, base))

        if len(recibos_pendentes) == 2:
            pagina_tbl = Table(
                [[recibos_pendentes[0]], [recibos_pendentes[1]]],
                colWidths=[(A4[0] - doc.leftMargin - doc.rightMargin)],
            )
            pagina_tbl.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (0, 0), 0.6, colors.HexColor("#dcdcdc")),
            ]))
            story.append(pagina_tbl)
            story.append(PageBreak())
            recibos_pendentes = []

    if len(recibos_pendentes) == 1:
        vazio = [Spacer(1, 1)]
        pagina_tbl = Table(
            [[recibos_pendentes[0]], [vazio]],
            colWidths=[(A4[0] - doc.leftMargin - doc.rightMargin)],
        )
        story.append(pagina_tbl)

    doc.build(story)
    buf.seek(0)
    return buf


# =========================
# CONFIG STREAMLIT
# =========================
import base64

st.set_page_config(page_title="ADM de Obras", page_icon="🏗️", layout="wide")

st.markdown("""
<style>

/* ====== FUNDO AZUL ESCURO PREMIUM ====== */
.stApp{
  background: linear-gradient(180deg, #0B3C5D 0%, #0A2F4A 60%, #08263B 100%);
  color: #F1F5F9;
}

/* ================= SIDEBAR ================= */
section[data-testid="stSidebar"]{
  background: linear-gradient(180deg, #0B4F8A 0%, #1E73BE 55%, #00A86B 120%);
}

section[data-testid="stSidebar"] *{
  color: #ffffff !important;
}

/* ================= ÁREA PRINCIPAL ================= */

h1, h2, h3 { color: #ffffff; }
a { color: #4DA3FF; }

/* Texto geral branco */
div[data-testid="stAppViewContainer"]{
  color: #F1F5F9 !important;
}

/* Inputs com contraste */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div{
  background: rgba(255,255,255,0.08) !important;
  border: 1px solid rgba(255,255,255,0.15) !important;
  color: #ffffff !important;
}

div[data-baseweb="input"] input{
  color: #ffffff !important;
}

/* Labels */
div[data-testid="stAppViewContainer"] label{
  color: #E2E8F0 !important;
  font-weight: 600;
}

/* ================= CARDS ================= */
.card{
  background: rgba(255,255,255,0.95);
  color: #0b1220;
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 10px 26px rgba(0,0,0,0.25);
}

/* Separador */
.hr{
  height: 1px;
  background: rgba(255,255,255,0.15);
  margin: 18px 0;
}

/* ================= BOTÕES ================= */
.stButton > button,
div[data-testid="stFormSubmitButton"] > button{
  background: linear-gradient(180deg, #1E73BE, #0B4F8A) !important;
  border-radius: 12px !important;
  color: #ffffff !important;
  border: none !important;
}

.stButton > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover{
  filter: brightness(1.1);
}

/* ================= DATAFRAME ================= */
[data-testid="stDataFrame"]{
  border-radius: 14px;
  overflow: hidden;
  background: rgba(255,255,255,0.95);
}

/* ================= BARRA DE TÍTULO ================= */
.section-title{
  background: linear-gradient(90deg, #1E73BE, #0B4F8A);
  color: #ffffff;
  border-radius: 14px;
  padding: 10px 14px;
  margin: 14px 0 10px 0;
  font-weight: 800;
  box-shadow: 0 8px 18px rgba(0,0,0,0.25);
}

/* ================= BRANDING ================= */
.brandbar{
  background: linear-gradient(90deg, #0B4F8A 0%, #1E73BE 55%, #00A86B 100%);
  border-radius: 18px;
  padding: 14px 16px;
  margin-bottom: 14px;
  display: flex;
  gap: 14px;
  align-items: center;
  box-shadow: 0 10px 22px rgba(0,0,0,0.30);
}

.brandbar .title{
  color: #ffffff;
  font-weight: 900;
  font-size: 20px;
}

.brandbar .subtitle{
  color: rgba(255,255,255,0.85);
  font-weight: 600;
  font-size: 12px;
}

</style>
""", unsafe_allow_html=True)

# -------------------------
# HELPERS DE UI (iguais ao FÁBRICA)
# -------------------------
def section_title(texto: str):
    st.markdown(f'<div class="section-title">{texto}</div>', unsafe_allow_html=True)

def _find_logo_path():
    for nm in ("logo_app.png", "logo.png", "logo_app.jpg", "logo.jpg", "logo_app.jpeg", "logo.jpeg"):
        if os.path.exists(nm):
            return nm
    return None

def _img_to_data_uri(path_img: str) -> str:
    ext = os.path.splitext(path_img)[1].lower().replace(".", "")
    if ext == "jpg":
        ext = "jpeg"
    with open(path_img, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/{ext};base64,{b64}"

def render_branding():
    logo_path = _find_logo_path()

    with st.sidebar:
        if logo_path:
            st.image(logo_path, use_container_width=True)
        st.markdown("### 🏗️ ADM de Obras")
        st.caption("Cadastro • Execução • Relatórios")

    if logo_path:
        uri = _img_to_data_uri(logo_path)
        st.markdown(
            f"""
            <div class="brandbar">
              <img src="{uri}" style="height:56px; width:auto; border-radius:12px; background: rgba(255,255,255,0.12); padding:6px;" />
              <div>
                <div class="title">ADM de Obras</div>
                <div class="subtitle">PEDRO FONSECA ENGENHARIA E CONSTRUTORA</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div class="brandbar">
              <div>
                <div class="title">ADM de Obras</div>
                <div class="subtitle">Coloque um arquivo <b>logo_app.png</b> (ou logo.png) na mesma pasta do .py para aparecer aqui.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )

render_branding()


# =========================
# CONEXÃO COM BANCO
# =========================
DB_NAME = "banco_adm_obras.db"
conn = db_adapter.get_conn("banco_adm_obras.db", schema="adm_obras")
cursor = db_adapter.get_cursor(conn)

# =========================
# CRIAÇÃO DE TABELAS
# =========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS periodos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero INTEGER UNIQUE,
    dt_inicio TEXT,
    dt_fim TEXT,
    observacao TEXT
)
""")

# 🔹 NOVO: Pagamentos já feitos (por período + obra + profissional)
cursor.execute("""
CREATE TABLE IF NOT EXISTS pagamentos_mao_obra (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    periodo_id INTEGER NOT NULL,
    obra_id INTEGER NOT NULL,
    profissional_id INTEGER NOT NULL,
    valor_pago REAL NOT NULL DEFAULT 0,
    atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(periodo_id, obra_id, profissional_id)
)
""")

# 🔹 NOVO: Acertos (por período + obra + profissional)
cursor.execute("""
CREATE TABLE IF NOT EXISTS acertos_mao_obra (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    periodo_id INTEGER NOT NULL,
    obra_id INTEGER NOT NULL,
    profissional_id INTEGER NOT NULL,
    valor_acerto REAL NOT NULL DEFAULT 0,
    atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(periodo_id, obra_id, profissional_id)
)
""")

conn.commit()

# =========================
# MIGRAÇÃO DE SCHEMA (compatibilidade)
# =========================

# Alguns bancos antigos podem ter criado a coluna com nome errado.
# Garantimos que exista dt_inicio e copiamos valores caso necessário.
try:
    cols = [r[1] for r in cursor.execute("PRAGMA table_info(periodos)").fetchall()]
    if ("dt_inicio" not in cols) and ("dt_iniciocio" in cols):
        cursor.execute("ALTER TABLE periodos ADD COLUMN dt_inicio TEXT")
        cursor.execute("UPDATE periodos SET dt_inicio = dt_iniciocio WHERE dt_inicio IS NULL")
        conn.commit()
except Exception:
    # Não derrubar o app por falha de migração
    pass

# Migração: Encargos Extras (pago / pago_em)
# - adiciona colunas para controlar situação "PAGO" ou "ABERTO"
try:
    cols_enc = [r[1] for r in cursor.execute("PRAGMA table_info(encargos_extras)").fetchall()]
    if "pago" not in cols_enc:
        cursor.execute("ALTER TABLE encargos_extras ADD COLUMN pago INTEGER DEFAULT 0")
    if "pago_em" not in cols_enc:
        cursor.execute("ALTER TABLE encargos_extras ADD COLUMN pago_em TEXT")
    conn.commit()
except Exception:
    # Não derrubar o app por falha de migração
    pass


cursor.execute("""
CREATE TABLE IF NOT EXISTS obras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE,
    cliente TEXT,
    status TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS profissionais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE,
    funcao TEXT,
    diaria REAL,
    ativo INTEGER DEFAULT 1
)
""")


# Migração leve: adiciona coluna 'ativo' caso o banco já exista de versões antigas
try:
    cursor.execute("ALTER TABLE profissionais ADD COLUMN ativo INTEGER DEFAULT 1")
    conn.commit()
except Exception:
    # coluna já existe ou não é possível alterar (ok)
    pass

cursor.execute("""
CREATE TABLE IF NOT EXISTS obra_profissionais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    obra_id INTEGER,
    profissional_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS folha_semanal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    periodo_id INTEGER,
    obra_id INTEGER,
    profissional_id INTEGER,
    seg REAL DEFAULT 0,
    ter REAL DEFAULT 0,
    qua REAL DEFAULT 0,
    qui REAL DEFAULT 0,
    sex REAL DEFAULT 0,
    sab REAL DEFAULT 0,
    laje_aditivo REAL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS compras_notas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    obra_id INTEGER,
    periodo_id INTEGER,
    data TEXT,
    numero_nota TEXT,
    fornecedor TEXT,
    pago INTEGER DEFAULT 0,
    pago_em TEXT DEFAULT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS compras_itens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nota_id INTEGER,
    item TEXT,
    unidade TEXT,
    quantidade REAL,
    valor_unitario REAL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS encargos_extras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    obra_id INTEGER,
    periodo_id INTEGER,
    data TEXT,
    descricao TEXT,
    valor REAL,
    observacao TEXT,
    pago INTEGER DEFAULT 0,
    pago_em TEXT
)
""")
# Parâmetros do Relatório (por Obra + Período)
cursor.execute("""
CREATE TABLE IF NOT EXISTS relatorio_params (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    obra_id INTEGER,
    periodo_id INTEGER,
    semana INTEGER DEFAULT NULL,
    taxa_admin_pct REAL DEFAULT 20.0,
    estorno_valor REAL DEFAULT 0.0,
    estorno_desc TEXT DEFAULT '',
    cidade TEXT DEFAULT 'Dores do Indaiá',
    data_emissao TEXT DEFAULT NULL,
    UNIQUE(obra_id, periodo_id)
)
""")



# Configuração padrão por OBRA (cidade e taxa administrativa padrão)
cursor.execute("""
CREATE TABLE IF NOT EXISTS obra_config (
    obra_id INTEGER PRIMARY KEY,
    cidade_padrao TEXT DEFAULT 'Dores do Indaiá',
    taxa_admin_padrao REAL DEFAULT 20.0
)
""")

# Status do período por OBRA (aberto/fechado)
cursor.execute("""
CREATE TABLE IF NOT EXISTS obra_periodo_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    obra_id INTEGER,
    periodo_id INTEGER,
    fechado INTEGER DEFAULT 0,
    fechado_em TEXT DEFAULT NULL,
    reaberto_em TEXT DEFAULT NULL,
    UNIQUE(obra_id, periodo_id)
)
""")


conn.commit()

# =========================

def _ensure_column_exists(table_name: str, column_name: str, column_type: str):
    cursor.execute(f"PRAGMA table_info({table_name})")
    cols = [r[1] for r in cursor.fetchall()]
    if column_name not in cols:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
        conn.commit()

# garante colunas do relatorio_params (caso banco antigo)
_ensure_column_exists("relatorio_params", "semana", "INTEGER")
_ensure_column_exists("relatorio_params", "taxa_admin_pct", "REAL")
_ensure_column_exists("relatorio_params", "estorno_valor", "REAL")
_ensure_column_exists("relatorio_params", "estorno_desc", "TEXT")
_ensure_column_exists("relatorio_params", "cidade", "TEXT")
_ensure_column_exists("relatorio_params", "data_emissao", "TEXT")

# garante coluna data em compras_notas (caso banco antigo)
_ensure_column_exists("compras_notas", "data", "TEXT")
_ensure_column_exists("compras_notas", "pago", "INTEGER DEFAULT 0")
_ensure_column_exists("compras_notas", "pago_em", "TEXT")

# garante colunas de desconto e totais em compras_notas (caso banco antigo)
_ensure_column_exists("compras_notas", "desconto_valor", "REAL DEFAULT 0")
_ensure_column_exists("compras_notas", "desconto_tipo", "TEXT DEFAULT 'VALOR'")
_ensure_column_exists("compras_notas", "desconto_informado", "REAL DEFAULT 0")
_ensure_column_exists("compras_notas", "total_bruto", "REAL DEFAULT 0")
_ensure_column_exists("compras_notas", "total_liquido", "REAL DEFAULT 0")

# garante coluna unidade em compras_itens (caso banco antigo)
_ensure_column_exists("compras_itens", "unidade", "TEXT")

# =========================
# FUNÇÕES AUXILIARES
# =========================
import re

def safe_filename(texto: str, max_len: int = 120) -> str:
    s = str(texto or "")

    # remove caracteres de controle invisíveis (quebra de linha, tabs, etc.)
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)

    # remove caracteres proibidos no Windows
    s = re.sub(r'[<>:"/\\|?*]', "-", s)

    # normaliza espaços
    s = s.strip()
    s = re.sub(r"\s+", "_", s)

    # evita repetição de separadores
    s = re.sub(r"[-_]{2,}", "_", s)

    # windows não aceita terminar com ponto ou espaço
    s = s.strip(" ._-")

    if not s:
        s = "arquivo"

    return s[:max_len]


def save_relatorio_params(
    obra_id: int,
    periodo_id: int,
    semana,
    taxa_admin_pct: float,
    estorno_valor: float,
    estorno_desc: str,
    cidade: str,
    data_emissao_iso: str
):
    cfg = get_obra_config(obra_id) or {}

    if not cidade:
        cidade = str(cfg.get("cidade_padrao", "Dores do Indaiá"))

    cursor.execute("""
        INSERT INTO relatorio_params (
            obra_id,
            periodo_id,
            semana,
            taxa_admin_pct,
            estorno_valor,
            estorno_desc,
            cidade,
            data_emissao
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(obra_id, periodo_id)
        DO UPDATE SET
            semana=excluded.semana,
            taxa_admin_pct=excluded.taxa_admin_pct,
            estorno_valor=excluded.estorno_valor,
            estorno_desc=excluded.estorno_desc,
            cidade=excluded.cidade,
            data_emissao=excluded.data_emissao
    """, (
        obra_id,
        periodo_id,
        semana,
        taxa_admin_pct,
        estorno_valor,
        estorno_desc,
        cidade,
        data_emissao_iso
    ))

    conn.commit()

def iso_to_br(data_iso):
    if not data_iso:
        return ""
    return date.fromisoformat(str(data_iso)).strftime("%d/%m/%Y")

def calc_valor_semana(diaria):
    return round(float(diaria) * 6, 2)

def calc_valor_hora(diaria):
    return round((float(diaria) * 6) / 44, 4)

def moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def buscar_notas_com_itens(obra_id, periodo_id):
    """Retorna DataFrame com notas + itens (materiais) da obra/período, já com totais por nota.
    Usado tanto na tela de Materiais quanto nos PDFs de Relatórios.
    """
    cursor.execute("""
        SELECT
            n.id AS nota_id,
            n.data,
            n.numero_nota,
            n.fornecedor,
            COALESCE(n.desconto_valor, 0) AS desconto_valor,
            COALESCE(n.total_bruto, 0) AS total_bruto,
            COALESCE(n.total_liquido, 0) AS total_liquido,
            COALESCE(n.pago, 0) AS pago,
            n.pago_em,
            i.id AS item_id,
            i.item,
            i.unidade,
                i.quantidade,
            i.valor_unitario
        FROM compras_notas n
        LEFT JOIN compras_itens i ON i.nota_id = n.id
        WHERE n.obra_id=? AND n.periodo_id=?
        ORDER BY n.data DESC, n.id DESC, i.id ASC
    """, (obra_id, periodo_id))
    rows = cursor.fetchall()

    df = pd.DataFrame(rows, columns=[
        "NotaID", "DataISO", "Nota", "Fornecedor", "Desconto", "Total Bruto (salvo)", "Total Líquido (salvo)", "Pago", "PagoEm",
        "ItemID", "Item", "Unidade", "Quantidade", "Valor Unitário"
    ])

    if df.empty:
        return df

    df["Data"] = df["DataISO"].apply(iso_to_br)
    df["Pago"] = df["Pago"].fillna(0).astype(int)
    df["Status"] = df["Pago"].apply(lambda x: "PAGA" if int(x) == 1 else "ABERTA")
    df["Pago Em"] = df["PagoEm"].fillna("").astype(str)

    df["Desconto"] = pd.to_numeric(df["Desconto"], errors="coerce").fillna(0.0)
    df["Total Bruto (salvo)"] = pd.to_numeric(df["Total Bruto (salvo)"], errors="coerce").fillna(0.0)
    df["Total Líquido (salvo)"] = pd.to_numeric(df["Total Líquido (salvo)"], errors="coerce").fillna(0.0)

    df["Quantidade"] = df["Quantidade"].fillna(0)
    df["Valor Unitário"] = df["Valor Unitário"].fillna(0)
    df["Valor Item"] = (df["Quantidade"] * df["Valor Unitário"]).round(2)

    totais = df.groupby("NotaID")["Valor Item"].sum().round(2).to_dict()
    df["Total Bruto"] = df["NotaID"].apply(lambda x: totais.get(x, 0.0))

    # desconto e total líquido por NOTA (usa o salvo se existir; senão calcula)
    desc_map = df.groupby("NotaID")["Desconto"].first().fillna(0).to_dict()
    liq_map = df.groupby("NotaID")["Total Líquido (salvo)"].first().fillna(0).to_dict()

    def _total_liquido(nota_id):
        bruto = float(totais.get(nota_id, 0.0) or 0.0)
        desc = float(desc_map.get(nota_id, 0.0) or 0.0)
        liq_salvo = float(liq_map.get(nota_id, 0.0) or 0.0)
        if liq_salvo > 0:
            return round(liq_salvo, 2)
        # calcula pelo desconto (travando para não ficar negativo)
        return round(max(bruto - min(desc, bruto), 0.0), 2)

    total_liq_map = {nid: _total_liquido(nid) for nid in totais.keys()}
    df["Total Nota"] = df["NotaID"].apply(lambda x: total_liq_map.get(x, _total_liquido(x)))

    # ======================================================
    # NÃO REPETIR DADOS DA NOTA (mostrar só na primeira linha)
    # ======================================================
    df = df.sort_values(["NotaID", "ItemID"], na_position="last")

    colunas_repetidas = ["NotaID", "Data", "Nota", "Fornecedor", "Desconto", "Total Bruto", "Total Nota"]

    for nota_id, grupo in df.groupby("NotaID", dropna=False):
        idx = grupo.index.tolist()
        if len(idx) > 1:
            for col in colunas_repetidas:
                df.loc[idx[1:], col] = ""

    return df



def set_nota_pago(nota_id: int, pago: bool):
    """Marca uma nota como paga (1) ou aberta (0)."""
    try:
        pago_int = 1 if bool(pago) else 0
        pago_em = datetime.now().isoformat(timespec="seconds") if pago_int == 1 else None
        cursor.execute(
            "UPDATE compras_notas SET pago=?, pago_em=? WHERE id=?",
            (pago_int, pago_em, int(nota_id))
        )
        conn.commit()
    except Exception as e:
        st.error(f"Erro ao atualizar status da nota: {e}")

def set_encargo_pago(encargo_id: int, pago: bool):
    """Marca um encargo extra como pago (1) ou aberto (0)."""
    try:
        pago_int = 1 if bool(pago) else 0
        pago_em = datetime.now().isoformat(timespec="seconds") if pago_int == 1 else None
        cursor.execute(
            "UPDATE encargos_extras SET pago=?, pago_em=? WHERE id=?",
            (pago_int, pago_em, int(encargo_id))
        )
        conn.commit()
    except Exception as e:
        st.error(f"Erro ao atualizar status do encargo: {e}")



def get_periodos():
    cursor.execute("SELECT * FROM periodos ORDER BY numero DESC")
    return cursor.fetchall()

def get_obras():
    cursor.execute("SELECT * FROM obras ORDER BY nome")
    return cursor.fetchall()

def get_profissionais():
    cursor.execute("SELECT * FROM profissionais ORDER BY nome")
    return cursor.fetchall()

def get_profissionais_obra(obra_id):
    cursor.execute("""
        SELECT p.id, p.nome, p.funcao, p.diaria
        FROM profissionais p
        JOIN obra_profissionais op ON op.profissional_id = p.id
        WHERE op.obra_id = ?
        ORDER BY p.nome
    """, (obra_id,))
    return cursor.fetchall()

def style_total_row(row):
    if str(row.get("Profissional", "")).strip().upper() == "TOTAL":
        return ["background-color: #fff3cd; font-weight: bold; color: #000000"] * len(row)
    return [""] * len(row)

def styler_notas_grayscale(df: pd.DataFrame, nota_key: pd.Series | list | None = None):
    """Aplica um 'zebra' por NOTA (mesma NotaID = mesma cor), em tons de cinza.
    Funciona bem no tema escuro (usa rgba com branco bem leve).
    """
    if df is None or df.empty:
        return df

    shades = [
        "rgba(255,255,255,0.00)",
        "rgba(255,255,255,0.08)",
    ]

    if nota_key is None:
        # tenta usar a coluna NotaID (se existir)
        if "NotaID" in df.columns:
            nota_key = df["NotaID"]
        else:
            nota_key = pd.Series([None] * len(df))

    key = pd.Series(nota_key).copy()
    key = key.replace("", pd.NA).ffill()
    codes, _ = pd.factorize(key, sort=False)

    def _row_style(row):
        i = int(row.name)
        g = int(codes[i]) if (i >= 0 and i < len(codes) and codes[i] >= 0) else -1
        bg = shades[g % len(shades)] if g >= 0 else shades[0]
        return [f"background-color: {bg}"] * len(row)

    return df.style.apply(_row_style, axis=1)



# =========================
# PARÂMETROS DO RELATÓRIO (Obra + Período)
# =========================
def get_relatorio_params(obra_id: int, periodo_id: int):
    cursor.execute("""
        SELECT semana, taxa_admin_pct, estorno_valor, estorno_desc, cidade, data_emissao
        FROM relatorio_params
        WHERE obra_id=? AND periodo_id=?
    """, (obra_id, periodo_id))
    row = cursor.fetchone()

    # garante cfg SEMPRE definido (mesmo se não existir linha na tabela)
    cfg = get_obra_config(obra_id) or {}

    if row:
        return {
            "semana": row[0],
            "taxa_admin_pct": float(row[1] if row[1] is not None else cfg.get("taxa_admin_padrao", 20.0)),
            "estorno_valor": float(row[2] if row[2] is not None else 0.0),
            "estorno_desc": str(row[3] or ""),
            "cidade": str(row[4] if row[4] else cfg.get("cidade_padrao", "Dores do Indaiá")),
            "data_emissao": str(row[5] or "")
        }

    return {
        "semana": None,
        "taxa_admin_pct": float(cfg.get("taxa_admin_padrao", 20.0)),
        "estorno_valor": 0.0,
        "estorno_desc": "",
        "cidade": str(cfg.get("cidade_padrao", "Dores do Indaiá")),
        "data_emissao": ""
    }


# =========================
# CONFIG POR OBRA + FECHAMENTO DE PERÍODO
# =========================
def get_obra_config(obra_id: int):
    cursor.execute("SELECT cidade_padrao, taxa_admin_padrao FROM obra_config WHERE obra_id=?", (int(obra_id),))
    r = cursor.fetchone()
    if r:
        return {"cidade_padrao": str(r[0] or "Dores do Indaiá"), "taxa_admin_padrao": float(r[1] or 20.0)}
    return {"cidade_padrao": "Dores do Indaiá", "taxa_admin_padrao": 20.0}

def save_obra_config(obra_id: int, cidade_padrao: str, taxa_admin_padrao: float):
    cursor.execute("""
        INSERT INTO obra_config (obra_id, cidade_padrao, taxa_admin_padrao)
        VALUES (?, ?, ?)
        ON CONFLICT(obra_id) DO UPDATE SET
            cidade_padrao=excluded.cidade_padrao,
            taxa_admin_padrao=excluded.taxa_admin_padrao
    """, (int(obra_id), str(cidade_padrao or "Dores do Indaiá"), float(taxa_admin_padrao or 20.0)))
    conn.commit()

def get_periodo_status(obra_id: int, periodo_id: int):
    cursor.execute("""
        SELECT fechado, fechado_em, reaberto_em
        FROM obra_periodo_status
        WHERE obra_id=? AND periodo_id=?
    """, (int(obra_id), int(periodo_id)))
    r = cursor.fetchone()
    if r:
        return {"fechado": bool(r[0]), "fechado_em": str(r[1] or ""), "reaberto_em": str(r[2] or "")}
    return {"fechado": False, "fechado_em": "", "reaberto_em": ""}

def is_periodo_fechado(obra_id: int, periodo_id: int) -> bool:
    return bool(get_periodo_status(obra_id, periodo_id).get("fechado", False))

def set_periodo_fechado(obra_id: int, periodo_id: int, fechado: bool):
    now_iso = datetime.now().isoformat(timespec="seconds")
    if fechado:
        cursor.execute("""
            INSERT INTO obra_periodo_status (obra_id, periodo_id, fechado, fechado_em, reaberto_em)
            VALUES (?, ?, 1, ?, NULL)
            ON CONFLICT(obra_id, periodo_id) DO UPDATE SET
                fechado=1,
                fechado_em=?,
                reaberto_em=NULL
        """, (int(obra_id), int(periodo_id), now_iso, now_iso))
    else:
        cursor.execute("""
            INSERT INTO obra_periodo_status (obra_id, periodo_id, fechado, fechado_em, reaberto_em)
            VALUES (?, ?, 0, NULL, ?)
            ON CONFLICT(obra_id, periodo_id) DO UPDATE SET
                fechado=0,
                reaberto_em=?
        """, (int(obra_id), int(periodo_id), now_iso, now_iso))
    conn.commit()


# ======================================================
# PARTE PDF (REPORTLAB)
# ======================================================

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import (
        SimpleDocTemplate, BaseDocTemplate, Frame, PageTemplate,
        NextPageTemplate, PageBreak, Table, TableStyle, Paragraph, Spacer, Image
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False
    st.warning("Para exportar PDF, instale: pip install reportlab")

# Styles base do ReportLab (necessário para ParagraphStyle fora de funções)
styles = getSampleStyleSheet() if REPORTLAB_OK else None


def _parse_date_iso(s):
    try:
        return date.fromisoformat(str(s))
    except Exception:
        return None


def _br_short(d: date):
    return d.strftime("%d/%m") if isinstance(d, date) else ""


def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def _money_str(v):
    return moeda(_safe_float(v, 0.0))


def gerar_pdf_folha_por_obra(
    filename: str,
    titulo: str,
    periodo_texto: str,
    obra_texto: str,
    dt_inicio_periodo_iso: str,
    df_calc_raw: pd.DataFrame,
    df_profissionais_resumo: pd.DataFrame,
    logo_path: str = "logo.png"
):
    """PDF de Folha Semanal (por Obra) em paisagem."""
    if not REPORTLAB_OK:
        raise Exception("ReportLab não está instalado. Rode: pip install reportlab")

    styles_local = getSampleStyleSheet()

    style_title = ParagraphStyle(
        "title_center",
        parent=styles_local["Title"],
        alignment=1,
        fontName="Helvetica-Bold",
        fontSize=16,
        spaceAfter=0
    )

    style_center_bold_1 = ParagraphStyle(
        "center_bold_1",
        parent=styles_local["Normal"],
        alignment=1,
        fontName="Helvetica-Bold",
        fontSize=16,
        spaceAfter=0
    )

    style_center_bold_2 = ParagraphStyle(
        "center_bold_2",
        parent=styles_local["Normal"],
        alignment=1,
        fontName="Helvetica-Bold",
        fontSize=16,
        spaceAfter=0
    )

    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(A4),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm
    )

    elems = []

    logo_elem = ""
    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path)
            max_w = 6.5 * cm
            max_h = 2.4 * cm
            iw, ih = img.imageWidth, img.imageHeight
            if iw and ih:
                scale = min(max_w / iw, max_h / ih)
                img.drawWidth = iw * scale
                img.drawHeight = ih * scale
            logo_elem = img
        except Exception:
            logo_elem = ""

    titulo_para = Paragraph(titulo, style_title)

    header_table = Table([[logo_elem, titulo_para]], colWidths=[7.0 * cm, None])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elems.append(header_table)
    elems.append(Spacer(1, 10))

    elems.append(Paragraph(periodo_texto, style_center_bold_1))
    elems.append(Spacer(1, 10))
    elems.append(Paragraph(obra_texto, style_center_bold_2))
    elems.append(Spacer(1, 14))

    dt_inicio = _parse_date_iso(dt_inicio_periodo_iso)
    datas = []
    if dt_inicio:
        for i in range(6):
            datas.append(dt_inicio + timedelta(days=i))

    def hdr(dia, idx):
        if datas and idx < len(datas):
            return f"{dia}<br/>{_br_short(datas[idx])}"
        return dia

    col_headers = [
        "Profissional",
        "Função",
        hdr("Seg", 0),
        hdr("Ter", 1),
        hdr("Qua", 2),
        hdr("Qui", 3),
        hdr("Sex", 4),
        hdr("Sáb", 5),
        "Horas<br/>Trab.",
        "Laje/<br/>Aditivo",
        "Total<br/>Semana"
    ]

    data = []
    data.append([Paragraph(h, styles_local["BodyText"]) for h in col_headers])

    for _, r in df_calc_raw.iterrows():
        data.append([
            str(r.get("Profissional", "")),
            str(r.get("Função", "")),
            f"{_safe_float(r.get('Seg')):.2f}".replace(".", ","),
            f"{_safe_float(r.get('Ter')):.2f}".replace(".", ","),
            f"{_safe_float(r.get('Qua')):.2f}".replace(".", ","),
            f"{_safe_float(r.get('Qui')):.2f}".replace(".", ","),
            f"{_safe_float(r.get('Sex')):.2f}".replace(".", ","),
            f"{_safe_float(r.get('Sáb')):.2f}".replace(".", ","),
            f"{_safe_float(r.get('Horas Trabalhadas')):.2f}".replace(".", ","),
            _money_str(r.get("Laje/Aditivo")),
            _money_str(r.get("Total Semana")),
        ])

    total_seg = _safe_float(df_calc_raw["Seg"].sum() if "Seg" in df_calc_raw else 0)
    total_ter = _safe_float(df_calc_raw["Ter"].sum() if "Ter" in df_calc_raw else 0)
    total_qua = _safe_float(df_calc_raw["Qua"].sum() if "Qua" in df_calc_raw else 0)
    total_qui = _safe_float(df_calc_raw["Qui"].sum() if "Qui" in df_calc_raw else 0)
    total_sex = _safe_float(df_calc_raw["Sex"].sum() if "Sex" in df_calc_raw else 0)
    total_sab = _safe_float(df_calc_raw["Sáb"].sum() if "Sáb" in df_calc_raw else 0)
    total_horas = _safe_float(df_calc_raw["Horas Trabalhadas"].sum() if "Horas Trabalhadas" in df_calc_raw else 0)
    total_laje = _safe_float(df_calc_raw["Laje/Aditivo"].sum() if "Laje/Aditivo" in df_calc_raw else 0)
    total_semana = _safe_float(df_calc_raw["Total Semana"].sum() if "Total Semana" in df_calc_raw else 0)

    data.append([
        "TOTAL", "",
        f"{total_seg:.2f}".replace(".", ","),
        f"{total_ter:.2f}".replace(".", ","),
        f"{total_qua:.2f}".replace(".", ","),
        f"{total_qui:.2f}".replace(".", ","),
        f"{total_sex:.2f}".replace(".", ","),
        f"{total_sab:.2f}".replace(".", ","),
        f"{total_horas:.2f}".replace(".", ","),
        _money_str(total_laje),
        _money_str(total_semana),
    ])

    col_widths = [
        7.0 * cm, 3.2 * cm,
        1.35 * cm, 1.35 * cm, 1.35 * cm, 1.35 * cm, 1.35 * cm, 1.35 * cm,
        2.1 * cm, 2.2 * cm, 2.6 * cm
    ]

    t = Table(data, colWidths=col_widths, repeatRows=1)

    style = TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BOX", (0, 0), (-1, -1), 1.0, colors.grey),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
    ])

    for i in range(1, len(data)):
        if i % 2 == 0:
            style.add("BACKGROUND", (0, i), (-1, i), colors.whitesmoke)

    style.add("BACKGROUND", (0, len(data) - 1), (-1, len(data) - 1), colors.HexColor("#fff3cd"))
    style.add("FONT", (0, len(data) - 1), (-1, len(data) - 1), "Helvetica-Bold", 9)

    t.setStyle(style)
    elems.append(t)
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("Resumo de valores (referência para o cliente)", styles_local["Heading3"]))
    elems.append(Spacer(1, 6))

    resumo_data = [["Profissional", "Diária", "Valor Semanal"]]
    for _, r in df_profissionais_resumo.iterrows():
        resumo_data.append([
            str(r.get("Profissional", "")),
            _money_str(r.get("Diária")),
            _money_str(r.get("Valor Semanal"))
        ])

    resumo_table = Table(resumo_data, colWidths=[9.0 * cm, 3.0 * cm, 3.5 * cm])
    resumo_style = TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BOX", (0, 0), (-1, -1), 1.0, colors.grey),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 10),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ])

    for i in range(1, len(resumo_data)):
        if i % 2 == 0:
            resumo_style.add("BACKGROUND", (0, i), (-1, i), colors.whitesmoke)

    resumo_table.setStyle(resumo_style)
    elems.append(resumo_table)

    doc.build(elems)


# ======================================================
# RELATÓRIO FINANCEIRO (SEMANAL)
# ======================================================
def gerar_relatorio_financeiro_pdf(
    filename: str,
    obra_nome: str,
    periodo_num: int,
    dt_inicio_iso: str,
    dt_fim_iso: str,
    semana: int,
    cidade: str,
    data_emissao_iso: str,
    taxa_admin_pct: float,
    estorno_valor: float,
    estorno_desc: str,
    total_materiais: float,
    total_mao_obra: float,
    total_encargos: float,
    df_notas_detalhe: pd.DataFrame,
    df_folha_calc: pd.DataFrame,
    df_encargos: pd.DataFrame,
    df_historico: pd.DataFrame,
    logo_path: str = "logo.png",
    nome_empresa: str = "PEDRO FONSECA ENGENHARIA",
):
    """Gera o PDF semanal (multi-páginas) com páginas em pé e em paisagem.
    Marca d'água centralizada SOMENTE nas páginas 3 e 4.
    """
    if not REPORTLAB_OK:
        raise Exception("ReportLab não está instalado. Rode: pip install reportlab")

    from reportlab.lib.utils import ImageReader

    styles_local = getSampleStyleSheet()

    # ===== templates (portrait e landscape) =====
    doc = BaseDocTemplate(
        filename, pagesize=A4,
        leftMargin=1.2 * cm, rightMargin=1.2 * cm,
        topMargin=1.0 * cm, bottomMargin=1.0 * cm
    )

    # ===== Paleta do relatório =====
    COLORS = {
        "primary": colors.HexColor("#1F4E79"),
        "primary_light": colors.HexColor("#D9E2F3"),
        "zebra": colors.HexColor("#F7F7F7"),
        "grid": colors.HexColor("#9AA3AE"),
        "muted": colors.HexColor("#6B7280"),
        "highlight": colors.HexColor("#fff3cd"),
    }

    style_normal = ParagraphStyle(
        "rel_normal",
        parent=styles_local["Normal"],
        fontSize=10,
        leading=12,
        textColor=colors.black,
    )

    def _br_date(iso):
        try:
            return date.fromisoformat(str(iso)).strftime("%d/%m/%Y")
        except Exception:
            return ""

    # =========================
    # DATA DE EMISSÃO (texto)
    # =========================
    if data_emissao_iso:
        data_emissao_txt = _br_date(data_emissao_iso)
    else:
        data_emissao_txt = _br_date(date.today().isoformat())

    # =========================
    # CÁLCULOS (garante admin_val e total_periodo)
    # =========================
    admin_val = round(float(total_mao_obra or 0.0) * float(taxa_admin_pct or 0.0) / 100.0, 2)
    estorno_val = float(estorno_valor or 0.0)
    total_periodo = round(
        float(total_materiais or 0.0) + float(total_mao_obra or 0.0) + admin_val + float(total_encargos or 0.0) - estorno_val,
        2
    )

    # =========================
    # BARRA DE SEÇÃO (faltava)
    # =========================
    def _section_bar(texto: str):
        sec_txt = ParagraphStyle(
            "sec_text",
            parent=style_normal,
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=colors.white,
        )
        t = Table([[Paragraph(f"<b>{texto}</b>", sec_txt)]], colWidths=[doc.width])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLORS["primary"]),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return t

    # =========================
    # TABELA PADRÃO (faltava)
    # =========================
    def _tbl(data, colWidths, font_size=9, header_bg=None, header_fg=None, align_right_cols=None):
        if header_bg is None:
            header_bg = COLORS["primary"]
        if header_fg is None:
            header_fg = colors.white
        align_right_cols = align_right_cols or []

        t = Table(data, colWidths=colWidths, repeatRows=1)

        stl = TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", font_size),
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), header_fg),

            ("FONT", (0, 1), (-1, -1), "Helvetica", font_size),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),

            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),

            ("GRID", (0, 0), (-1, -1), 0.35, COLORS["grid"]),
            ("BOX", (0, 0), (-1, -1), 0.9, COLORS["grid"]),
        ])

        # zebra
        for i in range(1, len(data)):
            if i % 2 == 0:
                stl.add("BACKGROUND", (0, i), (-1, i), COLORS["zebra"])

        # alinhar colunas numéricas à direita (linhas 1..fim)
        for c in align_right_cols:
            stl.add("ALIGN", (c, 1), (c, -1), "RIGHT")

        t.setStyle(stl)
        return t

    # ===== FRAMES =====
    frame_p = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="frame_p")

    wL, hL = landscape(A4)
    frame_l = Frame(
        doc.leftMargin, doc.bottomMargin,
        wL - doc.leftMargin - doc.rightMargin,
        hL - doc.topMargin - doc.bottomMargin,
        id="frame_l"
    )

    # =========================
    # FUNDO DA CAPA (Cover)
    # =========================
    def _cover_bg(canvas, doc_):
        canvas.saveState()
        w, h = A4

        canvas.setFillColor(COLORS["primary"])
        canvas.rect(0, 0, 2.2 * cm, h, fill=1, stroke=0)

        canvas.setFillColor(COLORS["primary_light"])
        p = canvas.beginPath()
        p.moveTo(0, h * 0.35)
        p.lineTo(w, h * 0.05)
        p.lineTo(w, 0)
        p.lineTo(0, 0)
        p.close()
        canvas.drawPath(p, fill=1, stroke=0)

        canvas.restoreState()

    # =========================
    # PREPARA WATERMARK
    # =========================
    wm_reader = None
    wm_w, wm_h = None, None
    if logo_path and os.path.exists(logo_path):
        try:
            wm_reader = ImageReader(logo_path)
            wm_w, wm_h = wm_reader.getSize()
        except Exception:
            wm_reader = None
            wm_w, wm_h = None, None

    def _draw_watermark(canvas, doc_):
        """Marca d'água centralizada SOMENTE nas páginas 3 e 4."""
        if doc_.page not in (3, 4):
            return
        if not wm_reader or not wm_w or not wm_h:
            return

        pw, ph = doc_.pagesize
        scale = min((pw * 0.65) / wm_w, (ph * 0.65) / wm_h)

        draw_w = wm_w * scale
        draw_h = wm_h * scale

        x = (pw - draw_w) / 2.0
        y = (ph - draw_h) / 2.0

        canvas.saveState()
        try:
            canvas.setFillAlpha(0.08)
            canvas.setStrokeAlpha(0.08)
        except Exception:
            pass

        canvas.drawImage(
            wm_reader,
            x, y,
            width=draw_w,
            height=draw_h,
            mask="auto",
            preserveAspectRatio=True,
            anchor="c"
        )
        canvas.restoreState()

    # =========================
    # CABEÇALHO / RODAPÉ
    # =========================
    def _header_footer(canvas, doc_):
        canvas.saveState()

        # watermark atrás (só pág 3 e 4)
        _draw_watermark(canvas, doc_)

        # linha superior
        canvas.setStrokeColor(COLORS["primary"])
        canvas.setLineWidth(1.5)
        canvas.line(
            doc_.leftMargin,
            doc_.pagesize[1] - doc_.topMargin + 0.15 * cm,
            doc_.pagesize[0] - doc_.rightMargin,
            doc_.pagesize[1] - doc_.topMargin + 0.15 * cm
        )

        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(COLORS["primary"])
        canvas.drawString(
            doc_.leftMargin,
            doc_.pagesize[1] - doc_.topMargin + 0.35 * cm,
            str(obra_nome)
        )

        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(COLORS["muted"])
        canvas.drawRightString(
            doc_.pagesize[0] - doc_.rightMargin,
            doc_.pagesize[1] - doc_.topMargin + 0.35 * cm,
            f"Semana {semana if semana else '--'} | Período {periodo_num}"
        )

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(COLORS["muted"])
        canvas.drawString(doc_.leftMargin, 0.75 * cm, nome_empresa)
        canvas.drawRightString(doc_.pagesize[0] - doc_.rightMargin, 0.75 * cm, f"Página {doc_.page}")

        canvas.restoreState()

    template_cover = PageTemplate(id="Cover", frames=[frame_p], pagesize=A4, onPage=_cover_bg)
    template_p = PageTemplate(id="Portrait", frames=[frame_p], pagesize=A4, onPage=_header_footer)
    template_l = PageTemplate(id="Landscape", frames=[frame_l], pagesize=landscape(A4), onPage=_header_footer)
    doc.addPageTemplates([template_cover, template_p, template_l])

    # =========================
    # ELEMENTOS DO PDF
    # =========================
    elems = []

    # ======================================================
    # CAPA (Cover)
    # ======================================================
    elems.append(NextPageTemplate("Cover"))

    style_cover_title = ParagraphStyle(
        "cover_title",
        parent=styles_local["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        alignment=1,
        textColor=colors.black,
        leading=22,
        spaceAfter=2,
    )

    style_cover_cliente = ParagraphStyle(
        "cover_cliente",
        parent=styles_local["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        alignment=1,
        textColor=colors.black,
        leading=20,
    )

    style_cover_week = ParagraphStyle(
        "cover_week",
        parent=styles_local["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        alignment=1,
        textColor=colors.black,
        leading=18,
    )

    style_cover_period = ParagraphStyle(
        "cover_period",
        parent=styles_local["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        alignment=1,
        textColor=colors.black,
        leading=14,
    )

    style_cover_footer = ParagraphStyle(
        "cover_footer",
        parent=styles_local["Normal"],
        fontSize=10,
        alignment=1,
        textColor=colors.HexColor("#111111"),
        leading=12,
    )

    periodo_txt_cover = f"Período {periodo_num} — {_br_date(dt_inicio_iso)} a {_br_date(dt_fim_iso)}"
    semana_txt_cover = f"SEMANA {int(semana):02d}" if semana else "SEMANA --"
    data_footer = f"{cidade}, {data_emissao_txt}"

    # ✅ LOGO DA CAPA (blindado)
    logo_big = ""
    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path)
            max_w = 15.0 * cm
            max_h = 7.0 * cm
            iw, ih = img.imageWidth, img.imageHeight
            if iw and ih:
                scale = min(max_w / iw, max_h / ih)
                img.drawWidth = iw * scale
                img.drawHeight = ih * scale
            logo_big = img
        except Exception:
            logo_big = ""

    if logo_big:
        logo_tbl = Table([[logo_big]], colWidths=[doc.width])
        logo_tbl.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
    else:
        logo_tbl = None

    elems.append(Spacer(1, 28))
    elems.append(Paragraph("RELATÓRIO FINANCEIRO SEMANAL", style_cover_title))
    elems.append(Paragraph("DE OBRA", style_cover_title))

    elems.append(Spacer(1, 52))
    elems.append(Paragraph(str(obra_nome), style_cover_cliente))

    elems.append(Spacer(1, 48))
    if logo_tbl:
        elems.append(logo_tbl)

    elems.append(Spacer(1, 48))
    elems.append(Paragraph(semana_txt_cover, style_cover_week))
    elems.append(Spacer(1, 18))
    elems.append(Paragraph(periodo_txt_cover, style_cover_period))

    elems.append(Spacer(1, 60))
    elems.append(Paragraph(data_footer, style_cover_footer))
    elems.append(Spacer(1, 6))
    elems.append(Paragraph(nome_empresa, style_cover_footer))

    # Página 2 portrait
    elems.append(NextPageTemplate("Portrait"))
    elems.append(PageBreak())

    # ======================================================
    # PRESTAÇÃO DE CONTAS (portrait) ✅ página 2
    # ======================================================
    elems.append(_section_bar("PRESTAÇÃO DE CONTAS"))
    elems.append(Spacer(1, 10))

    resumo = [
        ["Item", "Valor (R$)"],
        ["1. Valores Estornados", moeda(estorno_val)],
        ["   Descrição do Estorno", (estorno_desc or "-")],
        ["2. Notas (Materiais)", moeda(total_materiais)],
        ["3. Mão de Obra (somatório)", moeda(total_mao_obra)],
        [f"   3.2 Taxa Administrativa ({float(taxa_admin_pct or 0):.2f}%)", moeda(admin_val)],
        ["4. Encargos Extras", moeda(total_encargos)],
        ["5. VALOR TOTAL DO PERÍODO", moeda(total_periodo)],
    ]

    resumo_tbl = _tbl(resumo, colWidths=[12.0 * cm, 5.0 * cm], font_size=10, align_right_cols=[1])

    idx_total = len(resumo) - 1
    resumo_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, idx_total), (-1, idx_total), COLORS["highlight"]),
        ("FONT", (0, idx_total), (-1, idx_total), "Helvetica-Bold", 11),
    ]))

    elems.append(resumo_tbl)
    elems.append(Spacer(1, 10))
    elems.append(Paragraph("Obs.: Valores calculados automaticamente pelo sistema (Obra + Período).", style_normal))

    # ======================================================
    # NOTAS (regras do relatório) ✅ ainda na página 2
    # ======================================================
    elems.append(Spacer(1, 12))
    elems.append(Paragraph("<b>Notas:</b>", style_normal))
    elems.append(Spacer(1, 6))

    elems.append(Paragraph(
        "• O Contratante terá 1 (um) dia para análise e aprovação deste relatório. "
        "Caso não haja manifestação nesse prazo, este documento dar-se-á como aprovado.<br/><br/>"
        "• O Contratante terá 2 (dois) dias para pagamento integral do valor apresentado após a aprovação do relatório. "
        "Em caso de atraso, será cobrada taxa de 0,18% ao dia e, após 10 (dez) dias, será aplicada multa de 2% "
        "e taxa de 0,18% ao dia, ambas relativas ao valor apresentado.<br/><br/>"
        "• O Contratado não terá responsabilidade quanto a pagamento de material comprado para a obra.<br/><br/>"
        "• Em caso de atraso superior a 3 (três) semanas, as obras serão paralisadas até que todos os débitos sejam quitados.",
        style_normal
    ))

    # Página 3 landscape
    elems.append(NextPageTemplate("Landscape"))
    elems.append(PageBreak())

    # ======================================================
    # DETALHAMENTO DAS NOTAS (landscape) ✅ página 3
    # ======================================================
    elems.append(_section_bar("DETALHAMENTO DAS NOTAS"))
    elems.append(Spacer(1, 6))

    if df_notas_detalhe is None or df_notas_detalhe.empty:
        elems.append(Paragraph("Nenhuma nota lançada neste período.", style_normal))
    else:
        cols = ["Data", "Nota", "Fornecedor", "Item", "Qtd", "Vlr Unit", "Vlr da Nota", "Vlr C/ Desc."]
        data_tbl = [cols]
        for _, r in df_notas_detalhe.iterrows():
            data_tbl.append([
                str(r.get("Data", "")),
                str(r.get("Nota", "")),
                str(r.get("Fornecedor", "")),
                str(r.get("Item", "")),
                f"{_safe_float(r.get('Quantidade')):.2f}".replace(".", ","),
                moeda(_safe_float(r.get("Valor Unitário"))),
                moeda(_safe_float(r.get("Valor Item"))),
                moeda(_safe_float(r.get("Total Nota"))),
            ])
        elems.append(_tbl(
            data_tbl,
            colWidths=[2.2 * cm, 2.0 * cm, 4.2 * cm, 7.2 * cm, 1.6 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm],
            font_size=8,
            align_right_cols=[4, 5, 6, 7]
        ))

    # Página 4 portrait
    elems.append(NextPageTemplate("Portrait"))
    elems.append(PageBreak())

    # ======================================================
    # ESTUDO FINANCEIRO (portrait) ✅ página 4
    # ======================================================
    elems.append(_section_bar("ESTUDO FINANCEIRO"))
    elems.append(Spacer(1, 6))

    if df_historico is None or df_historico.empty:
        elems.append(Paragraph("Sem histórico para exibir.", style_normal))
    else:
        hist_cols = ["Período", "Início", "Fim", "Valor do Período", "Total Acumulado"]
        hist_data = [hist_cols]
        for _, r in df_historico.iterrows():
            hist_data.append([
                str(r.get("Período", "")),
                str(r.get("Início", "")),
                str(r.get("Fim", "")),
                moeda(_safe_float(r.get("Valor do Período"))),
                moeda(_safe_float(r.get("Total Acumulado"))),
            ])
        elems.append(_tbl(
            hist_data,
            colWidths=[2.2 * cm, 3.0 * cm, 3.0 * cm, 5.0 * cm, 5.0 * cm],
            font_size=9,
            align_right_cols=[3, 4]
        ))

    # Página 5 landscape
    elems.append(NextPageTemplate("Landscape"))
    elems.append(PageBreak())

    # ======================================================
    # FOLHA DE PAGAMENTO (landscape) ✅ página 5
    # ======================================================
    elems.append(_section_bar("FOLHA DE PAGAMENTO"))
    elems.append(Spacer(1, 6))

    if df_folha_calc is None or df_folha_calc.empty:
        elems.append(Paragraph("Sem dados de mão de obra neste período.", style_normal))
    else:
        folha_cols = ["Profissional", "Função", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Horas", "Vlr Hora", "Laje/Aditivo", "Total"]
        folha_data = [folha_cols]
        for _, r in df_folha_calc.iterrows():
            folha_data.append([
                str(r.get("Profissional", "")),
                str(r.get("Função", "")),
                f"{_safe_float(r.get('Seg')):.2f}".replace(".", ","),
                f"{_safe_float(r.get('Ter')):.2f}".replace(".", ","),
                f"{_safe_float(r.get('Qua')):.2f}".replace(".", ","),
                f"{_safe_float(r.get('Qui')):.2f}".replace(".", ","),
                f"{_safe_float(r.get('Sex')):.2f}".replace(".", ","),
                f"{_safe_float(r.get('Sáb')):.2f}".replace(".", ","),
                f"{_safe_float(r.get('Horas Trabalhadas')):.2f}".replace(".", ","),
                moeda(_safe_float(r.get("Valor Hora"))),
                moeda(_safe_float(r.get("Laje/Aditivo"))),
                moeda(_safe_float(r.get("Total Semana"))),
            ])

        total_folha = float(df_folha_calc["Total Semana"].sum() if "Total Semana" in df_folha_calc.columns else 0.0)
        folha_data.append(["TOTAL", "", "", "", "", "", "", "", "", "", "", moeda(total_folha)])

        elems.append(_tbl(
            folha_data,
            colWidths=[5.2 * cm, 3.0 * cm, 1.3 * cm, 1.3 * cm, 1.3 * cm, 1.3 * cm, 1.3 * cm, 1.3 * cm, 1.6 * cm, 1.8 * cm, 2.2 * cm, 2.2 * cm],
            font_size=8,
            align_right_cols=[2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        ))

    # Página 6 portrait
    elems.append(NextPageTemplate("Portrait"))
    elems.append(PageBreak())

    # ======================================================
    # ENCARGOS (portrait) ✅ página 6
    # ======================================================
    elems.append(_section_bar("ENCARGOS EXTRAS"))
    elems.append(Spacer(1, 6))

    if df_encargos is None or df_encargos.empty:
        elems.append(Paragraph("Nenhum encargo lançado neste período.", style_normal))
    else:
        enc_cols = ["Data", "Descrição", "Valor", "Obs"]
        enc_data = [enc_cols]
        for _, r in df_encargos.iterrows():
            enc_data.append([
                str(r.get("Data", "")),
                str(r.get("Descrição", "")),
                moeda(_safe_float(r.get("Valor"))),
                str(r.get("Obs", "")),
            ])
        elems.append(_tbl(
            enc_data,
            colWidths=[3.0 * cm, 9.0 * cm, 3.0 * cm, 4.0 * cm],
            font_size=9,
            align_right_cols=[2]
        ))

    elems.append(PageBreak())

    # ======================================================
    # ENCERRAMENTO (portrait)
    # ======================================================
    elems.append(NextPageTemplate("Portrait"))
    elems.append(_section_bar("ENCERRAMENTO"))
    elems.append(Spacer(1, 10))
    elems.append(Paragraph("Aproveitamos o ensejo para agradecer a confiança em nossos serviços.", style_normal))
    elems.append(Spacer(1, 10))
    elems.append(Paragraph("Permanecemos à disposição.", style_normal))
    elems.append(Spacer(1, 22))
    elems.append(Paragraph("<b>Atenciosamente,</b>", style_normal))
    elems.append(Spacer(1, 40))
    elems.append(Paragraph(f"<b>{nome_empresa}</b>", style_normal))
    elems.append(Spacer(1, 6))
    elems.append(Paragraph("Engenharia e Construções", style_normal))

    doc.build(elems)



def gerar_relatorio_mensal_pdf(
    filename: str,
    obra_nome: str,
    mes: int,
    ano: int,
    cidade: str,
    data_emissao_iso: str,
    df_consolidado: pd.DataFrame,
    total_mes: float,
    logo_path: str = "logo.png",
    nome_empresa: str = "PEDRO FONSECA ENGENHARIA"
):
    """Gera PDF consolidado do mês por OBRA."""
    if not REPORTLAB_OK:
        raise Exception("ReportLab não está instalado. Rode: pip install reportlab")

    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle(
        "m_normal",
        parent=styles["Normal"],
        fontSize=10,
        leading=12
    )
    style_title = ParagraphStyle(
        "m_title",
        parent=styles["Title"],
        alignment=1,
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=colors.HexColor("#1F4E79"),
        spaceAfter=8
    )
    style_section = ParagraphStyle(
        "m_section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=colors.HexColor("#1F4E79"),
        spaceBefore=10,
        spaceAfter=6
    )

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=1.6*cm,
        rightMargin=1.6*cm,
        topMargin=1.3*cm,
        bottomMargin=1.3*cm
    )

    elems = []

    # Cabeçalho
    logo_elem = ""
    if os.path.exists(logo_path):
        try:
            img = Image(logo_path)
            max_w = 6.0 * cm
            max_h = 2.2 * cm
            iw, ih = img.imageWidth, img.imageHeight
            if iw and ih:
                scale = min(max_w / iw, max_h / ih)
                img.drawWidth = iw * scale
                img.drawHeight = ih * scale
            logo_elem = img
        except Exception:
            logo_elem = ""

    titulo_para = Paragraph("RELATÓRIO FINANCEIRO MENSAL DE OBRA", style_title)
    header_table = Table([[logo_elem, titulo_para]], colWidths=[7.0*cm, None])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    elems.append(header_table)
    elems.append(Spacer(1, 10))

    meses = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    elems.append(Paragraph(f"<b>Obra:</b> {obra_nome}", style_normal))
    elems.append(Paragraph(f"<b>Mês:</b> {meses[int(mes)]}/{int(ano)}", style_normal))
    elems.append(Paragraph(f"{cidade}, {iso_to_br(data_emissao_iso)}", style_normal))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("Consolidado por Período", style_section))

    # Tabela consolidada
    cols = ["Período", "Datas", "Materiais", "Mão de obra", "Taxa adm", "Encargos", "Estornos", "Total período", "Acumulado"]
    data = [cols]

    def _fmt_money(v):
        return moeda(_safe_float(v))

    for _, r in df_consolidado.iterrows():
        data.append([
            str(r.get("Periodo", "")),
            str(r.get("Datas", "")),
            _fmt_money(r.get("Materiais", 0)),
            _fmt_money(r.get("MaoObra", 0)),
            _fmt_money(r.get("TaxaAdm", 0)),
            _fmt_money(r.get("Encargos", 0)),
            _fmt_money(r.get("Estornos", 0)),
            _fmt_money(r.get("TotalPeriodo", 0)),
            _fmt_money(r.get("Acumulado", 0)),
        ])

    # Linha total
    data.append([
        "TOTAL", "",
        _fmt_money(df_consolidado["Materiais"].sum() if "Materiais" in df_consolidado else 0),
        _fmt_money(df_consolidado["MaoObra"].sum() if "MaoObra" in df_consolidado else 0),
        _fmt_money(df_consolidado["TaxaAdm"].sum() if "TaxaAdm" in df_consolidado else 0),
        _fmt_money(df_consolidado["Encargos"].sum() if "Encargos" in df_consolidado else 0),
        _fmt_money(df_consolidado["Estornos"].sum() if "Estornos" in df_consolidado else 0),
        _fmt_money(total_mes),
        _fmt_money(total_mes),
    ])

    col_widths = [1.5*cm, 3.0*cm, 2.2*cm, 2.2*cm, 2.0*cm, 2.0*cm, 2.0*cm, 2.2*cm, 2.2*cm]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    ts = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9AA3AE")),
    ])
    # zebra
    for i in range(1, len(data)-1):
        if i % 2 == 0:
            ts.add("BACKGROUND", (0, i), (-1, i), colors.whitesmoke)
    # total highlight
    ts.add("BACKGROUND", (0, len(data)-1), (-1, len(data)-1), colors.HexColor("#fff3cd"))
    ts.add("FONT", (0, len(data)-1), (-1, len(data)-1), "Helvetica-Bold", 9)
    t.setStyle(ts)
    elems.append(t)

    elems.append(Spacer(1, 14))
    elems.append(Paragraph("Encerramento", style_section))
    elems.append(Paragraph("Agradecemos a confiança e permanecemos à disposição para quaisquer esclarecimentos.", style_normal))
    elems.append(Spacer(1, 8))
    elems.append(Paragraph(f"<b>{nome_empresa}</b>", style_normal))

    doc.build(elems)


# ======================================================
# MENU
# ======================================================
st.sidebar.title("Menu")

# Seção (radio) + submenu (radio)
st.sidebar.markdown("### Seção")
secao = st.sidebar.radio(
    "",
    ["🧩 Cadastro", "🏗️ Execução de Obras"],
    index=0,
    key="secao_menu"
)

menu_itens = {
    "🧩 Cadastro": ["📅 Períodos", "🏢 Obras", "👷 Profissionais"],
    "🏗️ Execução de Obras": [
        "👥 Equipe da Obra",
        "🗓️ Folha Semanal (Obra)",
        "🧱 Materiais & Encargos",
        "📊 Relatório de Obras",
        "👷 Relatório de Mão de Obra",
        "📌 Folha de Pagamento",  # <-- alterado aqui
        "📁 Controle de Notas",
        "💸 Controle de Encargos Extras"
    ],
}
pagina_rotulo = st.sidebar.radio(
    "Navegação",
    menu_itens.get(secao, []),
    key="pagina_menu"
)

# Converte o rótulo (com emoji) para o nome real das páginas já usadas no resto do código
pagina = pagina_rotulo.split(" ", 1)[1] if " " in pagina_rotulo else pagina_rotulo

# ======================================================
# PÁGINA: PERÍODOS
# ======================================================
if pagina == "Períodos":
    st.subheader("Cadastro de Períodos")

    # ===== Lista de períodos =====
    rows = get_periodos()
    df_lista = pd.DataFrame(rows, columns=["ID", "Número", "Início", "Fim", "Obs"])
    if not df_lista.empty:
        df_lista["Início"] = df_lista["Início"].apply(iso_to_br)
        df_lista["Fim"] = df_lista["Fim"].apply(iso_to_br)

    st.markdown("### Períodos cadastrados")
    st.dataframe(df_lista, use_container_width=True, hide_index=True)

    st.markdown("---")
    modo = st.radio("Modo", ["Novo", "Editar", "Excluir"], horizontal=True, key="modo_periodos")

    # Próximo número sugerido
    proximo_numero = 1
    try:
        if rows:
            proximo_numero = int(max([int(r[1]) for r in rows if r[1] is not None] + [0])) + 1
    except Exception:
        proximo_numero = 1

    # Helpers
    def _contar(sql, params):
        cursor.execute(sql, params)
        r = cursor.fetchone()
        return int(r[0] or 0) if r else 0



    # ======================================================
    # NOVO
    # ======================================================
    if modo == "Novo":
        st.markdown("### Novo Período")

        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            numero = st.number_input("Número do Período", min_value=1, step=1, value=int(proximo_numero), key="p_num_novo")
        with col2:
            dt_inicio = st.date_input("Data início (Segunda)", value=date.today(), key="p_ini_novo")
        with col3:
            dt_fim = st.date_input("Data fim (Sexta ou Sábado)", value=date.today(), key="p_fim_novo")

        obs = st.text_input("Observação (opcional)", value="", key="p_obs_novo")

        confirmar = st.checkbox("Confirmo que quero salvar este período", key="conf_salvar_periodo_novo")
        if st.button("💾 Salvar período", disabled=not confirmar, key="btn_salvar_periodo_novo"):
            cursor.execute("""
                INSERT INTO periodos (numero, dt_inicio, dt_fim, observacao)
                VALUES (?, ?, ?, ?)
            """, (int(numero), dt_inicio.isoformat(), dt_fim.isoformat(), obs.strip()))
            conn.commit()
            st.success("Período criado!")
            st.rerun()

    # ======================================================
    # EDITAR
    # ======================================================
    elif modo == "Editar":
        st.markdown("### Editar Período")

        if df_lista.empty:
            st.info("Não há períodos para editar.")
            st.stop()

        periodos_raw = get_periodos()  # (id, numero, dt_inicio, dt_fim, observacao)
        periodos_map = {
            f"ID {p[0]} — Período {p[1]} ({iso_to_br(p[2])} a {iso_to_br(p[3])})": p[0]
            for p in periodos_raw
        }

        escolha = st.selectbox("Escolha um período", list(periodos_map.keys()), key="p_escolha_editar")
        periodo_id = int(periodos_map[escolha])

        cursor.execute("SELECT id, numero, dt_inicio, dt_fim, observacao FROM periodos WHERE id=?", (periodo_id,))
        p = cursor.fetchone()
        numero_padrao = int(p[1] or 1)
        dt_inicio_padrao = date.fromisoformat(p[2]) if p and p[2] else date.today()
        dt_fim_padrao = date.fromisoformat(p[3]) if p and p[3] else date.today()
        obs_padrao = str(p[4] or "") if p else ""

        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            numero = st.number_input("Número do Período", min_value=1, step=1, value=int(numero_padrao), key="p_num_edit")
        with col2:
            dt_inicio = st.date_input("Data início (Segunda)", value=dt_inicio_padrao, key="p_ini_edit")
        with col3:
            dt_fim = st.date_input("Data fim (Sexta ou Sábado)", value=dt_fim_padrao, key="p_fim_edit")

        obs = st.text_input("Observação (opcional)", value=obs_padrao, key="p_obs_edit")

        confirmar = st.checkbox("Confirmo que quero salvar as alterações", key="conf_salvar_periodo_edit")
        if st.button("💾 Salvar alterações", disabled=not confirmar, key="btn_salvar_periodo_edit"):
            cursor.execute("""
                UPDATE periodos
                SET numero=?, dt_inicio=?, dt_fim=?, observacao=?
                WHERE id=?
            """, (int(numero), dt_inicio.isoformat(), dt_fim.isoformat(), obs.strip(), int(periodo_id)))
            conn.commit()
            st.success("Período atualizado!")
            st.rerun()

    # ======================================================
    # EXCLUIR
    # ======================================================
    else:
        st.markdown("### Excluir Período")

        if df_lista.empty:
            st.info("Não há períodos para excluir.")
            st.stop()

        periodos_raw = get_periodos()
        periodos_map = {
            f"ID {p[0]} — Período {p[1]} ({iso_to_br(p[2])} a {iso_to_br(p[3])})": p[0]
            for p in periodos_raw
        }

        escolha = st.selectbox("Escolha um período para excluir", list(periodos_map.keys()), key="p_escolha_excluir")
        periodo_id = int(periodos_map[escolha])

        # Contagens (para avisar antes de apagar)
        c_folha = _contar("SELECT COUNT(*) FROM folha_semanal WHERE periodo_id=?", (periodo_id,))
        c_notas = _contar("SELECT COUNT(*) FROM compras_notas WHERE periodo_id=?", (periodo_id,))
        c_enc   = _contar("SELECT COUNT(*) FROM encargos_extras WHERE periodo_id=?", (periodo_id,))
        c_stat  = _contar("SELECT COUNT(*) FROM obra_periodo_status WHERE periodo_id=?", (periodo_id,))
        c_rel   = _contar("SELECT COUNT(*) FROM relatorio_params WHERE periodo_id=?", (periodo_id,))

        st.warning(
            "Atenção: excluir um período pode apagar lançamentos vinculados a ele.\n\n"
            f"• Folha semanal: **{c_folha}** registros\n"
            f"• Notas de compras: **{c_notas}** registros\n"
            f"• Encargos extras: **{c_enc}** registros\n"
            f"• Status (obra/período): **{c_stat}** registros\n"
            f"• Relatório params: **{c_rel}** registros"
        )

        digite = st.text_input('Digite EXCLUIR para confirmar', value="", key="p_digite_excluir")
        confirmar = (digite.strip().upper() == "EXCLUIR")

        if st.button("🗑️ Excluir período", disabled=not confirmar, key="btn_excluir_periodo"):
            # Apaga dependências
            cursor.execute(
                "DELETE FROM compras_itens WHERE nota_id IN (SELECT id FROM compras_notas WHERE periodo_id=?)",
                (periodo_id,)
            )
            cursor.execute("DELETE FROM compras_notas WHERE periodo_id=?", (periodo_id,))
            cursor.execute("DELETE FROM folha_semanal WHERE periodo_id=?", (periodo_id,))
            cursor.execute("DELETE FROM encargos_extras WHERE periodo_id=?", (periodo_id,))
            cursor.execute("DELETE FROM obra_periodo_status WHERE periodo_id=?", (periodo_id,))
            cursor.execute("DELETE FROM relatorio_params WHERE periodo_id=?", (periodo_id,))
            cursor.execute("DELETE FROM periodos WHERE id=?", (periodo_id,))

            conn.commit()
            st.success("Período excluído!")
            st.rerun()

elif pagina == "Obras":
    st.subheader("Cadastro de Obras")

    obras = get_obras()
    df_obras = pd.DataFrame(obras, columns=["ID", "Obra", "Cliente", "Status"]) if obras else pd.DataFrame(columns=["ID", "Obra", "Cliente", "Status"])

    st.markdown("### Obras cadastradas")
    st.dataframe(df_obras, use_container_width=True, hide_index=True)

    st.markdown("---")
    modo = st.radio("Modo", ["Novo", "Editar", "Excluir"], horizontal=True, key="modo_obras")

    # ======================================================
    # NOVO
    # ======================================================
    if modo == "Novo":
        st.markdown("### Nova Obra")
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            nome = st.text_input("Nome da Obra", key="o_nome_novo")
        with col2:
            cliente = st.text_input("Cliente (opcional)", key="o_cliente_novo")
        with col3:
            status = st.selectbox("Status", ["Ativa", "Pausada", "Concluída"], key="o_status_novo")

        confirmar = st.checkbox("Confirmo que quero salvar esta obra", key="conf_salvar_obra_nova")

        if st.button("💾 Salvar obra", disabled=not confirmar, key="btn_salvar_obra_nova"):
            if not nome.strip():
                st.warning("Informe o nome da obra.")
            else:
                cursor.execute(
                    "INSERT INTO obras (nome, cliente, status) VALUES (?, ?, ?)",
                    (nome.strip(), cliente.strip(), status)
                )
                conn.commit()
                st.success("Obra criada!")
                st.rerun()

    # ======================================================
    # EDITAR
    # ======================================================
    elif modo == "Editar":
        st.markdown("### Editar Obra")

        if df_obras.empty:
            st.info("Não há obras para editar.")
            st.stop()

        obra_map = {f"ID {o[0]} — {o[1]}": o[0] for o in obras}
        obra_label = st.selectbox("Escolha uma obra", list(obra_map.keys()), key="o_escolha_edit")
        obra_id = int(obra_map[obra_label])

        cursor.execute("SELECT nome, cliente, status FROM obras WHERE id=?", (obra_id,))
        row = cursor.fetchone()
        nome_atual, cliente_atual, status_atual = row if row else ("", "", "Ativa")

        col1e, col2e, col3e = st.columns([2, 2, 1])
        with col1e:
            nome_edit = st.text_input("Nome da Obra", value=nome_atual, key="o_nome_edit")
        with col2e:
            cliente_edit = st.text_input("Cliente (opcional)", value=cliente_atual or "", key="o_cliente_edit")
        with col3e:
            status_opcoes = ["Ativa", "Pausada", "Concluída"]
            idx_status = status_opcoes.index(status_atual) if status_atual in status_opcoes else 0
            status_edit = st.selectbox("Status", status_opcoes, index=idx_status, key="o_status_edit")

        confirmar = st.checkbox("Confirmo que quero salvar as alterações", key="conf_salvar_obra_edit")

        if st.button("💾 Salvar alterações", disabled=not confirmar, key="btn_salvar_obra_edit"):
            if not nome_edit.strip():
                st.warning("Informe o nome da obra.")
            else:
                cursor.execute(
                    "UPDATE obras SET nome=?, cliente=?, status=? WHERE id=?",
                    (nome_edit.strip(), cliente_edit.strip(), status_edit, obra_id)
                )
                conn.commit()
                st.success("Obra atualizada!")
                st.rerun()

    # ======================================================
    # EXCLUIR
    # ======================================================
    else:
        st.markdown("### Excluir Obra")

        if df_obras.empty:
            st.info("Não há obras para excluir.")
            st.stop()

        obra_map = {f"ID {o[0]} — {o[1]}": o[0] for o in obras}
        obra_label = st.selectbox("Escolha uma obra para excluir", list(obra_map.keys()), key="o_escolha_del")
        obra_id = int(obra_map[obra_label])

        st.warning("Atenção: a exclusão remove também todos os lançamentos vinculados à obra (folha, notas, itens, encargos, equipe).")

        digite = st.text_input('Digite EXCLUIR para confirmar', value="", key="o_digite_excluir")
        confirmar = (digite.strip().upper() == "EXCLUIR")

        if st.button("🗑️ Excluir obra", disabled=not confirmar, key="btn_excluir_obra"):
            # Remove dependências (para não sobrar dados órfãos)
            cursor.execute("DELETE FROM folha_semanal WHERE obra_id=?", (obra_id,))
            cursor.execute("DELETE FROM obra_profissionais WHERE obra_id=?", (obra_id,))
            cursor.execute(
                "DELETE FROM compras_itens WHERE nota_id IN (SELECT id FROM compras_notas WHERE obra_id=?)",
                (obra_id,)
            )
            cursor.execute("DELETE FROM compras_notas WHERE obra_id=?", (obra_id,))
            cursor.execute("DELETE FROM encargos_extras WHERE obra_id=?", (obra_id,))
            cursor.execute("DELETE FROM obra_periodo_status WHERE obra_id=?", (obra_id,))
            cursor.execute("DELETE FROM relatorio_params WHERE obra_id=?", (obra_id,))
            cursor.execute("DELETE FROM obras WHERE id=?", (obra_id,))

            conn.commit()
            st.success("Obra excluída!")
            st.rerun()

elif pagina == "Equipe da Obra":
    st.subheader("Definir equipe da obra")
    st.markdown("---")

    # 🔹 Carregar obras
    obras = get_obras()
    obra_map = {o[1]: o[0] for o in obras}
    obra_escolha = st.selectbox("Escolha a obra", list(obra_map.keys()))
    obra_id = obra_map[obra_escolha]

    # 🔹 Carregar profissionais
    profs = get_profissionais()
    prof_map = {p[1]: p[0] for p in profs}

    # 🔹 Buscar equipe já vinculada à obra
    cursor.execute(
        "SELECT profissional_id FROM obra_profissionais WHERE obra_id=?",
        (obra_id,)
    )
    atuais = [r[0] for r in cursor.fetchall()]
    default = [nome for nome, pid in prof_map.items() if pid in atuais]

    # 🔹 Multiselect de profissionais
    selecionados = st.multiselect(
        "Profissionais desta obra",
        options=list(prof_map.keys()),
        default=default
    )

    # 🔹 Mostrar equipe atual em tabela
    cursor.execute("""
        SELECT p.nome
        FROM profissionais p
        JOIN obra_profissionais op ON op.profissional_id = p.id
        WHERE op.obra_id = ?
        ORDER BY p.nome
    """, (obra_id,))
    equipe_atual = cursor.fetchall()

    st.markdown("### Equipe atual da obra")
    if equipe_atual:
        df_equipe = pd.DataFrame(equipe_atual, columns=["Profissional"])
        st.dataframe(df_equipe, use_container_width=True, hide_index=True)
    else:
        st.caption("Nenhum profissional vinculado a esta obra.")

    # 🔹 Salvar equipe
    if st.button("Salvar equipe"):
        cursor.execute(
            "DELETE FROM obra_profissionais WHERE obra_id=?",
            (obra_id,)
        )
        for nome in selecionados:
            cursor.execute(
                "INSERT INTO obra_profissionais (obra_id, profissional_id) VALUES (?, ?)",
                (obra_id, int(prof_map[nome]))
            )
        conn.commit()
        st.success("Equipe salva com sucesso!")
        st.rerun()


# PÁGINA: PROFISSIONAIS
# ======================================================
elif pagina == "Profissionais":
    st.subheader("Cadastro de Profissionais")

    # ======================================================
    # NOVO / EDITAR / EXCLUIR + ATIVO
    # ======================================================
    profs_raw = get_profissionais()  # SELECT * (pode vir com ou sem coluna ativo, dependendo da migração)
    colunas = ["ID", "Nome", "Função", "Diária"] + (["Ativo"] if profs_raw and len(profs_raw[0]) >= 5 else [])
    df_profs = pd.DataFrame(profs_raw, columns=colunas) if profs_raw else pd.DataFrame(columns=colunas)

    st.markdown("### Profissionais cadastrados")
    if not df_profs.empty:
        if "Ativo" in df_profs.columns:
            df_profs["Ativo"] = df_profs["Ativo"].fillna(1).astype(int).apply(lambda x: "Sim" if int(x) == 1 else "Não")
        df_profs["Semanal"] = df_profs["Diária"].apply(calc_valor_semana).apply(moeda)
        df_profs["Hora"] = df_profs["Diária"].apply(calc_valor_hora).apply(moeda)
        df_profs["Diária"] = df_profs["Diária"].apply(moeda)

    st.dataframe(df_profs, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### Criar / Editar / Excluir Profissional")

    modo = st.radio("Modo", ["Novo", "Editar", "Excluir"], horizontal=True)

    # Defaults
    prof_id = None
    nome_padrao = ""
    funcao_padrao = ""
    diaria_padrao = 0.0
    ativo_padrao = True

    if modo in ["Editar", "Excluir"]:
        if df_profs.empty:
            st.info("Não há profissionais cadastrados.")
            st.stop()

        # Monta mapa de seleção
        # profs_raw: pode ter 4 ou 5 colunas
        prof_map = {}
        for p in profs_raw:
            pid = int(p[0])
            pnome = p[1]
            pfunc = p[2] if len(p) > 2 else ""
            pati = (int(p[4]) == 1) if len(p) >= 5 and p[4] is not None else True
            status = "Ativo" if pati else "Inativo"
            prof_map[f"ID {pid} — {pnome} ({pfunc}) [{status}]"] = pid

        escolha = st.selectbox("Escolha um profissional", list(prof_map.keys()))
        prof_id = int(prof_map[escolha])

        cursor.execute("SELECT id, nome, funcao, diaria, COALESCE(ativo, 1) FROM profissionais WHERE id=?", (prof_id,))
        row = cursor.fetchone()
        if row:
            nome_padrao = row[1] or ""
            funcao_padrao = row[2] or ""
            diaria_padrao = float(row[3] or 0.0)
            ativo_padrao = (int(row[4]) == 1)

    if modo in ["Novo", "Editar"]:
        col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
        with col1:
            nome = st.text_input("Nome do Profissional", value=nome_padrao)
        with col2:
            funcao = st.text_input("Função", value=funcao_padrao)
        with col3:
            diaria = st.number_input("Diária (R$)", min_value=0.0, step=10.0, value=float(diaria_padrao))
        with col4:
            ativo = st.checkbox("Ativo", value=ativo_padrao)

        if diaria > 0:
            st.caption(f"Valor semanal: {moeda(calc_valor_semana(diaria))} | Valor hora: {moeda(calc_valor_hora(diaria))}")

        if modo == "Novo":
            if st.button("✅ Salvar Profissional"):
                if not nome.strip():
                    st.warning("Informe o nome.")
                elif diaria <= 0:
                    st.warning("Informe a diária.")
                else:
                    cursor.execute(
                        "INSERT INTO profissionais (nome, funcao, diaria, ativo) VALUES (?, ?, ?, ?)",
                        (nome.strip(), funcao.strip(), float(diaria), 1 if ativo else 0)
                    )
                    conn.commit()
                    st.success("Profissional salvo!")
                    st.rerun()

        if modo == "Editar":
            if st.button("💾 Salvar alterações"):
                if not nome.strip():
                    st.warning("Informe o nome.")
                elif diaria <= 0:
                    st.warning("Informe a diária.")
                else:
                    cursor.execute(
                        "UPDATE profissionais SET nome=?, funcao=?, diaria=?, ativo=? WHERE id=?",
                        (nome.strip(), funcao.strip(), float(diaria), 1 if ativo else 0, int(prof_id))
                    )
                    conn.commit()
                    st.success("Profissional atualizado!")
                    st.rerun()

    if modo == "Excluir":
        st.warning("⚠️ Excluir é definitivo. Se o profissional já foi usado em lançamentos, o recomendado é marcar como INATIVO.")
        confirmar = st.checkbox("Confirmo que quero excluir este profissional", value=False)

        if st.button("🗑️ Excluir profissional", disabled=not confirmar):
            # Bloqueia exclusão se houver uso em folha/equipe (evita quebrar histórico)
            cursor.execute("SELECT COUNT(*) FROM folha_semanal WHERE profissional_id=?", (int(prof_id),))
            usado_folha = int(cursor.fetchone()[0] or 0)

            cursor.execute("SELECT COUNT(*) FROM obra_profissionais WHERE profissional_id=?", (int(prof_id),))
            usado_equipe = int(cursor.fetchone()[0] or 0)

            if usado_folha > 0 or usado_equipe > 0:
                st.error(
                    f"Não foi possível excluir: este profissional já está vinculado a registros "
                    f"(Folha: {usado_folha}, Equipe: {usado_equipe}). "
                    f"Marque como INATIVO em vez de excluir."
                )
            else:
                cursor.execute("DELETE FROM profissionais WHERE id=?", (int(prof_id),))
                conn.commit()
                st.success("Profissional excluído!")
                st.rerun()

# ======================================================
# PÁGINA: FOLHA SEMANAL (OBRA)
# ======================================================

elif pagina == "Folha Semanal (Obra)":
    st.subheader("Folha Semanal — Por Obra (Período + Obra)")

    periodos = get_periodos()
    obras = get_obras()

    if not periodos:
        st.warning("Cadastre pelo menos 1 período.")
        st.stop()
    if not obras:
        st.warning("Cadastre pelo menos 1 obra.")
        st.stop()

    periodo_map = {f"Período {p[1]} ({iso_to_br(p[2])} a {iso_to_br(p[3])})": p[0] for p in periodos}
    obra_map = {o[1]: o[0] for o in obras}

    colA, colB = st.columns(2)
    with colA:
        periodo_label = st.selectbox("Período", list(periodo_map.keys()))
        periodo_id = int(periodo_map[periodo_label])
    with colB:
        obra_label = st.selectbox("Obra", list(obra_map.keys()))
        obra_id = int(obra_map[obra_label])

    # Status do período (aberto/fechado) para esta obra
    fechado_fs = is_periodo_fechado(obra_id, periodo_id)
    if fechado_fs:
        st.warning("⚠️ Este período está FECHADO para esta obra. A folha está em modo somente leitura.")

    equipe = get_profissionais_obra(obra_id)
    if not equipe:
        st.warning("Essa obra não tem equipe cadastrada. Vá em 'Equipe da Obra' no menu e defina a equipe.")
        st.stop()

    # garante linhas no banco
    for p in equipe:
        prof_id = int(p[0])
        cursor.execute("""
            SELECT id FROM folha_semanal
            WHERE periodo_id=? AND obra_id=? AND profissional_id=?
        """, (periodo_id, obra_id, prof_id))
        existe = cursor.fetchone()
        if not existe:
            cursor.execute("""
                INSERT INTO folha_semanal (periodo_id, obra_id, profissional_id, seg, ter, qua, qui, sex, sab, laje_aditivo)
                VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0, 0)
            """, (periodo_id, obra_id, prof_id))
    conn.commit()

    # carrega dados
    cursor.execute("""
        SELECT fs.id, p.nome, p.funcao, p.diaria, fs.seg, fs.ter, fs.qua, fs.qui, fs.sex, fs.sab, fs.laje_aditivo
        FROM folha_semanal fs
        JOIN profissionais p ON p.id = fs.profissional_id
        WHERE fs.periodo_id=? AND fs.obra_id=?
        ORDER BY p.nome
    """, (periodo_id, obra_id))
    rows = cursor.fetchall()

    df = pd.DataFrame(rows, columns=[
        "FS_ID", "Profissional", "Função", "Diária",
        "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb",
        "Laje/Aditivo"
    ])

    st.markdown("### Lançar horas (grade)")
    df_edit = df[["FS_ID", "Profissional", "Função", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Laje/Aditivo"]].copy()

    edited = st.data_editor(
        df_edit,
        use_container_width=True,
        disabled=(["FS_ID","Profissional","Função"] if not fechado_fs else ["FS_ID","Profissional","Função","Seg","Ter","Qua","Qui","Sex","Sáb","Laje/Aditivo"]),
        num_rows="fixed"
    )

    if st.button("Salvar Folha", disabled=fechado_fs):
        for _, r in edited.iterrows():
            cursor.execute("""
                UPDATE folha_semanal
                SET seg=?, ter=?, qua=?, qui=?, sex=?, sab=?, laje_aditivo=?
                WHERE id=?
            """, (
                float(r["Seg"] or 0),
                float(r["Ter"] or 0),
                float(r["Qua"] or 0),
                float(r["Qui"] or 0),
                float(r["Sex"] or 0),
                float(r["Sáb"] or 0),
                float(r["Laje/Aditivo"] or 0),
                int(r["FS_ID"])
            ))
        conn.commit()
        st.success("Folha salva!")
        st.rerun()

    df_calc = df.copy()
    df_calc["Valor Semanal"] = df_calc["Diária"].apply(calc_valor_semana)
    df_calc["Valor Hora"] = df_calc["Diária"].apply(calc_valor_hora)
    df_calc["Horas Trabalhadas"] = df_calc[["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]].sum(axis=1)
    df_calc["Total Semana"] = (df_calc["Horas Trabalhadas"] * df_calc["Valor Hora"] + df_calc["Laje/Aditivo"]).round(2)

    total_geral = df_calc["Total Semana"].sum()
    st.metric("TOTAL SEMANAL (Obra)", moeda(total_geral))

    st.markdown("---")
    st.markdown("### Visualização com cálculos (com TOTAL)")

    df_view = df_calc[[
        "Profissional", "Função",
        "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb",
        "Horas Trabalhadas",
        "Laje/Aditivo",
        "Diária", "Valor Semanal", "Valor Hora",
        "Total Semana"
    ]].copy()

    for c in ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Horas Trabalhadas"]:
        df_view[c] = df_view[c].apply(lambda x: f"{float(x):.2f}".replace(".", ","))

    df_view["Laje/Aditivo"] = df_view["Laje/Aditivo"].apply(moeda)
    df_view["Diária"] = df_view["Diária"].apply(moeda)
    df_view["Valor Semanal"] = df_view["Valor Semanal"].apply(moeda)
    df_view["Valor Hora"] = df_view["Valor Hora"].apply(lambda x: moeda(x))
    df_view["Total Semana"] = df_view["Total Semana"].apply(moeda)

    total_row = {
        "Profissional": "TOTAL",
        "Função": "",
        "Seg": f"{df_calc['Seg'].sum():.2f}".replace(".", ","),
        "Ter": f"{df_calc['Ter'].sum():.2f}".replace(".", ","),
        "Qua": f"{df_calc['Qua'].sum():.2f}".replace(".", ","),
        "Qui": f"{df_calc['Qui'].sum():.2f}".replace(".", ","),
        "Sex": f"{df_calc['Sex'].sum():.2f}".replace(".", ","),
        "Sáb": f"{df_calc['Sáb'].sum():.2f}".replace(".", ","),
        "Horas Trabalhadas": f"{df_calc['Horas Trabalhadas'].sum():.2f}".replace(".", ","),
        "Laje/Aditivo": moeda(df_calc["Laje/Aditivo"].sum()),
        "Diária": "",
        "Valor Semanal": "",
        "Valor Hora": "",
        "Total Semana": moeda(df_calc["Total Semana"].sum())
    }

    df_view = pd.concat([df_view, pd.DataFrame([total_row])], ignore_index=True)
    st.dataframe(df_view.style.apply(style_total_row, axis=1), use_container_width=True)

    # =========================
    # BOTÃO PDF (FICA AQUI DENTRO)
    # =========================
    st.markdown("---")
    if not REPORTLAB_OK:
        st.info("Para exportar PDF, instale: pip install reportlab")
    else:
        cursor.execute("SELECT numero, dt_inicio, dt_fim FROM periodos WHERE id=?", (periodo_id,))
        per = cursor.fetchone()
        if per:
            per_num, per_ini, per_fim = per
            periodo_txt_pdf = f"Período {per_num} ({iso_to_br(per_ini)} a {iso_to_br(per_fim)})"
            dt_inicio_pdf = per_ini
        else:
            periodo_txt_pdf = periodo_label
            dt_inicio_pdf = None

        obra_txt_pdf = f"Obra: {obra_label}"
        df_resumo = df_calc[["Profissional", "Diária"]].copy()
        df_resumo["Valor Semanal"] = df_resumo["Diária"].apply(calc_valor_semana)

        if st.button("Exportar PDF da Folha (Obra)"):
            nome_pdf = f"Folha_Obra_{obra_label}_Periodo_{periodo_id}.pdf".replace(" ", "_").replace("/", "-")
            try:
                logo_use = "logo.png" if os.path.exists("logo.png") else ("logo.jpg" if os.path.exists("logo.jpg") else "logo.png")
                gerar_pdf_folha_por_obra(
                    filename=nome_pdf,
                    titulo="FOLHA SEMANAL — POR OBRA",
                    periodo_texto=periodo_txt_pdf,
                    obra_texto=obra_txt_pdf,
                    dt_inicio_periodo_iso=dt_inicio_pdf,
                    df_calc_raw=df_calc.copy(),
                    df_profissionais_resumo=df_resumo.copy(),
                    logo_path=logo_use
                )
                st.success("PDF gerado com sucesso!")
                st.download_button("Baixar PDF", data=open(nome_pdf, "rb"), file_name=nome_pdf)
            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")

# ======================================================
# ======================================================
# PÁGINA: RELATÓRIOS
# ======================================================

# ======================================================
# PÁGINA: MATERIAIS & ENCARGOS
# ======================================================
elif pagina == "Materiais & Encargos":
    st.subheader("📦 Materiais & Encargos (por Obra + Período)")
    st.caption("Lançamento de notas/itens de materiais e encargos extras. Respeita o fechamento do período por obra.")
    st.markdown("---")

    periodos = get_periodos()
    obras = get_obras()

    if not periodos:
        st.warning("Cadastre pelo menos 1 período.")
        st.stop()
    if not obras:
        st.warning("Cadastre pelo menos 1 obra.")
        st.stop()

    periodo_map = {f"Período {p[1]} ({iso_to_br(p[2])} a {iso_to_br(p[3])})": int(p[0]) for p in periodos}
    obra_map = {o[1]: int(o[0]) for o in obras}

    c1, c2 = st.columns(2)
    with c1:
        periodo_label_me = st.selectbox("Período", list(periodo_map.keys()), key="me_periodo")
        periodo_id_me = int(periodo_map[periodo_label_me])
    with c2:
        obra_label_me = st.selectbox("Obra", list(obra_map.keys()), key="me_obra")
        obra_id_me = int(obra_map[obra_label_me])

    fechado_me = is_periodo_fechado(obra_id_me, periodo_id_me)
    if fechado_me:
        st.warning("⚠️ Este período está FECHADO para esta obra. Materiais e encargos estão em modo somente leitura.")

    tab_mat, tab_enc = st.tabs(["🧱 Materiais (Notas + Itens)", "🧾 Encargos extras"])

    # =========================
    # MATERIAIS
    # =========================
    with tab_mat:
        st.markdown("### 🧱 Notas e Itens")

        # --- NOVA NOTA + ITENS (tudo junto)
        with st.expander("➕ Lançar nova NOTA (com itens)", expanded=False):
            with st.form("form_nova_nota_com_itens", clear_on_submit=True):
                cA, cB, cC = st.columns([1, 1, 2])
                with cA:
                    dt_nota = st.date_input("Data", value=date.today(), key="me_dt_nota")
                with cB:
                    numero_nota = st.text_input("Nº Nota", value="", key="me_num_nota")
                with cC:
                    fornecedor = st.text_input("Fornecedor", value="", key="me_fornecedor")

                st.caption("Itens da nota (adicione linhas se precisar).")
                df_novos = pd.DataFrame(
                    [{"Item": "", "Unidade": "", "Quantidade": 0.0, "Valor unitário": 0.0}]
                )

                editor = st.data_editor(
                    df_novos,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="dynamic",
                    disabled=fechado_me,
                    column_config={
                        "Item": st.column_config.TextColumn("Item"),
                        "Unidade": st.column_config.TextColumn("Unidade", help="Ex.: un, m, m², kg, cx"),
                        "Quantidade": st.column_config.NumberColumn("Quantidade", min_value=0.0, step=1.0),
                        "Valor unitário": st.column_config.NumberColumn("Valor unitário", min_value=0.0, step=0.01, format="%.2f"),
                    },
                    key="me_itens_nota_editor",
                )

                # --- DESCONTO + TOTAIS (calculado pelos itens) ---
                _df_calc = editor.copy()
                _df_calc["Quantidade"] = pd.to_numeric(_df_calc.get("Quantidade", 0), errors="coerce").fillna(0.0)
                _df_calc["Valor unitário"] = pd.to_numeric(_df_calc.get("Valor unitário", 0), errors="coerce").fillna(0.0)
                total_bruto_nota = float((_df_calc["Quantidade"] * _df_calc["Valor unitário"]).sum())

                cD1, cD2, cD3, cD4 = st.columns([1, 1, 1, 1])

                with cD1:
                    desconto_tipo = st.selectbox(
                        "Desconto",
                        ["R$ (valor)", "% (percentual)"],
                        index=0,
                        key="me_desconto_tipo",
                        disabled=fechado_me,
                    )

                with cD2:
                    desconto_informado = st.number_input(
                        "Valor do desconto",
                        min_value=0.0,
                        value=0.0,
                        step=1.0,
                        format="%.2f",
                        key="me_desconto_informado",
                        disabled=fechado_me,
                    )

                # calcula desconto em R$ (valor final aplicado)
                if str(desconto_tipo).startswith("%"):
                    desconto_valor = total_bruto_nota * (float(desconto_informado or 0.0) / 100.0)
                else:
                    desconto_valor = float(desconto_informado or 0.0)

                # trava desconto para não passar do total
                desconto_valor = float(desconto_valor or 0.0)
                if desconto_valor > total_bruto_nota:
                    desconto_valor = total_bruto_nota

                total_liquido_nota = float(max(total_bruto_nota - desconto_valor, 0.0))

                with cD3:
                    st.metric("Total bruto", moeda(total_bruto_nota))
                with cD4:
                    st.metric("Total com desconto", moeda(total_liquido_nota))


                salvar = st.form_submit_button("💾 Salvar nota + itens", use_container_width=True, disabled=fechado_me)

                if salvar:
                    if not str(fornecedor or "").strip():
                        st.warning("Informe o fornecedor.")
                    else:
                        df_ins = editor.copy()
                        df_ins["Item"] = df_ins["Item"].astype(str).fillna("").str.strip()
                        df_ins = df_ins[df_ins["Item"] != ""]

                        if df_ins.empty:
                            st.warning("Adicione pelo menos 1 item válido na nota.")
                        else:
                            # 1) cria a nota
                            cursor.execute(
                                "INSERT INTO compras_notas (obra_id, periodo_id, data, numero_nota, fornecedor, desconto_tipo, desconto_informado, desconto_valor, total_bruto, total_liquido) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (int(obra_id_me), int(periodo_id_me), dt_nota.isoformat(), str(numero_nota or "").strip(), str(fornecedor).strip(), str(desconto_tipo), float(desconto_informado or 0.0), float(desconto_valor or 0.0), float(total_bruto_nota or 0.0), float(total_liquido_nota or 0.0))
                            )
                            nota_id_nova = int(cursor.lastrowid)

                            # 2) salva os itens já vinculados
                            linhas_ok = 0
                            for _, r in df_ins.iterrows():
                                qtd = float(r.get("Quantidade", 0.0) or 0.0)
                                vlr = float(r.get("Valor unitário", 0.0) or 0.0)
                                und = str(r.get("Unidade", "") or "").strip()

                                cursor.execute(
                                    "INSERT INTO compras_itens (nota_id, item, unidade, quantidade, valor_unitario) VALUES (?, ?, ?, ?, ?)",
                                    (nota_id_nova, str(r["Item"]), und, qtd, vlr)
                                )
                                linhas_ok += 1

                            conn.commit()
                            st.success(f"Nota cadastrada com {linhas_ok} item(ns)!")
                            st.rerun()

        # --- LISTAGEM DETALHADA
        st.markdown("#### 📋 Materiais lançados (por item)")
        df_notas = buscar_notas_com_itens(obra_id_me, periodo_id_me)

        if df_notas is None or df_notas.empty:
            st.caption("Sem materiais lançados.")
        else:
            df_items = df_notas.copy()
            df_items["Valor Item"] = (df_items["Quantidade"].fillna(0) * df_items["Valor Unitário"].fillna(0)).round(2)
            df_items["Data"] = df_items["DataISO"].apply(iso_to_br)
            total_mat_bruto = float(df_items["Valor Item"].sum() if "Valor Item" in df_items.columns else 0.0)
            # total líquido (com desconto) = soma por NotaID (sem duplicar itens)
            _tmp_tot = df_items.copy()
            for _c in ["NotaID", "Total Nota"]:
                if _c in _tmp_tot.columns:
                    _tmp_tot[_c] = _tmp_tot[_c].replace("", pd.NA).ffill()
            total_mat = float(_tmp_tot.dropna(subset=["NotaID"]).drop_duplicates(subset=["NotaID"])["Total Nota"].fillna(0).sum()) if ("NotaID" in _tmp_tot.columns and "Total Nota" in _tmp_tot.columns) else 0.0

            # Formata para exibição
            df_show = df_items[["NotaID", "ItemID", "Data", "Nota", "Fornecedor", "Desconto", "Item", "Unidade", "Quantidade", "Valor Unitário", "Valor Item", "Total Bruto", "Total Nota"]].copy()
            df_show["Quantidade"] = df_show["Quantidade"].fillna(0).apply(lambda x: f"{float(x):.2f}".replace(".", ","))
            df_show["Valor Unitário"] = df_show["Valor Unitário"].fillna(0).apply(moeda)
            df_show["Valor Item"] = df_show["Valor Item"].fillna(0).apply(moeda)
            df_show["Desconto"] = df_show["Desconto"].fillna(0).apply(moeda)
            df_show["Total Bruto"] = df_show["Total Bruto"].fillna(0).apply(moeda)
            df_show["Total Nota"] = df_show["Total Nota"].fillna(0).apply(moeda)

            # Deixa o "Total Nota" apenas na 1ª linha de cada NotaID (as demais ficam em branco)
            _nota_ff = df_items["NotaID"].replace("", pd.NA).ffill()
            _dup = _nota_ff.duplicated()
            df_show.loc[_dup, "Total Nota"] = ""
            df_show.loc[_dup, "Total Bruto"] = ""
            df_show.loc[_dup, "Desconto"] = ""

            # Escala de cinza por NOTA (mesma NotaID = mesma cor)
            _nota_key = df_items["NotaID"].replace("", pd.NA).ffill()
            st.dataframe(
                styler_notas_grayscale(df_show, _nota_key),
                use_container_width=True,
                hide_index=True
            )
            # Totais por nota (resumo) — agora com BRUTO, DESCONTO e TOTAL (líquido)
            _tmp = df_items.copy()
            # como as colunas da nota são "blankadas" nas linhas 2..n, fazemos ffill para resumir certo
            for _c in ["NotaID", "Data", "Nota", "Fornecedor", "Desconto", "Total Bruto", "Total Nota"]:
                if _c in _tmp.columns:
                    _tmp[_c] = _tmp[_c].replace("", pd.NA).ffill()

            if "NotaID" in _tmp.columns:
                df_res = (_tmp.dropna(subset=["NotaID"])
                              .drop_duplicates(subset=["NotaID"])
                              [["NotaID", "Data", "Nota", "Fornecedor", "Total Bruto", "Desconto", "Total Nota"]]
                         )
            else:
                df_res = pd.DataFrame(columns=["NotaID", "Data", "Nota", "Fornecedor", "Total Bruto", "Desconto", "Total Nota"])

            df_res = df_res.sort_values(["Data", "NotaID"], ascending=[False, False])

            df_res_show = df_res.copy()
            for _c in ["Total Bruto", "Desconto", "Total Nota"]:
                if _c in df_res_show.columns:
                    df_res_show[_c] = df_res_show[_c].fillna(0).apply(moeda)

            st.markdown("##### 🧾 Totais por nota")
            st.dataframe(df_res_show, use_container_width=True, hide_index=True)

            c1, c2 = st.columns(2)
            with c1:
                st.metric("Total de materiais BRUTO (período)", moeda(total_mat_bruto))
            with c2:
                st.metric("Total de materiais c/ desconto (período)", moeda(total_mat))


            # --- CORREÇÕES (editar / excluir)
            st.markdown("---")
            st.markdown("#### 🛠️ Correções (Editar / Excluir)")
            st.caption("Use para corrigir lançamentos. Se o período estiver fechado, fica somente leitura.")

            tab_corr_ed, tab_corr_del = st.tabs(["✏️ Editar", "🗑️ Excluir"])

            # =========================
            # EDITAR
            # =========================
            with tab_corr_ed:
                col_e1, col_e2 = st.columns(2)

                # ---- Editar ITEM
                with col_e1:
                    st.markdown("##### ✏️ Editar item")
                    itens_validos = df_items.dropna(subset=["ItemID"])[["ItemID", "Item", "Fornecedor", "DataISO"]].copy()
                    itens_map = {}
                    for _, r in itens_validos.iterrows():
                        iid = int(r["ItemID"])
                        itens_map[f"ItemID {iid} — {iso_to_br(r['DataISO'])} — {r['Fornecedor']} — {r['Item']}"] = iid

                    if itens_map:
                        item_label_edit = st.selectbox("Selecione o item", list(itens_map.keys()), key="me_item_edit")
                        item_id_edit = int(itens_map[item_label_edit])

                        cursor.execute("SELECT item, unidade, quantidade, valor_unitario FROM compras_itens WHERE id=?", (int(item_id_edit),))
                        row_it = cursor.fetchone()

                        if row_it:
                            with st.form("form_edit_item"):
                                item_txt = st.text_input("Item", value=str(row_it[0] or ""), key="me_item_txt_edit")
                                und_txt = st.text_input("Unidade", value=str(row_it[1] or ""), key="me_item_und_edit")
                                qtd = st.number_input("Quantidade", min_value=0.0, value=float(row_it[3] or 0.0), step=0.01, key="me_item_qtd_edit")
                                vunit = st.number_input("Valor unitário", min_value=0.0, value=float(row_it[3] or 0.0), step=0.01, key="me_item_vunit_edit")
                                st.caption(f"Total do item: {moeda(qtd * vunit)}")
                                salvar_item = st.form_submit_button("💾 Salvar alterações do item", use_container_width=True, disabled=fechado_me)

                            if salvar_item:
                                cursor.execute(
                                    "UPDATE compras_itens SET item=?, unidade=?, quantidade=?, valor_unitario=? WHERE id=?",
                                    (item_txt.strip(), und_txt.strip(), float(qtd), float(vunit), int(item_id_edit))
                                )
                                conn.commit()
                                st.success("Item atualizado!")
                                st.rerun()
                        else:
                            st.warning("Item não encontrado.")
                    else:
                        st.caption("Sem itens para editar.")

                # ==============================
                # MAPA DE NOTAS (para editar/excluir)
                # ==============================
                cursor.execute("""
                    SELECT id, data, numero_nota, fornecedor
                    FROM compras_notas
                    ORDER BY data DESC, id DESC
                """)
                notas_rows = cursor.fetchall()

                def _nota_label(nota_id, data_iso, numero, fornecedor):
                    try:
                        data_br = iso_to_br(str(data_iso))
                    except Exception:
                        data_br = str(data_iso)
                    return f"ID {nota_id} — {data_br} — Nota {numero or ''} — {fornecedor or ''}"

                notas_map = {_nota_label(r[0], r[1], r[2], r[3]): r[0] for r in notas_rows}

                # ---- Editar NOTA
                with col_e2:
                    st.markdown("##### ✏️ Editar nota")
                    if notas_map:
                        nota_label_edit = st.selectbox(
                            "Selecione a nota",
                            list(notas_map.keys()),
                            key="me_nota_edit"
                        )
                        nota_id_edit = int(notas_map[nota_label_edit])

                        cursor.execute(
                            "SELECT data, numero_nota, fornecedor FROM compras_notas WHERE id=?",
                            (int(nota_id_edit),)
                        )
                        row_nt = cursor.fetchone()

                        if row_nt:
                            # data pode vir em ISO
                            try:
                                dt_ini = datetime.strptime(str(row_nt[0]), "%Y-%m-%d").date()
                            except Exception:
                                dt_ini = date.today()

                            with st.form("form_edit_nota"):
                                dt_nota = st.date_input(
                                    "Data da nota",
                                    value=dt_ini,
                                    key="me_nota_dt_edit"
                                )
                                num_nota = st.text_input(
                                    "Número da nota",
                                    value=str(row_nt[1] or ""),
                                    key="me_nota_num_edit"
                                )
                                forn = st.text_input(
                                    "Fornecedor",
                                    value=str(row_nt[2] or ""),
                                    key="me_nota_forn_edit"
                                )
                                salvar_nota = st.form_submit_button(
                                    "💾 Salvar alterações da nota",
                                    use_container_width=True,
                                    disabled=fechado_me
                                )

                            if salvar_nota:
                                cursor.execute(
                                    "UPDATE compras_notas SET data=?, numero_nota=?, fornecedor=? WHERE id=?",
                                    (dt_nota.isoformat(), num_nota.strip(), forn.strip(), int(nota_id_edit))
                                )
                                conn.commit()
                                st.success("Nota atualizada!")
                                st.rerun()
                        else:
                            st.warning("Nota não encontrada.")
                    else:
                        st.caption("Sem notas para editar.")

                # =========================
                # EXCLUIR
                # =========================
                with tab_corr_del:
                    col_del1, col_del2 = st.columns(2)

                    with col_del1:
                        st.markdown("##### 🗑️ Excluir item")
                        st.caption("Recomendado para corrigir um lançamento específico (mantém a nota).")

                        itens_validos = df_items.dropna(subset=["ItemID"])[["ItemID", "Item", "Fornecedor", "DataISO"]].copy()
                        itens_map = {}
                        for _, r in itens_validos.iterrows():
                            iid = int(r["ItemID"])
                            itens_map[f"ItemID {iid} — {iso_to_br(r['DataISO'])} — {r['Fornecedor']} — {r['Item']}"] = iid

                        if itens_map:
                            item_label_del = st.selectbox(
                                "Selecione o item",
                                list(itens_map.keys()),
                                key="me_item_del"
                            )
                            item_id_del = int(itens_map[item_label_del])
                            conf_item = st.checkbox("Confirmo excluir este item", key="me_conf_item_del")

                            if st.button(
                                "🗑️ Excluir item",
                                disabled=(fechado_me or not conf_item),
                                key="me_btn_del_item"
                            ):
                                cursor.execute("DELETE FROM compras_itens WHERE id=?", (int(item_id_del),))
                                conn.commit()
                                st.success("Item excluído!")
                                st.rerun()
                        else:
                            st.caption("Sem itens para excluir.")

                    with col_del2:
                        st.markdown("##### 🗑️ Excluir nota")
                        st.caption("Apaga a nota e TODOS os itens dela.")

                        if notas_map:
                            nota_label_del = st.selectbox(
                                "Selecione a nota",
                                list(notas_map.keys()),
                                key="me_nota_del"
                            )
                            nota_id_del = int(notas_map[nota_label_del])
                            conf_nota = st.checkbox("Confirmo excluir esta nota", key="me_conf_nota_del")

                            if st.button(
                                "🗑️ Excluir nota",
                                disabled=(fechado_me or not conf_nota),
                                key="me_btn_del_nota"
                            ):
                                cursor.execute("DELETE FROM compras_itens WHERE nota_id=?", (int(nota_id_del),))
                                cursor.execute("DELETE FROM compras_notas WHERE id=?", (int(nota_id_del),))
                                conn.commit()
                                st.success("Nota excluída!")
                                st.rerun()
                        else:
                            st.caption("Sem notas para excluir.")
    # =========================
    # ENCARGOS
    # =========================
    with tab_enc:
        st.markdown("### 🧾 Encargos extras")

        with st.expander("➕ Lançar novo ENCARGO", expanded=False):
            with st.form("form_novo_encargo", clear_on_submit=True):
                cE1, cE2 = st.columns([1, 2])
                with cE1:
                    dt_enc = st.date_input("Data", value=date.today(), key="me_dt_enc")
                with cE2:
                    desc = st.text_input("Descrição", value="", key="me_desc_enc")
                cE3, cE4 = st.columns([1, 2])
                with cE3:
                    valor = st.number_input("Valor", min_value=0.0, value=0.0, step=0.01, key="me_val_enc")
                with cE4:
                    obs = st.text_input("Obs (opcional)", value="", key="me_obs_enc")

                salvar_enc = st.form_submit_button("💾 Salvar encargo", use_container_width=True, disabled=fechado_me)
                if salvar_enc:
                    if not desc.strip():
                        st.warning("Informe a descrição.")
                    else:
                        cursor.execute(
                            "INSERT INTO encargos_extras (obra_id, periodo_id, data, descricao, valor, observacao) VALUES (?, ?, ?, ?, ?, ?)",
                            (int(obra_id_me), int(periodo_id_me), dt_enc.isoformat(), str(desc).strip(), float(valor), str(obs or "").strip())
                        )
                        conn.commit()
                        st.success("Encargo lançado!")
                        st.rerun()

        st.markdown("#### 📋 Encargos lançados")
        cursor.execute("""
            SELECT id, data, descricao, valor, observacao
            FROM encargos_extras
            WHERE obra_id=? AND periodo_id=?
            ORDER BY data ASC, id ASC
        """, (int(obra_id_me), int(periodo_id_me)))
        enc_rows = cursor.fetchall()

        if not enc_rows:
            st.caption("Sem encargos lançados.")
        else:
            df_enc = pd.DataFrame(enc_rows, columns=["ID", "DataISO", "Descrição", "Valor", "Obs"])
            df_enc["Data"] = df_enc["DataISO"].apply(iso_to_br)
            total_enc = float(df_enc["Valor"].sum() if "Valor" in df_enc.columns else 0.0)
            df_show = df_enc[["ID", "Data", "Descrição", "Valor", "Obs"]].copy()
            df_show["Valor"] = df_show["Valor"].fillna(0).apply(moeda)

            st.dataframe(df_show, use_container_width=True, hide_index=True)
            st.metric("Total de encargos (período)", moeda(total_enc))

            st.markdown("---")
            st.markdown("#### 🧹 Excluir encargo")
            enc_map = {f"ID {r[0]} — {iso_to_br(r[1])} — {r[2]} ({moeda(r[3])})": int(r[0]) for r in enc_rows}
            enc_label = st.selectbox("Selecione o encargo", list(enc_map.keys()), key="me_enc_del")
            enc_id_del = int(enc_map[enc_label])
            conf_enc = st.checkbox("Confirmo excluir este encargo", key="me_conf_enc_del")
            if st.button("🗑️ Excluir encargo", disabled=(fechado_me or not conf_enc), key="me_btn_del_enc"):
                cursor.execute("DELETE FROM encargos_extras WHERE id=?", (int(enc_id_del),))
                conn.commit()
                st.success("Encargo excluído!")
                st.rerun()




# ======================================================
# PÁGINA: CONTROLE DE NOTAS
# ======================================================
elif pagina == "Controle de Notas":
    st.subheader("🗂️ Controle de Notas")
    st.caption("Marque notas como PAGAS ou ABERTAS e acompanhe os somatórios (Obra + Período).")

    obras = get_obras()
    periodos = get_periodos()

    if not obras or not periodos:
        st.warning("Cadastre pelo menos uma obra e um período para usar este menu.")
        st.stop()

    # --- mapas ---
    obra_dict_base = {str(o[1]): int(o[0]) for o in obras}  # nome -> id
    obra_dict = {"🏗️ Todas as Obras": None, **obra_dict_base}

    periodo_dict_base = {f"Período {p[1]}": int(p[0]) for p in periodos}  # label -> id
    periodo_dict = {"📅 Todos os Períodos": None, **periodo_dict_base}

    c1, c2, c3 = st.columns([1.2, 1.0, 1.0])
    with c1:
        obra_sel = st.selectbox("Obra", list(obra_dict.keys()), key="cn_obra_sel")
    with c2:
        periodo_sel = st.selectbox("Período", list(periodo_dict.keys()), key="cn_periodo_sel")
    with c3:
        filtro = st.selectbox("Mostrar", ["Todas", "Abertas", "Pagas"], index=0, key="cn_filtro_status")

    obra_id = obra_dict.get(obra_sel)         # None => todas as obras
    periodo_id = periodo_dict.get(periodo_sel)  # None => todos os períodos

    modo_leitura_cn = True
    fechado_cn = False
    if obra_id is not None and periodo_id is not None:
        fechado_cn = is_periodo_fechado(int(obra_id), int(periodo_id))
        modo_leitura_cn = bool(fechado_cn)
    else:
        # quando filtra "Todos", trava edição para evitar alterar períodos fechados sem querer
        modo_leitura_cn = True

    if fechado_cn:
        st.warning("🔒 Este período está FECHADO para esta obra. Edições/exclusões estão bloqueadas (status PAGA/ABERTA continua liberado).oqueadas.")
    elif obra_id is None or periodo_id is None:
        st.info("Modo leitura: selecione uma OBRA e um PERÍODO específico para habilitar alterações.")

    # ======================================================
    # Helper: detecta colunas pago/pago_em (pra não quebrar em bancos antigos)
    # ======================================================
    def _has_col(table: str, col: str) -> bool:
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            cols = [r[1] for r in cursor.fetchall()]
            return col in cols
        except Exception:
            return False

    HAS_PAGO = _has_col("compras_notas", "pago")
    HAS_PAGO_EM = _has_col("compras_notas", "pago_em")

    # ======================================================
    # BUSCA GERAL (suporta: obra específica / todas; período específico / todos)
    # ======================================================
    def _buscar_notas_itens(obra_id_: int | None, periodo_id_: int | None) -> pd.DataFrame:
        if HAS_PAGO:
            pago_sql = "COALESCE(n.pago, 0) AS pago"
        else:
            pago_sql = "0 AS pago"

        if HAS_PAGO_EM:
            pagoem_sql = "COALESCE(n.pago_em, '') AS pago_em"
        else:
            pagoem_sql = "'' AS pago_em"

        where = []
        params = []

        if obra_id_ is not None:
            where.append("n.obra_id=?")
            params.append(int(obra_id_))

        if periodo_id_ is not None:
            where.append("n.periodo_id=?")
            params.append(int(periodo_id_))

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        cursor.execute(f"""
            SELECT
                n.id AS nota_id,
                n.data,
                n.numero_nota,
                n.fornecedor,
                {pago_sql},
                {pagoem_sql},
                i.id AS item_id,
                i.item,
                i.unidade,
                i.quantidade,
                i.valor_unitario,
                o.nome AS obra_nome,
                p.numero AS periodo_num
            FROM compras_notas n
            JOIN obras o ON o.id = n.obra_id
            JOIN periodos p ON p.id = n.periodo_id
            LEFT JOIN compras_itens i ON i.nota_id = n.id
            {where_sql}
            ORDER BY p.numero DESC, o.nome ASC, n.data DESC, n.id DESC, i.id ASC
        """, tuple(params))

        rows = cursor.fetchall()

        df = pd.DataFrame(rows, columns=[
            "NotaID", "DataISO", "Nota", "Fornecedor", "Pago", "PagoEm",
            "ItemID", "Item", "Unidade", "Quantidade", "Valor Unitário",
            "Obra", "PeriodoNum"
        ])

        if df.empty:
            return df

        df["Data"] = df["DataISO"].apply(iso_to_br)
        df["Pago"] = pd.to_numeric(df["Pago"], errors="coerce").fillna(0).astype(int)
        df["Status"] = df["Pago"].apply(lambda x: "PAGA" if int(x) == 1 else "ABERTA")
        df["Periodo"] = df["PeriodoNum"].apply(lambda x: f"Período {int(x)}" if str(x).strip() != "" else "Período ?")

        df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0.0)
        df["Valor Unitário"] = pd.to_numeric(df["Valor Unitário"], errors="coerce").fillna(0.0)
        df["Valor Item"] = (df["Quantidade"] * df["Valor Unitário"]).round(2)

        totais = df.groupby("NotaID")["Valor Item"].sum().round(2).to_dict()
        df["Total Nota"] = df["NotaID"].apply(lambda x: totais.get(x, 0.0))
        return df

    df_notas = _buscar_notas_itens(obra_id, periodo_id)

    st.markdown("### Resumo das Notas")

    if df_notas is None or df_notas.empty:
        st.info("Nenhuma nota encontrada para esta seleção.")
        st.stop()

    # ======================================================
    # RESUMO (1 linha por nota)
    # ======================================================
    try:
        group_cols = ["NotaID", "DataISO", "Data", "Nota", "Fornecedor", "Status", "Pago"]
        # se estiver em todos os períodos, separa por período também (pra não misturar)
        if "Periodo" in df_notas.columns and periodo_id is None:
            group_cols = ["Periodo"] + group_cols
        # se estiver em todas as obras, separa por obra também
        if "Obra" in df_notas.columns and obra_id is None:
            group_cols = ["Obra"] + group_cols

        df_res = (
            df_notas
            .groupby(group_cols, as_index=False)["Valor Item"]
            .sum()
            .rename(columns={"Valor Item": "TotalNota"})
            .sort_values(["DataISO", "NotaID"], ascending=[False, False])
        )
    except Exception:
        df_res = pd.DataFrame()

    if df_res.empty:
        st.info("Não foi possível montar o resumo das notas.")
        st.stop()

    # filtros de visualização
    if filtro == "Abertas":
        df_res_view = df_res[df_res["Pago"].astype(int) == 0].copy()
    elif filtro == "Pagas":
        df_res_view = df_res[df_res["Pago"].astype(int) == 1].copy()
    else:
        df_res_view = df_res.copy()

    # SOMATÓRIOS (sempre no total)
    total_geral = float(df_res["TotalNota"].sum())
    total_pagas = float(df_res.loc[df_res["Pago"].astype(int) == 1, "TotalNota"].sum())
    total_abertas = float(df_res.loc[df_res["Pago"].astype(int) == 0, "TotalNota"].sum())

    k1, k2, k3 = st.columns(3)
    k1.metric("💰 Total Geral", moeda(total_geral))
    k2.metric("✅ Total Pago", moeda(total_pagas))
    k3.metric("🕒 Total Aberto", moeda(total_abertas))

    st.markdown("---")

    # ======================================================
    # NOTA A NOTA
    # ======================================================
    for row in df_res_view.itertuples(index=False):
        nota_id = int(getattr(row, "NotaID"))
        status_txt = str(getattr(row, "Status", "") or "")
        pago_atual = int(getattr(row, "Pago", 0)) == 1

        obra_txt = ""
        if hasattr(row, "Obra") and getattr(row, "Obra"):
            obra_txt = f"🏗️ {getattr(row, 'Obra')} — "

        periodo_txt = ""
        if hasattr(row, "Periodo") and getattr(row, "Periodo"):
            periodo_txt = f"📅 {getattr(row, 'Periodo')} — "

        emoji = "✅" if pago_atual else "🕒"
        titulo = f"{emoji} {periodo_txt}{obra_txt}Nota {getattr(row, 'Nota')} — {getattr(row, 'Fornecedor')} — {getattr(row, 'Data')} — Total: {moeda(getattr(row, 'TotalNota'))}"

        with st.expander(titulo, expanded=False):
            col_a, col_b, col_c = st.columns([1.3, 1.0, 1.0])

            with col_a:
                if hasattr(row, "Periodo") and getattr(row, "Periodo"):
                    st.write(f"**Período:** {getattr(row, 'Periodo')}")
                if hasattr(row, "Obra") and getattr(row, "Obra"):
                    st.write(f"**Obra:** {getattr(row, 'Obra')}")
                st.write(f"**Fornecedor:** {getattr(row, 'Fornecedor')}")
                st.write(f"**Data:** {getattr(row, 'Data')}")
                st.write(f"**Número:** {getattr(row, 'Nota')}")

            with col_b:
                st.write(f"**Status atual:** {status_txt}")
                st.write(f"**Total da nota:** {moeda(getattr(row, 'TotalNota'))}")

            with col_c:
                novo_pago = st.checkbox(
                    "Marcar como paga",
                    value=pago_atual,
                    key=f"cn_pago_{nota_id}",
                    disabled=False
                )
                if novo_pago != pago_atual:
                    set_nota_pago(nota_id, novo_pago)
                    st.success("Status atualizado!")
                    st.rerun()

            # itens da nota
            df_it = df_notas[df_notas["NotaID"].astype(int) == nota_id].copy()
            cols_show = []
            for c in ["Periodo", "Obra", "Item", "Unidade", "Quantidade", "Valor Unitário", "Valor Item"]:
                if c in df_it.columns:
                    cols_show.append(c)
            if cols_show:
                df_it = df_it[cols_show].copy()

            st.dataframe(df_it, use_container_width=True, hide_index=True)

    # ======================================================
    # Totais por fornecedor (Pago x Aberto)
    # ======================================================
    with st.expander("Ver totais por fornecedor (Pago x Aberto)"):
        try:
            df_f = (
                df_res.groupby(["Fornecedor", "Pago"], as_index=False)["TotalNota"]
                .sum()
            )
            df_f["Status"] = df_f["Pago"].apply(lambda x: "PAGA" if int(x) == 1 else "ABERTA")
            df_f = df_f.pivot_table(
                index="Fornecedor",
                columns="Status",
                values="TotalNota",
                aggfunc="sum",
                fill_value=0.0
            ).reset_index()

            for c in ["ABERTA", "PAGA"]:
                if c not in df_f.columns:
                    df_f[c] = 0.0

            df_f["TOTAL"] = df_f["ABERTA"] + df_f["PAGA"]
            df_f = df_f.sort_values("TOTAL", ascending=False)

            for c in ["ABERTA", "PAGA", "TOTAL"]:
                df_f[c] = df_f[c].apply(moeda)

            st.dataframe(df_f, use_container_width=True, hide_index=True)
        except Exception:
            st.info("Não foi possível calcular o total por fornecedor.")

    # ======================================================
    # Totais por obra (Pago x Aberto) — só quando estiver em TODAS as obras
    # ======================================================
    if obra_id is None and "Obra" in df_res.columns:
        with st.expander("Ver totais por obra (Pago x Aberto)"):
            try:
                df_o = (
                    df_res.groupby(["Obra", "Pago"], as_index=False)["TotalNota"]
                    .sum()
                )
                df_o["Status"] = df_o["Pago"].apply(lambda x: "PAGA" if int(x) == 1 else "ABERTA")
                df_o = df_o.pivot_table(
                    index="Obra",
                    columns="Status",
                    values="TotalNota",
                    aggfunc="sum",
                    fill_value=0.0
                ).reset_index()

                for c in ["ABERTA", "PAGA"]:
                    if c not in df_o.columns:
                        df_o[c] = 0.0

                df_o["TOTAL"] = df_o["ABERTA"] + df_o["PAGA"]
                df_o = df_o.sort_values("TOTAL", ascending=False)

                for c in ["ABERTA", "PAGA", "TOTAL"]:
                    df_o[c] = df_o[c].apply(moeda)

                st.dataframe(df_o, use_container_width=True, hide_index=True)
            except Exception:
                st.info("Não foi possível calcular o total por obra.")

    # ======================================================
    # Totais por período (Pago x Aberto) — só quando estiver em TODOS os períodos
    # ======================================================
    if periodo_id is None and "Periodo" in df_res.columns:
        with st.expander("Ver totais por período (Pago x Aberto)"):
            try:
                df_p = (
                    df_res.groupby(["Periodo", "Pago"], as_index=False)["TotalNota"]
                    .sum()
                )
                df_p["Status"] = df_p["Pago"].apply(lambda x: "PAGA" if int(x) == 1 else "ABERTA")
                df_p = df_p.pivot_table(
                    index="Periodo",
                    columns="Status",
                    values="TotalNota",
                    aggfunc="sum",
                    fill_value=0.0
                ).reset_index()

                for c in ["ABERTA", "PAGA"]:
                    if c not in df_p.columns:
                        df_p[c] = 0.0

                df_p["TOTAL"] = df_p["ABERTA"] + df_p["PAGA"]

                # ordena por número do período (desc)
                def _num_periodo(label: str) -> int:
                    try:
                        return int(str(label).replace("Período", "").strip())
                    except Exception:
                        return -1

                df_p["__ord"] = df_p["Periodo"].apply(_num_periodo)
                df_p = df_p.sort_values("__ord", ascending=False).drop(columns=["__ord"])

                for c in ["ABERTA", "PAGA", "TOTAL"]:
                    df_p[c] = df_p[c].apply(moeda)

                st.dataframe(df_p, use_container_width=True, hide_index=True)
            except Exception:
                st.info("Não foi possível calcular o total por período.")

    # ======================================================
# PÁGINA: CONTROLE DE NOTAS
# ======================================================
elif pagina == "Controle de Notas":
    st.subheader("🗂️ Controle de Notas")
    st.caption("Marque notas como PAGAS ou ABERTAS e acompanhe os somatórios (Obra + Período).")

    obras = get_obras()
    periodos = get_periodos()

    if not obras or not periodos:
        st.warning("Cadastre pelo menos uma obra e um período para usar este menu.")
        st.stop()

    # --- mapas ---
    obra_dict_base = {str(o[1]): int(o[0]) for o in obras}  # nome -> id
    obra_dict = {"🏗️ Todas as Obras": None, **obra_dict_base}

    periodo_dict = {f"Período {p[1]}": int(p[0]) for p in periodos}  # label -> id

    c1, c2, c3 = st.columns([1.2, 1.0, 1.0])
    with c1:
        obra_sel = st.selectbox("Obra", list(obra_dict.keys()), key="cn_obra_sel")
    with c2:
        periodo_sel = st.selectbox("Período", list(periodo_dict.keys()), key="cn_periodo_sel")
    with c3:
        filtro = st.selectbox("Mostrar", ["Todas", "Abertas", "Pagas"], index=0, key="cn_filtro_status")

    obra_id = obra_dict.get(obra_sel)  # None => todas
    periodo_id = int(periodo_dict.get(periodo_sel))

    # ======================================================
    # Helper: detecta colunas pago/pago_em (pra não quebrar em bancos antigos)
    # ======================================================
    def _has_col(table: str, col: str) -> bool:
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            cols = [r[1] for r in cursor.fetchall()]
            return col in cols
        except Exception:
            return False

    HAS_PAGO = _has_col("compras_notas", "pago")
    HAS_PAGO_EM = _has_col("compras_notas", "pago_em")

    def _buscar_notas_itens_todas_obras(periodo_id_: int) -> pd.DataFrame:
        """Notas + itens para TODAS AS OBRAS de um período (inclui nome da obra).

        Retorna colunas com Total Bruto e Total Líquido (quando existir desconto/total salvo),
        além do Total Nota (mantido por compatibilidade).
        """

        # Colunas opcionais (bancos antigos podem não ter)
        HAS_DESCONTO = _has_col("compras_notas", "desconto_valor")
        HAS_TB = _has_col("compras_notas", "total_bruto")
        HAS_TL = _has_col("compras_notas", "total_liquido")

        if HAS_PAGO:
            pago_sql = "COALESCE(n.pago, 0) AS pago"
        else:
            pago_sql = "0 AS pago"

        if HAS_PAGO_EM:
            pagoem_sql = "COALESCE(n.pago_em, '') AS pago_em"
        else:
            pagoem_sql = "'' AS pago_em"

        desconto_sql = "COALESCE(n.desconto_valor, 0) AS desconto_valor" if HAS_DESCONTO else "0 AS desconto_valor"
        tb_sql = "COALESCE(n.total_bruto, 0) AS total_bruto" if HAS_TB else "0 AS total_bruto"
        tl_sql = "COALESCE(n.total_liquido, 0) AS total_liquido" if HAS_TL else "0 AS total_liquido"

        cursor.execute(f"""
            SELECT
                n.id AS nota_id,
                n.data,
                n.numero_nota,
                n.fornecedor,
                {desconto_sql},
                {tb_sql},
                {tl_sql},
                {pago_sql},
                {pagoem_sql},
                i.id AS item_id,
                i.item,
                i.unidade,
                i.quantidade,
                i.valor_unitario,
                o.nome AS obra_nome
            FROM compras_notas n
            JOIN obras o ON o.id = n.obra_id
            LEFT JOIN compras_itens i ON i.nota_id = n.id
            WHERE n.periodo_id=?
            ORDER BY o.nome ASC, n.data DESC, n.id DESC, i.id ASC
        """, (int(periodo_id_),))
        rows = cursor.fetchall()

        df = pd.DataFrame(rows, columns=[
            "NotaID", "DataISO", "Nota", "Fornecedor",
            "Desconto", "Total Bruto (salvo)", "Total Líquido (salvo)",
            "Pago", "PagoEm",
            "ItemID", "Item", "Unidade", "Quantidade", "Valor Unitário",
            "Obra"
        ])

        if df.empty:
            return df

        df["Data"] = df["DataISO"].apply(iso_to_br)
        df["Pago"] = pd.to_numeric(df["Pago"], errors="coerce").fillna(0).astype(int)
        df["Status"] = df["Pago"].apply(lambda x: "PAGA" if int(x) == 1 else "ABERTA")

        # numéricos
        df["Desconto"] = pd.to_numeric(df["Desconto"], errors="coerce").fillna(0.0)
        df["Total Bruto (salvo)"] = pd.to_numeric(df["Total Bruto (salvo)"], errors="coerce").fillna(0.0)
        df["Total Líquido (salvo)"] = pd.to_numeric(df["Total Líquido (salvo)"], errors="coerce").fillna(0.0)
        df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0.0)
        df["Valor Unitário"] = pd.to_numeric(df["Valor Unitário"], errors="coerce").fillna(0.0)

        df["Valor Item"] = (df["Quantidade"] * df["Valor Unitário"]).round(2)

        # Total bruto calculado pelos itens (mais confiável para detalhamento)
        totais = df.groupby("NotaID")["Valor Item"].sum().round(2).to_dict()
        df["Total Bruto"] = df["NotaID"].apply(lambda x: totais.get(x, 0.0))

        # Total líquido por nota: usa salvo se existir; senão (bruto - desconto)
        desc_map = df.groupby("NotaID")["Desconto"].first().fillna(0).to_dict()
        liq_salvo_map = df.groupby("NotaID")["Total Líquido (salvo)"].first().fillna(0).to_dict()

        def _total_liquido(nota_id):
            bruto = float(totais.get(nota_id, 0.0) or 0.0)
            desc = float(desc_map.get(nota_id, 0.0) or 0.0)
            liq_salvo = float(liq_salvo_map.get(nota_id, 0.0) or 0.0)
            if liq_salvo > 0:
                return round(liq_salvo, 2)
            return round(max(bruto - min(desc, bruto), 0.0), 2)

        total_liq_map = {nid: _total_liquido(nid) for nid in totais.keys()}
        df["Total Líquido"] = df["NotaID"].apply(lambda x: total_liq_map.get(x, _total_liquido(x)))

        # Mantém "Total Nota" para compatibilidade com telas/agrupamentos já existentes
        df["Total Nota"] = df["Total Líquido"]

        return df

        df["Data"] = df["DataISO"].apply(iso_to_br)
        df["Pago"] = pd.to_numeric(df["Pago"], errors="coerce").fillna(0).astype(int)
        df["Status"] = df["Pago"].apply(lambda x: "PAGA" if int(x) == 1 else "ABERTA")
        df["Valor Item"] = (pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0.0) *
                            pd.to_numeric(df["Valor Unitário"], errors="coerce").fillna(0.0)).round(2)

        totais = df.groupby("NotaID")["Valor Item"].sum().round(2).to_dict()
        df["Total Nota"] = df["NotaID"].apply(lambda x: totais.get(x, 0.0))
        return df

    # ======================================================
    # BUSCA (obra específica ou todas)
    # ======================================================
    if obra_id is None:
        df_notas = _buscar_notas_itens_todas_obras(periodo_id)
    else:
        df_notas = buscar_notas_com_itens(int(obra_id), int(periodo_id))
        if df_notas is None:
            df_notas = pd.DataFrame()
        else:
            df_notas = df_notas.copy()

        # garante coluna Obra (pra exibir bonitinho e permitir totais por obra no futuro)
        if not df_notas.empty and "Obra" not in df_notas.columns:
            df_notas["Obra"] = str(obra_sel)

        # blindagens (caso a função não tenha criado essas colunas ainda)
        if not df_notas.empty:
            if "Pago" not in df_notas.columns:
                df_notas["Pago"] = 0
            df_notas["Pago"] = pd.to_numeric(df_notas["Pago"], errors="coerce").fillna(0).astype(int)
            if "Status" not in df_notas.columns:
                df_notas["Status"] = df_notas["Pago"].apply(lambda x: "PAGA" if int(x) == 1 else "ABERTA")

    st.markdown("### Resumo das Notas")

    if df_notas.empty:
        st.info("Nenhuma nota encontrada para esta seleção.")
        st.stop()

    # ======================================================
    # RESUMO (1 linha por nota)
    # ======================================================
    try:
        group_cols = ["NotaID", "DataISO", "Data", "Nota", "Fornecedor", "Status", "Pago"]
        if "Obra" in df_notas.columns:
            group_cols = ["Obra"] + group_cols

        df_res = (
            df_notas
            .groupby(group_cols, as_index=False)["Valor Item"]
            .sum()
            .rename(columns={"Valor Item": "TotalNota"})
            .sort_values(["DataISO", "NotaID"], ascending=[False, False])
        )
    except Exception:
        df_res = pd.DataFrame()

    if df_res.empty:
        st.info("Não foi possível montar o resumo das notas.")
        st.stop()

    # filtros de visualização
    if filtro == "Abertas":
        df_res_view = df_res[df_res["Pago"].astype(int) == 0].copy()
    elif filtro == "Pagas":
        df_res_view = df_res[df_res["Pago"].astype(int) == 1].copy()
    else:
        df_res_view = df_res.copy()

    # SOMATÓRIOS (sempre no total)
    total_geral = float(df_res["TotalNota"].sum())
    total_pagas = float(df_res.loc[df_res["Pago"].astype(int) == 1, "TotalNota"].sum())
    total_abertas = float(df_res.loc[df_res["Pago"].astype(int) == 0, "TotalNota"].sum())

    k1, k2, k3 = st.columns(3)
    k1.metric("💰 Total Geral", moeda(total_geral))
    k2.metric("✅ Total Pago", moeda(total_pagas))
    k3.metric("🕒 Total Aberto", moeda(total_abertas))

    st.markdown("---")

    # ======================================================
    # NOTA A NOTA
    # ======================================================
    for row in df_res_view.itertuples(index=False):
        nota_id = int(getattr(row, "NotaID"))
        status_txt = str(getattr(row, "Status", "") or "")
        pago_atual = int(getattr(row, "Pago", 0)) == 1

        obra_txt = ""
        if hasattr(row, "Obra") and getattr(row, "Obra"):
            obra_txt = f"🏗️ {getattr(row, 'Obra')} — "

        emoji = "✅" if pago_atual else "🕒"
        titulo = f"{emoji} {obra_txt}Nota {getattr(row, 'Nota')} — {getattr(row, 'Fornecedor')} — {getattr(row, 'Data')} — Total: {moeda(getattr(row, 'TotalNota'))}"

        with st.expander(titulo, expanded=False):
            col_a, col_b, col_c = st.columns([1.3, 1.0, 1.0])

            with col_a:
                if hasattr(row, "Obra") and getattr(row, "Obra"):
                    st.write(f"**Obra:** {getattr(row, 'Obra')}")
                st.write(f"**Fornecedor:** {getattr(row, 'Fornecedor')}")
                st.write(f"**Data:** {getattr(row, 'Data')}")
                st.write(f"**Número:** {getattr(row, 'Nota')}")

            with col_b:
                st.write(f"**Status atual:** {status_txt}")
                st.write(f"**Total da nota:** {moeda(getattr(row, 'TotalNota'))}")

            with col_c:
                novo_pago = st.checkbox(
                    "Marcar como paga",
                    value=pago_atual,
                    key=f"cn_pago_{nota_id}"
                )
                if novo_pago != pago_atual:
                    set_nota_pago(nota_id, novo_pago)
                    st.success("Status atualizado!")
                    st.rerun()

            # itens da nota
            df_it = df_notas[df_notas["NotaID"].astype(int) == nota_id].copy()
            cols_show = []
            for c in ["Obra", "Item", "Unidade", "Quantidade", "Valor Unitário", "Valor Item"]:
                if c in df_it.columns:
                    cols_show.append(c)
            if cols_show:
                df_it = df_it[cols_show].copy()

            st.dataframe(df_it, use_container_width=True, hide_index=True)

    # ======================================================
    # Totais por fornecedor (Pago x Aberto)
    # ======================================================
    with st.expander("Ver totais por fornecedor (Pago x Aberto)"):
        try:
            df_f = (
                df_res.groupby(["Fornecedor", "Pago"], as_index=False)["TotalNota"]
                .sum()
            )
            df_f["Status"] = df_f["Pago"].apply(lambda x: "PAGA" if int(x) == 1 else "ABERTA")
            df_f = df_f.pivot_table(
                index="Fornecedor",
                columns="Status",
                values="TotalNota",
                aggfunc="sum",
                fill_value=0.0
            ).reset_index()

            for c in ["ABERTA", "PAGA"]:
                if c not in df_f.columns:
                    df_f[c] = 0.0

            df_f["TOTAL"] = df_f["ABERTA"] + df_f["PAGA"]
            df_f = df_f.sort_values("TOTAL", ascending=False)

            for c in ["ABERTA", "PAGA", "TOTAL"]:
                df_f[c] = df_f[c].apply(moeda)

            st.dataframe(df_f, use_container_width=True, hide_index=True)
        except Exception:
            st.info("Não foi possível calcular o total por fornecedor.")

    # ======================================================
    # Totais por obra (Pago x Aberto) — só quando estiver em TODAS as obras
    # ======================================================
    if obra_id is None and "Obra" in df_res.columns:
        with st.expander("Ver totais por obra (Pago x Aberto)"):
            try:
                df_o = (
                    df_res.groupby(["Obra", "Pago"], as_index=False)["TotalNota"]
                    .sum()
                )
                df_o["Status"] = df_o["Pago"].apply(lambda x: "PAGA" if int(x) == 1 else "ABERTA")
                df_o = df_o.pivot_table(
                    index="Obra",
                    columns="Status",
                    values="TotalNota",
                    aggfunc="sum",
                    fill_value=0.0
                ).reset_index()

                for c in ["ABERTA", "PAGA"]:
                    if c not in df_o.columns:
                        df_o[c] = 0.0

                df_o["TOTAL"] = df_o["ABERTA"] + df_o["PAGA"]
                df_o = df_o.sort_values("TOTAL", ascending=False)

                for c in ["ABERTA", "PAGA", "TOTAL"]:
                    df_o[c] = df_o[c].apply(moeda)

                st.dataframe(df_o, use_container_width=True, hide_index=True)
            except Exception:
                st.info("Não foi possível calcular o total por obra.")
            




# ======================================================
# PÁGINA: CONTROLE DE ENCARGOS EXTRAS (NAVEGAÇÃO)
# ======================================================
elif pagina == "Controle de Encargos Extras":
    st.subheader("💸 Controle de Encargos Extras")
    st.caption("Navegue e edite os encargos extras lançados (Obra + Período), igual ao Controle de Notas.")

    obras = get_obras()
    periodos = get_periodos()

    if not obras or not periodos:
        st.warning("Cadastre pelo menos uma obra e um período para usar este menu.")
        st.stop()

    # --- mapas ---
    obra_dict_base = {str(o[1]): int(o[0]) for o in obras}  # nome -> id
    obra_dict = {"🏗️ Todas as Obras": None, **obra_dict_base}

    periodo_dict_base = {f"Período {p[1]}": int(p[0]) for p in periodos}  # label -> id
    periodo_dict = {"📅 Todos os Períodos": None, **periodo_dict_base}

    c1, c2, c3 = st.columns([1.2, 1.0, 1.0])
    with c1:
        obra_sel = st.selectbox("Obra", list(obra_dict.keys()), key="cex_obra_sel")
    with c2:
        periodo_sel = st.selectbox("Período", list(periodo_dict.keys()), key="cex_periodo_sel")
    with c3:
        ordenar_por = st.selectbox("Ordenar por", ["Data (mais recente)", "Maior valor", "Menor valor"], index=0, key="cex_ord")

    obra_id = obra_dict.get(obra_sel)            # None => todas as obras
    periodo_id = periodo_dict.get(periodo_sel)  # None => todos os períodos


    modo_leitura_cex = True
    fechado_cex = False
    if obra_id is not None and periodo_id is not None:
        fechado_cex = is_periodo_fechado(int(obra_id), int(periodo_id))
        modo_leitura_cex = bool(fechado_cex)
    else:
        modo_leitura_cex = True

    if fechado_cex:
        st.warning("🔒 Este período está FECHADO para esta obra. Alterações estão bloqueadas.")
    elif obra_id is None or periodo_id is None:
        st.info("Modo leitura: selecione uma OBRA e um PERÍODO específico para habilitar alterações.")

    # ======================================================
    # BUSCA GERAL (suporta: obra específica / todas; período específico / todos)
    # ======================================================
    def _buscar_encargos(obra_id_: int | None, periodo_id_: int | None) -> pd.DataFrame:
        where = []
        params = []

        if obra_id_ is not None:
            where.append("e.obra_id=?")
            params.append(int(obra_id_))

        if periodo_id_ is not None:
            where.append("e.periodo_id=?")
            params.append(int(periodo_id_))

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        cursor.execute(f"""
            SELECT
                e.id AS enc_id,
                e.data,
                e.descricao,
                e.valor,
                e.observacao,
                COALESCE(e.pago, 0) AS pago,
                e.pago_em AS pago_em,
                o.nome AS obra_nome,
                p.numero AS periodo_num,
                e.obra_id AS obra_id,
                e.periodo_id AS periodo_id
            FROM encargos_extras e
            JOIN obras o ON o.id = e.obra_id
            JOIN periodos p ON p.id = e.periodo_id
            {where_sql}
        """, tuple(params))

        rows = cursor.fetchall()

        df = pd.DataFrame(rows, columns=[
            "EncargoID", "DataISO", "Descrição", "Valor", "Obs",
            "Pago", "PagoEm",
            "Obra", "PeriodoNum", "ObraID", "PeriodoID"
        ])

        if df.empty:
            return df

        df["DataISO"] = df["DataISO"].fillna("").astype(str)
        df["Data"] = df["DataISO"].apply(iso_to_br)
        df["ValorNum"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0.0)
        df["Valor"] = df["ValorNum"]
        df["Pago"] = df["Pago"].fillna(0).astype(int)
        df["Status"] = df["Pago"].apply(lambda x: "PAGO" if int(x) == 1 else "ABERTO")
        df["Pago Em"] = df["PagoEm"].fillna("").astype(str)
        df["Periodo"] = df["PeriodoNum"].apply(lambda x: f"Período {int(x)}" if str(x).strip() != "" else "Período ?")
        return df

    df_enc = _buscar_encargos(obra_id, periodo_id)

    if df_enc.empty:
        st.info("Sem encargos extras para este filtro.")
        st.stop()

    # ordenação
    if ordenar_por == "Maior valor":
        df_enc = df_enc.sort_values(["ValorNum", "DataISO", "EncargoID"], ascending=[False, False, False])
    elif ordenar_por == "Menor valor":
        df_enc = df_enc.sort_values(["ValorNum", "DataISO", "EncargoID"], ascending=[True, False, False])
    else:
        df_enc = df_enc.sort_values(["DataISO", "EncargoID"], ascending=[False, False])

        # SOMATÓRIOS
    total_geral = float(df_enc["ValorNum"].sum())
    total_pagos = float(df_enc.loc[df_enc["Pago"] == 1, "ValorNum"].sum())
    total_abertos = float(df_enc.loc[df_enc["Pago"] == 0, "ValorNum"].sum())

    qtd_total = int(len(df_enc))
    qtd_pagos = int((df_enc["Pago"] == 1).sum())
    qtd_abertos = int((df_enc["Pago"] == 0).sum())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 Total de Encargos", moeda(total_geral))
    k2.metric("✅ Total pagos", moeda(total_pagos), f"{qtd_pagos} lanç.")
    k3.metric("🕒 Total abertos", moeda(total_abertos), f"{qtd_abertos} lanç.")
    k4.metric("🧾 Qtde de lançamentos", f"{qtd_total}")
    st.markdown("---")

    # ======================================================
    # ENCARGO A ENCARGO (igual a Nota a Nota)
    # ======================================================
    for row in df_enc.itertuples(index=False):
        enc_id = int(getattr(row, "EncargoID"))
        obra_nome = str(getattr(row, "Obra", "") or "")
        periodo_lbl = str(getattr(row, "Periodo", "") or "")
        data_br = str(getattr(row, "Data", "") or "")
        desc_txt = str(getattr(row, "Descrição", "") or "")
        valor_num = float(getattr(row, "ValorNum", 0.0) or 0.0)
        obs_txt = str(getattr(row, "Obs", "") or "")

        obra_id_row = int(getattr(row, "ObraID"))
        periodo_id_row = int(getattr(row, "PeriodoID"))

        fechado_row = is_periodo_fechado(obra_id_row, periodo_id_row)

        pago_atual = int(getattr(row, "Pago", 0) or 0) == 1
        status_txt = "PAGO" if pago_atual else "ABERTO"

        emoji_pago = "✅" if pago_atual else "🕒"
        emoji_trava = "🔒" if fechado_row else ""
        titulo = f"{emoji_pago} {emoji_trava}📅 {periodo_lbl} — 🏗️ {obra_nome} — {data_br} — {desc_txt} — Valor: {moeda(valor_num)}"

        with st.expander(titulo, expanded=False):
            col_a, col_b, col_c = st.columns([1.2, 1.0, 1.0])

            with col_a:
                st.write(f"**Período:** {periodo_lbl}")
                st.write(f"**Obra:** {obra_nome}")
                st.write(f"**Data:** {data_br}")
                st.write(f"**Status do período:** {'FECHADO' if fechado_row else 'ABERTO'}")
                st.write(f"**Situação do encargo:** {status_txt}")

            with col_b:
                st.write("**Edição do lançamento**")
                # campos editáveis
                try:
                    dt_ini = date.fromisoformat(str(getattr(row, "DataISO") or date.today().isoformat()))
                except Exception:
                    dt_ini = date.today()

                dt_new = st.date_input("Data", value=dt_ini, key=f"cex_dt_{enc_id}", disabled=fechado_row)
                desc_new = st.text_input("Descrição", value=desc_txt, key=f"cex_desc_{enc_id}", disabled=fechado_row)
                valor_new = st.number_input("Valor (R$)", min_value=0.0, step=10.0, value=float(valor_num), key=f"cex_val_{enc_id}", disabled=fechado_row)
                obs_new = st.text_area("Observação", value=obs_txt, key=f"cex_obs_{enc_id}", disabled=fechado_row, height=90)

            with col_c:
                st.write(f"**Situação:** {status_txt}")
                novo_pago = st.checkbox(
                    "Marcar como pago",
                    value=pago_atual,
                    key=f"cex_pago_{enc_id}",
                    disabled=False
                )
                if novo_pago != pago_atual:
                    set_encargo_pago(enc_id, novo_pago)
                    st.success("Situação atualizada!")
                    st.rerun()


                if st.button("💾 Salvar alterações", key=f"cex_save_{enc_id}", disabled=(fechado_row or modo_leitura_cex)):
                    if not str(desc_new).strip():
                        st.warning("Informe a descrição.")
                    else:
                        cursor.execute(
                            "UPDATE encargos_extras SET data=?, descricao=?, valor=?, observacao=? WHERE id=?",
                            (dt_new.isoformat(), str(desc_new).strip(), float(valor_new or 0.0), str(obs_new or '').strip(), int(enc_id))
                        )
                        conn.commit()
                        st.success("Encargo atualizado!")
                        st.rerun()

            with col_c:
                st.write("**Excluir lançamento**")
                conf = st.checkbox("Confirmo excluir este encargo", key=f"cex_conf_{enc_id}", disabled=fechado_row)
                if st.button("🗑️ Excluir", key=f"cex_del_{enc_id}", disabled=(fechado_row or not conf)):
                    cursor.execute("DELETE FROM encargos_extras WHERE id=?", (int(enc_id),))
                    conn.commit()
                    st.success("Encargo excluído!")
                    st.rerun()
elif pagina == "Relatório de Obras":
    st.subheader("📊 Relatório de Obras")
    st.caption("Escolha a obra e o período. Depois use as abas para Resumo / Notas e Encargos / PDF Semanal.")

    periodos = get_periodos()
    obras = get_obras()

    if not periodos:
        st.warning("Cadastre pelo menos 1 período antes.")
        st.stop()
    if not obras:
        st.warning("Cadastre pelo menos 1 obra antes.")
        st.stop()

    periodo_map = {f"Período {p[1]} ({iso_to_br(p[2])} a {iso_to_br(p[3])})": p[0] for p in periodos}
    obra_map = {o[1]: o[0] for o in obras}

    colA, colB = st.columns(2)
    with colA:
        periodo_label_me = st.selectbox("Período (referência)", list(periodo_map.keys()), key="me_periodo")
        periodo_id_me = int(periodo_map[periodo_label_me])
    with colB:
        obra_label_me = st.selectbox("Obra", list(obra_map.keys()), key="me_obra")
        obra_id_me = int(obra_map[obra_label_me])

    # Status do período (aberto/fechado) — trava lançamentos quando fechado
    fechado_me = is_periodo_fechado(obra_id_me, periodo_id_me)
    status_me = get_periodo_status(obra_id_me, periodo_id_me)
    if fechado_me:
        st.warning("⚠️ Este período está FECHADO para esta obra. Lançamentos (folha, notas e encargos) estão bloqueados.")

    

    tab_resumo, tab_notas, tab_semanal = st.tabs(["📌 Resumo", "🧾 Notas / Encargos", "📄 PDF Semanal"])

    with tab_resumo:
        st.markdown("### 📌 Resumo do Período")

        # =========================
        # FECHAMENTO DO PERÍODO (OBRA + PERÍODO)
        # =========================
        st.markdown("#### 🔒 Fechamento do Período")

        status = get_periodo_status(obra_id_me, periodo_id_me)

        c_status, c_acao = st.columns([2, 1])
        with c_status:
            if status["fechado"]:
                st.success(f"✅ Período FECHADO (em {iso_to_br(status['fechado_em'][:10]) if status['fechado_em'] else '-'})")
            else:
                st.info("🟢 Período ABERTO")

        with c_acao:
            if status["fechado"]:
                conf = st.checkbox("Confirmo reabrir", key=f"conf_reabrir_{obra_id_me}_{periodo_id_me}")
                if st.button("🔓 Reabrir período", use_container_width=True, disabled=not conf, key=f"btn_reabrir_{obra_id_me}_{periodo_id_me}"):
                    set_periodo_fechado(obra_id_me, periodo_id_me, False)
                    st.success("Período reaberto!")
                    st.rerun()
            else:
                conf = st.checkbox("Confirmo fechar", key=f"conf_fechar_{obra_id_me}_{periodo_id_me}")
                if st.button("📌 Fechar período", use_container_width=True, disabled=not conf, key=f"btn_fechar_{obra_id_me}_{periodo_id_me}"):
                    set_periodo_fechado(obra_id_me, periodo_id_me, True)
                    st.success("Período fechado! Lançamentos bloqueados.")
                    st.rerun()

        st.caption("Ao fechar, o sistema bloqueia lançamentos (folha, notas e encargos) para esta obra neste período.")
        st.markdown("---")

        cursor.execute("""
            SELECT COALESCE(SUM(i.quantidade * i.valor_unitario), 0)
            FROM compras_notas n
            JOIN compras_itens i ON i.nota_id = n.id
            WHERE n.obra_id=? AND n.periodo_id=?
        """, (obra_id_me, periodo_id_me))
        total_mat = float(cursor.fetchone()[0] or 0)

        cursor.execute("""
            SELECT COALESCE(SUM(valor), 0)
            FROM encargos_extras
            WHERE obra_id=? AND periodo_id=?
        """, (obra_id_me, periodo_id_me))
        total_enc = float(cursor.fetchone()[0] or 0)

        # MÃO DE OBRA (folha semanal)
        cursor.execute("""
            SELECT p.nome, p.funcao, p.diaria, fs.seg, fs.ter, fs.qua, fs.qui, fs.sex, fs.sab, fs.laje_aditivo
            FROM folha_semanal fs
            JOIN profissionais p ON p.id = fs.profissional_id
            WHERE fs.periodo_id=? AND fs.obra_id=?
            ORDER BY p.nome
        """, (periodo_id_me, obra_id_me))
        folha_rows = cursor.fetchall()
        df_mao = pd.DataFrame(
            folha_rows,
            columns=["Profissional", "Função", "Diária", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Laje/Aditivo"]
        )

        total_mao = 0.0
        if not df_mao.empty:
            df_mao["Valor Hora"] = df_mao["Diária"].apply(calc_valor_hora)
            df_mao["Horas Trabalhadas"] = df_mao[["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]].sum(axis=1)
            df_mao["Total Semana"] = (df_mao["Horas Trabalhadas"] * df_mao["Valor Hora"] + df_mao["Laje/Aditivo"]).round(2)
            total_mao = float(df_mao["Total Semana"].sum())

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Materiais", moeda(total_mat))
        col2.metric("Mão de obra", moeda(total_mao))
        col3.metric("Encargos", moeda(total_enc))
        col4.metric("Total do período", moeda(total_mat + total_mao + total_enc))

        if status.get("fechado") and not df_mao.empty:
            st.markdown("#### 👷 Mão de obra do período (fechado)")
            df_show = df_mao.copy()
            # Formatação
            for c in ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Horas Trabalhadas"]:
                df_show[c] = df_show[c].fillna(0).apply(lambda x: f"{float(x):.2f}".replace(".", ","))
            for c in ["Diária", "Valor Hora", "Laje/Aditivo", "Total Semana"]:
                df_show[c] = df_show[c].fillna(0).apply(moeda)
            st.dataframe(
                df_show[["Profissional", "Função", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Horas Trabalhadas", "Laje/Aditivo", "Total Semana"]],
                use_container_width=True,
                hide_index=True
            )
        elif status.get("fechado") and df_mao.empty:
            st.info("Período fechado, mas não há lançamentos de mão de obra (folha) para esta obra neste período.")
        else:
            st.caption("Dica: ao FECHAR o período, você travará os lançamentos e poderá conferir a mão de obra final aqui no Resumo.")


        # ======================================================
        # GERAR RELATÓRIO FINANCEIRO (PDF COMPLETO)
        # ======================================================


    with tab_semanal:
        st.markdown("### 📄 Relatório para o Cliente (PDF semanal)")

        # parâmetros salvos (se já existir)
        params = get_relatorio_params(obra_id_me, periodo_id_me)

        with st.expander("⚙️ Configurar e gerar (clique para abrir)", expanded=False):
            cursor.execute("SELECT numero, dt_inicio, dt_fim FROM periodos WHERE id=?", (periodo_id_me,))
            per_info = cursor.fetchone()
            per_num = int(per_info[0]) if per_info else 0
            per_ini = per_info[1] if per_info else ""
            per_fim = per_info[2] if per_info else ""

            # ======================================================
            # 🔒 TRAVAR / FECHAR PERÍODO (OBRA + PERÍODO) — obrigatório para gerar PDF
            # ======================================================
            status_pdf = get_periodo_status(obra_id_me, periodo_id_me)
            cst1, cst2 = st.columns([2, 1])
            with cst1:
                if status_pdf.get("fechado"):
                    st.success(f"✅ Período TRANCADO (em {iso_to_br(status_pdf['fechado_em'][:10]) if status_pdf.get('fechado_em') else '-'})")
                else:
                    st.warning("🔓 Período AINDA ABERTO — trave o período para liberar a geração do PDF.")
            with cst2:
                if not status_pdf.get("fechado"):
                    conf_lock = st.checkbox("Confirmo trancar", key=f"conf_trancar_pdf_{obra_id_me}_{periodo_id_me}")
                    if st.button("🔒 Trancar período", use_container_width=True, disabled=not conf_lock, key=f"btn_trancar_pdf_{obra_id_me}_{periodo_id_me}"):
                        set_periodo_fechado(obra_id_me, periodo_id_me, True)
                        st.success("Período trancado! Agora o PDF pode ser gerado. ✅")
                        st.rerun()
                else:
                    st.caption("PDF liberado ✅")
            
            st.caption("Regra: o PDF do Relatório Financeiro só pode ser gerado após TRANCAR o período.")


            colp1, colp2, colp3 = st.columns([1, 1, 2])
            with colp1:
                semana_num = st.number_input("Número da Semana", min_value=0, step=1, value=int(params["semana"] or 0))
            with colp2:
                taxa_admin_pct = st.number_input("Taxa Administrativa (%)", min_value=0.0, max_value=100.0, step=1.0, value=float(params["taxa_admin_pct"] or 20.0))
            with colp3:
                cidade = st.text_input("Cidade", value=str(params["cidade"] or "Dores do Indaiá"))

            # Salvar padrão desta OBRA (cidade + taxa) para já preencher nos próximos relatórios
            colcfg1, colcfg2 = st.columns([1, 3])
            with colcfg1:
                if st.button("Salvar padrão desta obra", key=f"save_cfg_obra_{obra_id_me}"):
                    save_obra_config(obra_id_me, cidade, taxa_admin_pct)
                    st.success("Padrão da obra salvo! (Cidade e taxa administrativa)")
                    st.rerun()
            with colcfg2:
                st.caption("Isso define o padrão da obra. Você ainda pode alterar estes campos por período, se precisar.")

            colp4, colp5 = st.columns([2, 1])
            with colp4:
                estorno_desc = st.text_input("Descrição do Estorno (se houver)", value=str(params["estorno_desc"] or ""))
            with colp5:
                estorno_valor = st.number_input("Valor Estornado (R$)", min_value=0.0, step=50.0, value=float(params["estorno_valor"] or 0.0))

            data_emissao = st.date_input("Data de emissão do relatório", value=date.today() if not params["data_emissao"] else (_parse_date_iso(params["data_emissao"]) or date.today()))

            # --- carrega folha (mão de obra) desta obra/período
            cursor.execute("""
                SELECT p.nome, p.funcao, p.diaria, fs.seg, fs.ter, fs.qua, fs.qui, fs.sex, fs.sab, fs.laje_aditivo
                FROM folha_semanal fs
                JOIN profissionais p ON p.id = fs.profissional_id
                WHERE fs.periodo_id=? AND fs.obra_id=?
                ORDER BY p.nome
            """, (periodo_id_me, obra_id_me))
            folha_rows = cursor.fetchall()

            df_folha = pd.DataFrame(folha_rows, columns=["Profissional", "Função", "Diária", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Laje/Aditivo"])
            if not df_folha.empty:
                df_folha["Valor Hora"] = df_folha["Diária"].apply(calc_valor_hora)
                df_folha["Horas Trabalhadas"] = df_folha[["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]].sum(axis=1)
                df_folha["Total Semana"] = (df_folha["Horas Trabalhadas"] * df_folha["Valor Hora"] + df_folha["Laje/Aditivo"]).round(2)
                total_mao_obra = float(df_folha["Total Semana"].sum())
            else:
                total_mao_obra = 0.0
            # --- detalhamento de notas (já usado abaixo)
            df_notas_pdf = buscar_notas_com_itens(obra_id_me, periodo_id_me)

            # --- encargos detalhados
            cursor.execute("""
                SELECT data, descricao, valor, observacao
                FROM encargos_extras
                WHERE obra_id=? AND periodo_id=?
                ORDER BY data ASC, id ASC
            """, (obra_id_me, periodo_id_me))
            enc_rows = cursor.fetchall()
            df_enc_pdf = pd.DataFrame(enc_rows, columns=["DataISO", "Descrição", "Valor", "Obs"])
            # garante a coluna Data (BR) mesmo quando o dataframe está vazio
            if "DataISO" in df_enc_pdf.columns:
                df_enc_pdf["Data"] = df_enc_pdf["DataISO"].apply(iso_to_br)
            else:
                df_enc_pdf["Data"] = ""
            # compatibilidade com trechos que usam df_enc
            df_enc = df_enc_pdf

            # totais (materiais e encargos)
            total_materiais_pdf = float(total_mat or 0.0)
            total_encargos_pdf = float(total_enc or 0.0)

            taxa_admin_val = round(total_mao_obra * float(taxa_admin_pct or 0) / 100.0, 2)
            total_geral_periodo = round(total_materiais_pdf + total_mao_obra + taxa_admin_val + total_encargos_pdf - float(estorno_valor or 0.0), 2)

            st.markdown("---")
            st.metric("Total do Período (com taxa adm e estorno)", moeda(total_geral_periodo))

            # --- histórico (estudo financeiro) por período da obra
            cursor.execute("SELECT id, numero, dt_inicio, dt_fim FROM periodos ORDER BY numero ASC")
            all_periodos = cursor.fetchall()

            hist_rows = []
            acumulado = 0.0
            for pid, pnum, pini, pfim in all_periodos:
                # pega params daquele período (se existir)
                ppar = get_relatorio_params(obra_id_me, pid)
                taxa_p = float(ppar["taxa_admin_pct"] or 20.0)
                est_p = float(ppar["estorno_valor"] or 0.0)

                # materiais
                cursor.execute("""
                    SELECT COALESCE(SUM(i.quantidade * i.valor_unitario), 0)
                    FROM compras_notas n
                    JOIN compras_itens i ON i.nota_id = n.id
                    WHERE n.obra_id=? AND n.periodo_id=?
                """, (obra_id_me, pid))
                mat_p = float(cursor.fetchone()[0] or 0)

                # encargos
                cursor.execute("""
                    SELECT COALESCE(SUM(valor), 0)
                    FROM encargos_extras
                    WHERE obra_id=? AND periodo_id=?
                """, (obra_id_me, pid))
                enc_p = float(cursor.fetchone()[0] or 0)

                # mão de obra
                cursor.execute("""
                    SELECT p.diaria, fs.seg, fs.ter, fs.qua, fs.qui, fs.sex, fs.sab, fs.laje_aditivo
                    FROM folha_semanal fs
                    JOIN profissionais p ON p.id = fs.profissional_id
                    WHERE fs.periodo_id=? AND fs.obra_id=?
                """, (pid, obra_id_me))
                mo_rows = cursor.fetchall()
                mo_p = 0.0
                for diaria, seg, ter, qua, qui, sex, sab, laje in mo_rows:
                    vh = calc_valor_hora(diaria or 0.0)
                    horas = float(seg or 0) + float(ter or 0) + float(qua or 0) + float(qui or 0) + float(sex or 0) + float(sab or 0)
                    mo_p += (horas * vh) + float(laje or 0)

                adm_p = mo_p * taxa_p / 100.0
                total_p = (mat_p + mo_p + adm_p + enc_p - est_p)

                acumulado += total_p

                # mostra até o período atual selecionado
                if int(pnum) <= int(per_num):
                    hist_rows.append({
                        "Período": f"{int(pnum)}",
                        "Início": iso_to_br(pini),
                        "Fim": iso_to_br(pfim),
                        "Valor do Período": round(total_p, 2),
                        "Total Acumulado": round(acumulado, 2)
                    })

            df_hist = pd.DataFrame(hist_rows)

            if st.button("Gerar PDF do Relatório Financeiro", disabled=not status_pdf.get("fechado"), key=f"btn_relatorio_pdf_{obra_id_me}_{periodo_id_me}"):
                # salva parâmetros para este período
                save_relatorio_params(
                    obra_id=obra_id_me,
                    periodo_id=periodo_id_me,
                    semana=int(semana_num) if semana_num else None,
                    taxa_admin_pct=float(taxa_admin_pct),
                    estorno_valor=float(estorno_valor),
                    estorno_desc=str(estorno_desc or ""),
                    cidade=str(cidade or ""),
                    data_emissao_iso=data_emissao.isoformat()
                )

                # salva em uma pasta fixa "pdfs" (evita erro de caminho / caracteres)
                base_dir = os.path.dirname(os.path.abspath(__file__))
                out_dir = os.path.join(base_dir, "pdfs")
                os.makedirs(out_dir, exist_ok=True)

                base = f"Relatorio_Financeiro_{obra_label_me}_Periodo_{per_num}"
                nome_pdf = os.path.join(out_dir, safe_filename(base) + ".pdf")

                # escolhe logo disponível
                logo_use = (
                    "logo.png"
                    if os.path.exists("logo.png")
                    else ("logo.jpg" if os.path.exists("logo.jpg") else "logo.png")
                )

                try:
                    gerar_relatorio_financeiro_pdf(
                        filename=nome_pdf,
                        obra_nome=str(obra_label_me),
                        periodo_num=int(per_num),
                        dt_inicio_iso=per_ini,
                        dt_fim_iso=per_fim,
                        semana=int(semana_num) if semana_num else 0,
                        cidade=str(cidade or ""),
                        data_emissao_iso=data_emissao.isoformat(),
                        taxa_admin_pct=float(taxa_admin_pct),
                        estorno_valor=float(estorno_valor),
                        estorno_desc=str(estorno_desc or ""),
                        total_materiais=float(total_materiais_pdf),
                        total_mao_obra=float(total_mao_obra),
                        total_encargos=float(total_encargos_pdf),
                        df_notas_detalhe=df_notas_pdf.copy() if isinstance(df_notas_pdf, pd.DataFrame) else pd.DataFrame(),
                        df_folha_calc=df_folha.copy() if isinstance(df_folha, pd.DataFrame) else pd.DataFrame(),
                        df_encargos=df_enc_pdf.copy() if isinstance(df_enc_pdf, pd.DataFrame) else pd.DataFrame(),
                        df_historico=df_hist.copy() if isinstance(df_hist, pd.DataFrame) else pd.DataFrame(),
                        logo_path=logo_use,
                    )

                    st.success("Relatório PDF gerado com sucesso!")

                    with open(nome_pdf, "rb") as f:
                        st.download_button(
                            "Baixar Relatório PDF",
                            data=f.read(),
                            file_name=os.path.basename(nome_pdf),
                            mime="application/pdf"
                        )

                except Exception as e:
                    st.error(f"Erro ao gerar relatório: {e}")





# ======================================================
# PÁGINA: RELATÓRIO DE MÃO DE OBRA
# ======================================================
elif pagina == "Relatório de Mão de Obra":
    st.subheader("🧑‍🔧 Relatório de Mão de Obra")
    st.caption("Somatório por OBRA dentro de cada período (com base na Folha Semanal).")
    st.markdown("---")

    periodos = get_periodos()
    if not periodos:
        st.warning("Cadastre pelo menos 1 período antes.")
        st.stop()

    # 🔹 Seleção ÚNICA de período
    periodo_map = {
        f"Período {p[1]} ({iso_to_br(p[2])} a {iso_to_br(p[3])})": int(p[0])
        for p in periodos
    }
    periodo_label = st.selectbox(
        "Período",
        list(periodo_map.keys()),
        key="mo_periodo"
    )
    periodo_id_sel = int(periodo_map[periodo_label])

    # 🔹 Dados brutos: período + obra + profissional + horas + diária
    sql = """
        SELECT
            fs.id       AS folha_id,

            fs.periodo_id,
            p.numero    AS periodo_num,
            p.dt_inicio AS periodo_ini,
            p.dt_fim    AS periodo_fim,

            fs.obra_id,
            o.nome      AS obra_nome,

            fs.profissional_id,
            pr.nome     AS profissional_nome,
            pr.diaria   AS diaria,

            fs.seg, fs.ter, fs.qua, fs.qui, fs.sex, fs.sab,
            COALESCE(fs.laje_aditivo, 0) AS laje_aditivo
        FROM folha_semanal fs
        JOIN periodos p       ON p.id = fs.periodo_id
        JOIN obras o          ON o.id = fs.obra_id
        JOIN profissionais pr ON pr.id = fs.profissional_id
        WHERE fs.periodo_id = ?
    """
    df_raw = pd.read_sql(sql, conn, params=(periodo_id_sel,))

    if df_raw.empty:
        st.info("Não há lançamentos de folha para este período.")
        st.stop()

    # ======================================================
    # CÁLCULOS (sem colunas extras na tela)
    # - base = horas * valor_hora
    # - total_periodo = base + laje_aditivo (já embutido)
    # ======================================================
    df = df_raw.copy()
    df["valor_hora"] = (df["diaria"].astype(float) * 6.0) / 44.0
    df["horas"] = (
        df[["seg", "ter", "qua", "qui", "sex", "sab"]]
        .fillna(0)
        .astype(float)
        .sum(axis=1)
    )

    df["base_calc"] = (df["horas"] * df["valor_hora"]).round(2)
    df["laje_aditivo"] = df["laje_aditivo"].fillna(0).astype(float).round(2)

    # ✅ Total que vamos usar em TUDO nessa página
    # (já considera laje/aditivo, mas não exibe como coluna)
    df["total_periodo"] = (df["base_calc"] + df["laje_aditivo"]).round(2)

    # ======================================================
    # RESUMO
    # ======================================================
    st.markdown("### 📌 Resumo do Período")

    # Total por OBRA + PROFISSIONAL
    df_ob_prof = (
        df.groupby(["obra_id", "obra_nome", "profissional_id", "profissional_nome"], as_index=False)
          .agg(total_periodo=("total_periodo", "sum"))
          .sort_values(["obra_nome", "total_periodo"], ascending=[True, False])
    )

    # Total por OBRA
    df_tot_obra = (
        df.groupby(["obra_id", "obra_nome"], as_index=False)[["total_periodo"]]
          .sum()
          .sort_values("total_periodo", ascending=False)
    )

    # ======================================================
    # ✅ TABELA: TOTAIS POR OBRA
    # ======================================================
    st.markdown("#### 🏗️ Totais por Obra")
    df_show_obras = df_tot_obra.copy()
    df_show_obras["Mão de Obra"] = df_show_obras["total_periodo"].apply(moeda)

    st.dataframe(
        df_show_obras[["obra_nome", "Mão de Obra"]].rename(columns={"obra_nome": "Obra"}),
        use_container_width=True,
        hide_index=True,
    )

    # ======================================================
    # RENDERIZAÇÃO (detalhamento por obra)
    # ======================================================
    def render_periodo(df_p: pd.DataFrame, pid_for_keys: int):
        if df_p.empty:
            return

        periodo_num = int(df_p["periodo_num"].iloc[0])
        periodo_ini = df_p["periodo_ini"].iloc[0]
        periodo_fim = df_p["periodo_fim"].iloc[0]

        titulo = f"Período {periodo_num} ({iso_to_br(periodo_ini)} a {iso_to_br(periodo_fim)})"
        st.markdown(f"## {titulo}")

        total_periodo = float(df_p["total_periodo"].sum())

        c1, c2, c3 = st.columns(3)
        with c2:
            st.metric("TOTAL DO PERÍODO", moeda(total_periodo))

        st.markdown("---")

        # ✅ PDF geral ainda disponível, mas sem colunas extras (desc = 0)
        col_pdf1, col_pdf2 = st.columns([1, 3])
        with col_pdf1:
            if st.button("📄 Gerar PDF Geral do Período", key=f"btn_pdf_geral_{pid_for_keys}"):
                # monta df no formato que o PDF espera
                df_pdf = df_p.groupby(["obra_nome", "profissional_nome"], as_index=False).agg(
                    base=("total_periodo", "sum"),
                )
                df_pdf["desconto_aditivo"] = 0.0
                df_pdf["total_final"] = df_pdf["base"].round(2)

                pdf_buf = gerar_pdf_geral_mao_obra_periodo(
                    df_periodo=df_pdf.rename(columns={
                        "obra_nome": "obra_nome",
                        "profissional_nome": "profissional_nome",
                    }),
                    periodo_num=periodo_num,
                    periodo_ini=periodo_ini,
                    periodo_fim=periodo_fim,
                )
                st.download_button(
                    "⬇️ Baixar PDF",
                    data=pdf_buf.getvalue(),
                    file_name=f"Relatorio_Geral_Mao_Obra_Periodo_{periodo_num}.pdf",
                    mime="application/pdf",
                    key=f"dl_pdf_geral_{pid_for_keys}",
                )

        with col_pdf2:
            st.caption("Gera o PDF geral do período com Obras + Profissionais + Totais (sem colunas extras).")

        # Totais por obra (para ordenar e mostrar)
        obras_tot = (
            df_p.groupby(["obra_id", "obra_nome"], as_index=False)[["total_periodo"]]
                .sum()
                .sort_values("total_periodo", ascending=False)
        )

        for _, row in obras_tot.iterrows():
            obra_id = int(row["obra_id"])
            obra_nome = row["obra_nome"]

            st.markdown("---")
            st.markdown(f"### 🏗️ {obra_nome}")

            df_o = df_p[df_p["obra_id"] == obra_id].copy()

            # 1 linha por profissional/obra/período ✅ (SÓ o total)
            profs = (
                df_o.groupby(["profissional_id", "profissional_nome"], as_index=False)
                    .agg(
                        folha_id=("folha_id", "min"),
                        total_periodo=("total_periodo", "sum"),
                    )
                    .sort_values("total_periodo", ascending=False)
            )
            profs = profs.rename(columns={"profissional_nome": "Profissional"})

            # ✅ TABELA SEM AS 3 COLUNAS
            st.dataframe(
                profs[["folha_id", "profissional_id", "Profissional", "total_periodo"]].rename(columns={
                    "folha_id": "ID",
                    "profissional_id": "PROF_ID",
                    "total_periodo": "Total no Período",
                }),
                use_container_width=True,
                hide_index=True,
            )

            st.caption("Obs.: aqui o total já inclui o Laje/Aditivo (sem mostrar separado).")

            # ======================================================
            # RECIBOS (por obra + período)
            # ======================================================
            with st.expander("🧾 Recibos dos profissionais (Obra + Período)", expanded=False):
                st.caption("Gera 1 página por profissional (recibo simples com assinatura).")

                # a função de recibo usa a coluna 'base'
                df_rec = profs[["Profissional", "total_periodo"]].copy()
                df_rec = df_rec.rename(columns={"total_periodo": "base"})

                if st.button("🧾 Gerar Recibos (Obra)", key=f"btn_recibos_{pid_for_keys}_{obra_id}"):
                    try:
                        pdf_buf = gerar_pdf_recibos_mao_obra_por_obra_periodo(
                            df_obra=df_rec,
                            obra_nome=str(obra_nome),
                            periodo_num=int(periodo_num),
                            periodo_ini=str(periodo_ini),
                            periodo_fim=str(periodo_fim),
                        )

                        if pdf_buf is None:
                            st.warning("Sem dados para gerar recibos nesta obra.")
                        else:
                            nome_pdf = f"Recibos_Mao_de_Obra_{safe_filename(obra_nome)}_Periodo_{periodo_num}.pdf"
                            st.download_button(
                                "⬇️ Baixar PDF de Recibos",
                                data=pdf_buf.getvalue(),
                                file_name=nome_pdf,
                                mime="application/pdf",
                                key=f"dl_recibos_{pid_for_keys}_{obra_id}",
                            )
                    except Exception as e:
                        st.error(f"Erro ao gerar recibos: {e}")

            st.metric("TOTAL DA OBRA (Mão de Obra)", moeda(float(profs["total_periodo"].sum())))

    # ✅ chama a renderização
    render_periodo(df, periodo_id_sel)

# ======================================================
# PÁGINA: Folha de Pagamento
# ======================================================
elif pagina == "Folha de Pagamento":
    st.subheader("📄 Folha de Pagamento")
    st.caption("Planilha consolidada por período (com aviso se houver obra/período ainda em aberto).")
    st.markdown("---")

    # =========================
    # FILTRO DE PERÍODO
    # =========================
    periodos = get_periodos()
    if not periodos:
        st.warning("Cadastre pelo menos 1 período.")
        st.stop()

    # labels (mais novo primeiro)
    periodo_labels = [
        f"Período {p[1]} ({iso_to_br(p[2])} a {iso_to_br(p[3])})"
        for p in periodos
    ]
    periodo_id_by_label = {lbl: int(periodos[i][0]) for i, lbl in enumerate(periodo_labels)}

    # 🔥 selectbox (apenas 1 período)
    sel_label = st.selectbox(
        "Filtrar período",
        options=periodo_labels,
        index=0,  # último período por padrão
        key="rfmo_periodo_unico"
    )

    sel_periodo_ids = [periodo_id_by_label[sel_label]]

    # =========================
    # BUSCA CONSOLIDADA (SQL)
    # =========================
    # OBS IMPORTANTE:
    # - O valor "fechado" do pedreiro no período é o TOTAL DA SEMANA, que JÁ inclui o Laje/Aditivo lançado na Folha Semanal (Obra).
    # - Portanto, nesta página NÃO exibimos "Desc/Aditivo" separado (ele fica apenas embutido no total).
    ph = ",".join(["?"] * len(sel_periodo_ids))
    cursor.execute(f"""
        SELECT
            fs.periodo_id,
            pe.numero AS periodo_num,
            pe.dt_inicio AS periodo_ini,
            pe.dt_fim AS periodo_fim,

            fs.obra_id,
            o.nome AS obra_nome,

            fs.profissional_id,
            p.nome AS profissional_nome,
            COALESCE(p.diaria, 0) AS diaria,

            SUM(
                COALESCE(fs.seg,0) + COALESCE(fs.ter,0) + COALESCE(fs.qua,0) +
                COALESCE(fs.qui,0) + COALESCE(fs.sex,0) + COALESCE(fs.sab,0)
            ) AS horas_trab,

            -- fica embutido no TOTAL, não exibimos separado
            SUM(COALESCE(fs.laje_aditivo,0)) AS laje_aditivo,

            COALESCE(ops.fechado, 0) AS fechado

        FROM folha_semanal fs
        JOIN periodos pe ON pe.id = fs.periodo_id
        JOIN obras o ON o.id = fs.obra_id
        JOIN profissionais p ON p.id = fs.profissional_id
        LEFT JOIN obra_periodo_status ops
            ON ops.obra_id = fs.obra_id
           AND ops.periodo_id = fs.periodo_id

        WHERE fs.periodo_id IN ({ph})
        GROUP BY
            fs.periodo_id, pe.numero, pe.dt_inicio, pe.dt_fim,
            fs.obra_id, o.nome,
            fs.profissional_id, p.nome, p.diaria,
            ops.fechado
        ORDER BY pe.numero DESC, o.nome ASC, p.nome ASC
    """, sel_periodo_ids)

    rows = cursor.fetchall()
    cols = [
        "PeriodoID", "Período", "InícioISO", "FimISO",
        "ObraID", "Obra",
        "ProfissionalID", "Profissional", "Diária",
        "Horas Trabalhadas", "Laje/Aditivo (embutido)", "Fechado"
    ]
    df = pd.DataFrame(rows, columns=cols)

    if df.empty:
        st.info("Não há lançamentos de mão de obra (folha semanal) nos períodos selecionados.")
        st.stop()

    # =========================
    # CÁLCULOS
    # =========================
    df["Início"] = df["InícioISO"].apply(iso_to_br)
    df["Fim"] = df["FimISO"].apply(iso_to_br)

    df["Horas Trabalhadas"] = pd.to_numeric(df["Horas Trabalhadas"], errors="coerce").fillna(0.0)
    df["Diária"] = pd.to_numeric(df["Diária"], errors="coerce").fillna(0.0)
    df["Laje/Aditivo (embutido)"] = pd.to_numeric(df["Laje/Aditivo (embutido)"], errors="coerce").fillna(0.0)

    # Valor hora baseado na sua regra (6 diárias / 44h)
    df["Valor Hora"] = df["Diária"].apply(calc_valor_hora)

    # Mão de Obra (somente horas x valor hora)
    df["Mão de Obra (R$)"] = (df["Horas Trabalhadas"] * df["Valor Hora"]).round(2)

    # ✅ Valor fechado do período = TOTAL DA SEMANA (horas x valor hora + laje/aditivo)
    df["Valor Fechado (R$)"] = (df["Mão de Obra (R$)"] + df["Laje/Aditivo (embutido)"]).round(2)

    df["Status Período (Obra)"] = df["Fechado"].apply(lambda x: "FECHADO" if int(x) == 1 else "ABERTO")

    # =========================
    # AVISO: EXISTE OBRA/PERÍODO EM ABERTO?
    # =========================
    abertos = df[df["Fechado"].fillna(0).astype(int) == 0].copy()
    if not abertos.empty:
        lista_abertos = (
            abertos[["Período", "Obra"]]
            .drop_duplicates()
            .sort_values(["Período", "Obra"], ascending=[False, True])
        )
        st.warning("⚠️ Atenção: existem obras com período ainda **ABERTO** dentro do filtro selecionado.")
        st.dataframe(lista_abertos, use_container_width=True, hide_index=True)

        continuar = st.checkbox("Desejo continuar mesmo assim", value=False, key="rfmo_continuar_abertos")
        if not continuar:
            st.info("Feche os períodos acima (na obra correspondente) ou marque a opção para continuar.")
            st.stop()

    # =========================
    # PLANILHA (CONSOLIDADO)
    # =========================
    st.markdown("### 📌 Planilha — Profissional x Período (Valor Fechado)")

    # ✅ Agora consolida por (PeríodoID, ObraID, ProfissionalID)
    # (mantém IDs para salvar o ACERTO no banco)
    df_show = (
        df.groupby(
            ["PeriodoID", "ObraID", "ProfissionalID", "Obra", "Profissional"],
            as_index=False
        )
        .agg(
            valor_fechado=("Valor Fechado (R$)", "sum"),
        )
        .sort_values(["Profissional", "Obra"], ascending=[True, True])
    )

    # =========================
    # ACERTOS (carrega do banco)
    # =========================
    periodo_ids_sel = sorted(df_show["PeriodoID"].dropna().astype(int).unique().tolist())
    if len(periodo_ids_sel) == 0:
        st.info("Sem dados para exibir.")
        st.stop()

    ph = ",".join(["?"] * len(periodo_ids_sel))
    acertos_df = pd.read_sql(
        f"""
        SELECT periodo_id, obra_id, profissional_id, valor_acerto
        FROM acertos_mao_obra
        WHERE periodo_id IN ({ph})
        """,
        conn,
        params=periodo_ids_sel
    )

    df_show["valor_fechado"] = pd.to_numeric(df_show["valor_fechado"], errors="coerce").fillna(0.0)

    if acertos_df is None or acertos_df.empty:
        df_show["Acerto"] = 0.0
    else:
        df_show = df_show.merge(
            acertos_df,
            left_on=["PeriodoID", "ObraID", "ProfissionalID"],
            right_on=["periodo_id", "obra_id", "profissional_id"],
            how="left"
        )
        df_show["Acerto"] = pd.to_numeric(df_show["valor_acerto"], errors="coerce").fillna(0.0)
        df_show = df_show.drop(columns=["periodo_id", "obra_id", "profissional_id", "valor_acerto"], errors="ignore")

    df_show["Fechamento"] = (df_show["valor_fechado"] + df_show["Acerto"]).round(2)

    # =========================
    # VISUAL (profissional “mesclado” + TOTAL por profissional)
    # =========================
    df_view = df_show.copy().sort_values(["Profissional", "Obra"], ascending=[True, True])

    linhas = []
    for prof, grupo in df_view.groupby("Profissional", sort=True):
        grupo = grupo.sort_values("Obra", ascending=True).copy()

        primeira = True
        for _, r in grupo.iterrows():
            vf = float(r.get("valor_fechado") or 0.0)
            ac = float(r.get("Acerto") or 0.0)
            fech = vf + ac

            linhas.append({
                "__key": (
                    str(int(r["PeriodoID"])) + "|" +
                    str(int(r["ObraID"])) + "|" +
                    str(int(r["ProfissionalID"]))
                ),
                "Profissional": prof if primeira else "",
                "Obra": str(r.get("Obra", "")),
                "Valor Fechado": round(vf, 2),
                "Acerto": round(ac, 2),
                "Fechamento": round(fech, 2),
            })
            primeira = False

        # ✅ TOTAL do profissional
        total_vf = float(pd.to_numeric(grupo["valor_fechado"], errors="coerce").fillna(0.0).sum())
        total_ac = float(pd.to_numeric(grupo["Acerto"], errors="coerce").fillna(0.0).sum())
        total_fech = round(total_vf + total_ac, 2)

        linhas.append({
            "__key": f"TOTAL|{prof}",
            "Profissional": "",
            "Obra": "TOTAL",
            "Valor Fechado": round(total_vf, 2),
            "Acerto": round(total_ac, 2),
            "Fechamento": total_fech,
        })

    df_editor = pd.DataFrame(linhas).set_index("__key")



    # ======================================================
    # ✅ VISUAL PRINCIPAL (mantém só 1 planilha na tela)
    # - Mostra a tabela bonita (amarelo no TOTAL)
    # - E deixa a edição de ACERTO dentro de um expander
    # ======================================================

    # Totais (filtro atual)
    st.markdown("### ✅ Totais (filtro atual)")
    t1, t2, t3 = st.columns(3)
    with t1:
        st.metric("Valor Fechado (total)", moeda(float(df_show["valor_fechado"].sum())))
    with t2:
        st.metric("Acerto (total)", moeda(float(df_show["Acerto"].sum())))
    with t3:
        st.metric("Fechamento (total)", moeda(float(df_show["Fechamento"].sum())))

    # ✅ Estilo: destaca linhas TOTAL
    def _style_total_row(row):
        if str(row.get("Obra", "")).strip().upper() == "TOTAL":
            return ["background-color: #fff3cd; font-weight: bold; color: #000000"] * len(row)
        return [""] * len(row)

    # Tabela bonita (somente visual)
    st.dataframe(
        df_editor.reset_index(drop=True).style.apply(_style_total_row, axis=1),
        use_container_width=True,
        hide_index=True
    )

    

# ======================================================
# PDF DA PLANILHA (VALOR FECHADO / ACERTO / FECHAMENTO)
# ======================================================
colp1, colp2 = st.columns([1, 3])

with colp1:
    if st.button("📄 Gerar PDF desta Planilha", key="btn_pdf_planilha_valor_fechado"):

        # ======================================================
        # 🔒 BLOQUEIO: se existir alguma OBRA com PERÍODO ABERTO
        # ======================================================
        obras_abertas = []

        try:
            # Preferência: usa df_show (tem PeriodoID/ObraID/Obra)
            df_verifica = df_show[["PeriodoID", "ObraID", "Obra"]].dropna().drop_duplicates()

            for _, row in df_verifica.iterrows():
                periodo_id = int(row["PeriodoID"])
                obra_id = int(row["ObraID"])
                obra_nome = str(row["Obra"])

                if not is_periodo_fechado(obra_id, periodo_id):
                    obras_abertas.append(obra_nome)

        except Exception:
            # Fallback: tenta descobrir via __key do df_editor (periodo|obra|prof)
            try:
                if "__key" in df_editor.columns:
                    chaves = df_editor["__key"].dropna().astype(str).unique().tolist()
                    chaves = [c for c in chaves if not c.startswith("TOTAL|")]

                    pares = set()
                    for k in chaves:
                        p_id, o_id, _ = k.split("|")
                        pares.add((int(o_id), int(p_id)))

                    for (obra_id, periodo_id) in sorted(pares):
                        # nome pode não existir no fallback, então mostramos só o ID
                        if not is_periodo_fechado(obra_id, periodo_id):
                            obras_abertas.append(f"Obra ID {obra_id} (Período ID {periodo_id})")
            except Exception:
                pass

        if obras_abertas:
            st.error("⚠️ EXISTEM OBRAS COM PERÍODO AINDA ABERTO.")
            st.warning("Feche o período dessas obras antes de gerar o PDF:")

            for nome in sorted(set(obras_abertas)):
                st.markdown(f"- ❌ **{nome}**")

            st.stop()

        # ======================================================
        # ✅ Se estiver tudo FECHADO, gera PDF
        # ======================================================
        df_pdf_plan = df_editor.reset_index(drop=True).copy()

        # garante numérico
        for c in ["Valor Fechado", "Acerto", "Fechamento"]:
            df_pdf_plan[c] = pd.to_numeric(df_pdf_plan.get(c, 0), errors="coerce").fillna(0.0)

        # subtítulo com períodos selecionados (se existir no df original)
        try:
            periodos_txt = ", ".join(sorted(df["Período"].dropna().astype(str).unique().tolist()))
        except Exception:
            periodos_txt = ""

        pdf_buf = gerar_pdf_planilha_valor_fechado(
            df_planilha=df_pdf_plan[["Profissional", "Obra", "Valor Fechado", "Acerto", "Fechamento"]],
            titulo="PLANILHA — PROFISSIONAL x PERÍODO (VALOR FECHADO)",
            subtitulo=f"Períodos no filtro: {periodos_txt}" if periodos_txt else "",
        )

        st.session_state["pdf_planilha_valor_fechado"] = pdf_buf.getvalue()

with colp2:
    if st.session_state.get("pdf_planilha_valor_fechado"):
        st.download_button(
            "⬇️ Baixar PDF da Planilha",
            data=st.session_state["pdf_planilha_valor_fechado"],
            file_name="Planilha_Profissional_x_Periodo_Valor_Fechado.pdf",
            mime="application/pdf",
            key="dl_pdf_planilha_valor_fechado",
        )

st.caption("Obs.: Fechamento = Valor Fechado + Acerto (Acerto editável e salvo no banco).")
