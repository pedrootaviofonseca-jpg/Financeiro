import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import calendar
from datetime import date
from io import BytesIO
import os
import base64
from typing import Optional, Tuple, List

# PDF (reportlab)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# ==========================================================
# FINANCEIRO PROFISSIONAL — arquivo único (Streamlit)
# Baseado no seu arquivo original (reorganizado e limpo).
# ==========================================================

# =========================
# CONFIGURAÇÃO STREAMLIT
# =========================
st.set_page_config(page_title="Financeiro — Sistema Interno", layout="wide")

# =========================
# UI (TEMA AMARELO ESCURO + LOGO NA LATERAL)
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _find_logo_path() -> Optional[str]:
    """Procura um arquivo de logo na mesma pasta do .py."""
    for nm in ("logo_app.png", "logo_app.jpg", "logo_app.jpeg", "logo.png", "logo.jpg", "logo.jpeg"):
        p = os.path.join(BASE_DIR, nm)
        if os.path.exists(p):
            return p
    return None

def _img_to_data_uri(path_img: str) -> str:
    ext = os.path.splitext(path_img)[1].lower().replace(".", "")
    if ext == "jpg":
        ext = "jpeg"
    with open(path_img, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/{ext};base64,{b64}"

def apply_light_theme():
    """Aplica CSS (AMARELO ESCURO + sidebar colorida)."""
    st.markdown(
        """
        <style>

        /* ====== FUNDO AMARELO ESCURO ====== */
        .stApp{
          background: linear-gradient(180deg, #D4A017 0%, #B8860B 60%, #8B6508 100%);
          color: #1F2937;
        }

        /* ====== SIDEBAR COLORIDA ====== */
        section[data-testid="stSidebar"]{
          background: linear-gradient(180deg, #0B4F8A 0%, #1E73BE 55%, #00A86B 120%);
        }
        section[data-testid="stSidebar"] *{
          color: #ffffff !important;
        }

        /* ====== Área principal: força texto escuro ====== */
        div[data-testid="stAppViewContainer"]{
          color: #1F2937 !important;
        }
        div[data-testid="stAppViewContainer"] label{
          color: #1F2937 !important;
          font-weight: 600;
        }

        /* Inputs/Selects com fundo claro */
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div{
          background: rgba(255,255,255,0.92) !important;
          border-color: rgba(0,0,0,0.15) !important;
        }
        div[data-testid="stAppViewContainer"] div[data-baseweb="select"] *{
          color: #111827 !important;
        }
        div[data-testid="stAppViewContainer"] div[data-baseweb="input"] input{
          color: #111827 !important;
        }

        /* Botões */
        .stButton > button,
        div[data-testid="stFormSubmitButton"] > button{
          background: linear-gradient(180deg, rgba(30,115,190,0.95), rgba(11,79,138,0.95)) !important;
          border: 1px solid rgba(2,6,23,0.10) !important;
          border-radius: 12px !important;
          color: #ffffff !important;
          padding: 0.60rem 1.0rem !important;
          box-shadow: 0 10px 20px rgba(2,6,23,0.18);
        }
        .stButton > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover{
          filter: brightness(1.07);
        }


        /* ====== BOTÕES DE DOWNLOAD (PDF/EXPORT) ====== */
        div.stDownloadButton > button{
          width: 100% !important;
          background: linear-gradient(180deg, rgba(0,168,107,0.95), rgba(0,130,85,0.95)) !important;
          border: 1px solid rgba(0,0,0,0.18) !important;
          border-radius: 12px !important;
          color: #111827 !important;
          font-weight: 900 !important;
          padding: 0.60rem 1.0rem !important;
          box-shadow: 0 10px 20px rgba(2,6,23,0.14);
        }
        div.stDownloadButton > button:hover{
          filter: brightness(1.06);
        }
        div.stDownloadButton > button:disabled{
          opacity: 0.85 !important;
          filter: none !important;
        }

        /* Dataframe estilo card */
        [data-testid="stDataFrame"]{
          border: 1px solid rgba(0,0,0,0.12);
          border-radius: 14px;
          overflow: hidden;
          background: rgba(255,255,255,0.92);
        }

        /* Banner topo (amarelo) */
        .brandbar{
          background: linear-gradient(90deg, #8B6508 0%, #B8860B 55%, #D4A017 100%);
          border-radius: 18px;
          padding: 14px 16px;
          margin-bottom: 14px;
          display: flex;
          gap: 14px;
          align-items: center;
          box-shadow: 0 10px 22px rgba(0,0,0,0.20);
        }
        .brandbar .title{
          color: #ffffff;
          font-weight: 900;
          font-size: 20px;
        }
        .brandbar .subtitle{
          color: rgba(255,255,255,0.90);
          font-weight: 600;
          font-size: 12px;
        }


        /* Chip da seção atual (sidebar) */
        .secao-chip{
          background: rgba(255,255,255,0.14);
          border: 1px solid rgba(255,255,255,0.25);
          padding: 8px 10px;
          border-radius: 12px;
          margin-top: 8px;
          margin-bottom: 8px;
          font-weight: 800;
          text-align: center;
          letter-spacing: 0.2px;
        }

/* ===== BOTÃO DESTAQUE (Relatório Diário Geral) ===== */
.relatorio-btn .stButton > button{
  width: 100% !important;
  background: linear-gradient(90deg, #00A86B 0%, #1E73BE 55%, #0B4F8A 100%) !important;
  border: 2px solid rgba(255,255,255,0.60) !important;
  border-radius: 14px !important;
  color: #ffffff !important;
  font-weight: 900 !important;
  letter-spacing: 0.2px;
  padding: 0.80rem 1rem !important;
  box-shadow: 0 14px 28px rgba(0,0,0,0.28) !important;
}

.relatorio-btn .stButton > button:hover{
  filter: brightness(1.12);
  transform: translateY(-1px);
}

.relatorio-btn .stButton > button:active{
  transform: translateY(0px);
}

        </style>
        """,
        unsafe_allow_html=True
    )

def render_branding_sidebar():
    """Logo fixa no sidebar (coloque logo_app.png ou logo.png na pasta do app)."""
    logo_path = _find_logo_path()
    with st.sidebar:
        if logo_path:
            st.image(logo_path, use_container_width=True)
        st.markdown("### 💰 Financeiro")
        st.caption("Sistema interno • acesso por login")

def render_brandbar_topo():
    """Banner no topo (opcional, mas fica bonito)."""
    logo_path = _find_logo_path()
    if logo_path:
        uri = _img_to_data_uri(logo_path)
        st.markdown(
            f"""
            <div class="brandbar">
              <img src="{uri}" style="height:56px; width:auto; border-radius:12px; background: rgba(255,255,255,0.12); padding:6px;" />
              <div>
                <div class="title">Financeiro</div>
                <div class="subtitle">PEDRO FONSECA ENG. E CONSTRUTORA</div>
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
                <div class="title">Financeiro</div>
                <div class="subtitle">Coloque um arquivo <b>logo_app.png</b> (ou logo.png) na mesma pasta do .py.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )


# =========================
# CONSTANTES
# =========================
DB_PATH = "banco.db"
GLOBAL = "GLOBAL"

EMPRESAS = [
    "01_Escritório",
    "02_Adm de Obras",
    "03_Fábrica",
    "04_Locação de Equipamentos",
    "05_Refil",
]

FORMAS_PAGAMENTO = ["Dinheiro", "Pix/Transferência", "Boleto", "Cheque", "Cartão"]
SITUACOES = ["Pago", "Em aberto"]


# =========================
# BANCO DE DADOS
# =========================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


conn = get_conn()
cursor = conn.cursor()


def ensure_column(table: str, column: str, coltype: str):
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [c[1] for c in cursor.fetchall()]
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
        conn.commit()


def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE,
        senha TEXT,          -- legado (texto puro)
        senha_hash TEXT,
        nivel TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categorias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa TEXT NOT NULL,
        tipo TEXT,              -- NULL (vale p/ tudo) ou 'entrada' ou 'saida'
        nome TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contas_bancarias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa TEXT NOT NULL,
        nome TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa TEXT,
        tipo TEXT,              -- 'entrada' ou 'saida'
        numero_item INTEGER,    -- legado (não usado)
        data_operacao TEXT,     -- ISO: YYYY-MM-DD
        descricao TEXT,
        categoria TEXT,
        conta_bancaria TEXT,
        valor REAL,
        forma_pagamento TEXT,   -- Dinheiro, Cheque, Cartão
        parcelas INTEGER,
        primeiro_debito TEXT,   -- ISO: YYYY-MM-DD
        situacao TEXT           -- Pago, Em aberto
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS parcelas_agendadas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lancamento_id INTEGER NOT NULL,
        parcela_num INTEGER NOT NULL,
        data_debito TEXT NOT NULL,     -- ISO: YYYY-MM-DD
        paga INTEGER DEFAULT 0,        -- 0/1
        UNIQUE(lancamento_id, parcela_num)
    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS extratos_diarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa TEXT NOT NULL,
        conta_bancaria TEXT NOT NULL,
        data_ref TEXT NOT NULL,          -- ISO: YYYY-MM-DD
        saldo_inicio REAL,
        saldo_fim REAL,
        usuario TEXT,
        criado_em TEXT DEFAULT (datetime('now')),
        UNIQUE(empresa, conta_bancaria, data_ref)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meses_fechados (
        empresa TEXT NOT NULL,
        ano INTEGER NOT NULL,
        mes INTEGER NOT NULL,
        fechado INTEGER DEFAULT 0,
        fechado_em TEXT,
        fechado_por TEXT,
        PRIMARY KEY (empresa, ano, mes)
    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dias_fechados (
        empresa TEXT NOT NULL,
        conta_bancaria TEXT NOT NULL,
        data_ref TEXT NOT NULL,       -- ISO: YYYY-MM-DD
        fechado INTEGER DEFAULT 1,
        fechado_em TEXT,
        fechado_por TEXT,
        PRIMARY KEY (empresa, conta_bancaria, data_ref)
    )
    """)


    conn.commit()

    # Garantias para banco antigo
    ensure_column("usuarios", "senha_hash", "TEXT")
    ensure_column("dados", "tipo", "TEXT")
    ensure_column("dados", "numero_item", "INTEGER")
    ensure_column("dados", "data_operacao", "TEXT")
    ensure_column("dados", "categoria", "TEXT")
    ensure_column("dados", "conta_bancaria", "TEXT")
    ensure_column("dados", "forma_pagamento", "TEXT")
    ensure_column("dados", "parcelas", "INTEGER")
    ensure_column("dados", "primeiro_debito", "TEXT")
    ensure_column("dados", "situacao", "TEXT")
    ensure_column("parcelas_agendadas", "paga", "INTEGER")
    ensure_column("extratos_diarios", "empresa", "TEXT")
    ensure_column("extratos_diarios", "conta_bancaria", "TEXT")
    ensure_column("extratos_diarios", "data_ref", "TEXT")
    ensure_column("extratos_diarios", "saldo_inicio", "REAL")
    ensure_column("extratos_diarios", "saldo_fim", "REAL")
    ensure_column("extratos_diarios", "usuario", "TEXT")
    ensure_column("extratos_diarios", "criado_em", "TEXT")


    # Usuário padrão
    cursor.execute("SELECT COUNT(1) FROM usuarios")
    if (cursor.fetchone()[0] or 0) == 0:
        cursor.execute(
            "INSERT INTO usuarios (usuario, senha, senha_hash, nivel) VALUES (?, ?, ?, ?)",
            ("admin", None, hash_senha("123"), "admin")
        )
        conn.commit()


# =========================
# HELPERS (FORMATAÇÃO / EXPORT / HEADER)
# =========================
def br_money(x) -> str:
    try:
        v = float(x or 0)
        s = f"{v:,.2f}"
        # troca padrão US -> BR
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {s}"
    except Exception:
        return str(x)


def iso_to_br(iso: str) -> str:
    try:
        return date.fromisoformat(str(iso)).strftime("%d/%m/%Y")
    except Exception:
        return str(iso) if iso is not None else ""


def format_df_dates(df: pd.DataFrame, cols):
    df2 = df.copy()
    for c in cols:
        if c in df2.columns:
            df2[c] = df2[c].apply(iso_to_br)
    return df2


def df_to_excel_bytes(df: pd.DataFrame, sheet_name="Dados") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def df_to_pdf_bytes(df: pd.DataFrame, title: str, max_rows: int = 300) -> bytes:
    df2 = df.copy()
    if len(df2) > max_rows:
        df2 = df2.head(max_rows)

    def cell_str(x):
        s = "" if x is None else str(x)
        s = s.replace("\n", " ")
        return (s[:60] + "…") if len(s) > 60 else s

    data = [list(df2.columns)]
    for _, row in df2.iterrows():
        data.append([cell_str(v) for v in row.values.tolist()])

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=18,
        rightMargin=18,
        topMargin=18,
        bottomMargin=18
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 10))

    if len(df) > max_rows:
        story.append(Paragraph(f"(Mostrando apenas as primeiras {max_rows} linhas para caber no PDF.)", styles["Normal"]))
        story.append(Spacer(1, 8))

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ]))

    story.append(table)
    doc.build(story)
    return buf.getvalue()


def relatorio_diario_geral_pdf_todas_empresas(data_ref: date) -> bytes:
    """Gera um PDF único (todas as empresas) no formato do relatório diário geral.

    Ajustes:
    - Tabela sempre cabe na página (colWidths automáticos)
    - Quebra de texto em Descrição/Categoria
    - Marca d'água centralizada (logo) em TODAS as páginas
    - Cabeçalho (2 linhas) com as MESMAS cores e textos em negrito
    """
    buf = BytesIO()

    # margens
    left_margin = 18
    right_margin = 18
    top_margin = 18
    bottom_margin = 18

    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin
    )

    styles = getSampleStyleSheet()
    story = []

    # =========================
    # ✅ Quebra de texto (Paragraph dentro da tabela)
    # =========================
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.utils import ImageReader

    cell_style = ParagraphStyle(
        name="Cell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        alignment=TA_LEFT,
        wordWrap="CJK",
    )
    cell_center = ParagraphStyle(
        name="CellCenter",
        parent=cell_style,
        alignment=TA_CENTER
    )

    # Cabeçalho (negrito) — mesma métrica do corpo
    hdr_style = ParagraphStyle(
        name="Hdr",
        parent=cell_style,
        fontName="Helvetica-Bold",
    )
    hdr_center = ParagraphStyle(
        name="HdrCenter",
        parent=hdr_style,
        alignment=TA_CENTER
    )

    def _esc(txt):
        t = "" if txt is None else str(txt)
        return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    def P(txt, center: bool = False):
        return Paragraph(_esc(txt), cell_center if center else cell_style)

    def H(txt, center: bool = False):
        return Paragraph(_esc(txt), hdr_center if center else hdr_style)

    # =========================
    # ✅ Marca d'água (logo central)
    # =========================
    def _guess_logo_path() -> str | None:
        # tenta usar _find_logo_path() se existir no arquivo
        try:
            p = _find_logo_path()  # type: ignore[name-defined]
            if p and os.path.exists(p):
                return p
        except Exception:
            pass

        # fallback: procura na pasta do script
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            for nm in ("logo_app.png", "logo.png", "logo_app.jpg", "logo.jpg", "logo_app.jpeg", "logo.jpeg"):
                pp = os.path.join(base_dir, nm)
                if os.path.exists(pp):
                    return pp
        except Exception:
            pass
        return None

    watermark_path = _guess_logo_path()

    def _on_page(canvas, doc_):
        if not watermark_path:
            return
        try:
            canvas.saveState()

            # transparência (se disponível)
            if hasattr(canvas, "setFillAlpha"):
                canvas.setFillAlpha(0.10)
            elif hasattr(canvas, "setStrokeAlpha"):
                canvas.setStrokeAlpha(0.10)

            img = ImageReader(watermark_path)
            iw, ih = img.getSize()

            pw, ph = doc_.pagesize
            # ocupa ~45% da largura/altura (ajuste aqui se quiser maior/menor)
            max_w = pw * 0.45
            max_h = ph * 0.45
            scale = min(max_w / float(iw), max_h / float(ih))
            w = float(iw) * scale
            h = float(ih) * scale

            x = (pw - w) / 2.0
            y = (ph - h) / 2.0

            canvas.drawImage(img, x, y, width=w, height=h, mask="auto", preserveAspectRatio=True, anchor="c")
            canvas.restoreState()
        except Exception:
            try:
                canvas.restoreState()
            except Exception:
                pass

    titulo = f"Relatório Diário Geral — {data_ref.strftime('%d/%m/%Y')}"
    story.append(Paragraph(titulo, styles["Title"]))
    story.append(Spacer(1, 10))

    # largura útil real
    page_width = landscape(A4)[0]
    usable_width = page_width - (left_margin + right_margin)

    # ===== helpers DB =====
    def _mov_list(emp: str, tipo: str):
        cursor.execute(
            """
            SELECT valor, descricao, categoria
            FROM dados
            WHERE empresa=? AND tipo=? AND date(data_operacao)=date(?)
            ORDER BY id ASC
            """,
            (emp, tipo, data_ref.isoformat())
        )
        return [(float(r[0] or 0), r[1] or "", r[2] or "") for r in cursor.fetchall()]

    def _sum_mov(emp: str, tipo: str) -> float:
        cursor.execute(
            """
            SELECT COALESCE(SUM(valor),0)
            FROM dados
            WHERE empresa=? AND tipo=? AND date(data_operacao)=date(?)
            """,
            (emp, tipo, data_ref.isoformat())
        )
        return float(cursor.fetchone()[0] or 0)

    def _sum_saldos(emp: str):
        cursor.execute(
            """
            SELECT COALESCE(SUM(saldo_inicio),0), COALESCE(SUM(saldo_fim),0)
            FROM extratos_diarios
            WHERE empresa=? AND date(data_ref)=date(?)
            """,
            (emp, data_ref.isoformat())
        )
        r = cursor.fetchone() or (0, 0)
        return float(r[0] or 0), float(r[1] or 0)

    # ===== monta por empresa =====
    for idx, emp in enumerate(EMPRESAS):
        entradas = _mov_list(emp, "entrada")
        saidas = _mov_list(emp, "saida")

        ent_total = _sum_mov(emp, "entrada")
        sai_total = _sum_mov(emp, "saida")
        variacao = ent_total - sai_total

        saldo_ini, saldo_fim = _sum_saldos(emp)

        n = max(len(entradas), len(saidas), 1)

        header1 = [
            H("Empresas", center=True),
            H("Entrada", center=True), "", "",
            H("Saída", center=True), "", "",
            H("Variações de Transações do Dia", center=True),
            H("Valor do Extrato Inicial do Dia", center=True),
            H("Valor do Extrato Final do Dia", center=True),
        ]
        header2 = [
            "",
            H("Valor", center=True), H("Descrição", center=True), H("Categoria", center=True),
            H("Valor", center=True), H("Descrição", center=True), H("Categoria", center=True),
            "", "", ""
        ]
        data = [header1, header2]

        for i in range(n):
            e_val, e_desc, e_cat = ("", "", "")
            s_val, s_desc, s_cat = ("", "", "")

            if i < len(entradas):
                e_val = br_money(entradas[i][0])
                e_desc = entradas[i][1]
                e_cat = entradas[i][2]

            if i < len(saidas):
                s_val = br_money(saidas[i][0])
                s_desc = saidas[i][1]
                s_cat = saidas[i][2]

            var_txt = br_money(variacao) if i == 0 else ""
            ini_txt = br_money(saldo_ini) if i == 0 else ""
            fim_txt = br_money(saldo_fim) if i == 0 else ""

            data.append([
                P(emp, center=True),
                P(e_val, center=True), P(e_desc), P(e_cat),
                P(s_val, center=True), P(s_desc), P(s_cat),
                P(var_txt, center=True), P(ini_txt, center=True), P(fim_txt, center=True)
            ])

        # ✅ COLUNAS AUTOMÁTICAS (cabem na página)
        base_widths = [70, 55, 170, 120, 55, 170, 120, 90, 100, 100]
        total_base = sum(base_widths)
        col_widths = [(w / total_base) * usable_width for w in base_widths]

        table = Table(data, repeatRows=2, colWidths=col_widths)

        style = TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),

            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),

            # Cabeçalho 1 (linha 0)
            ("BACKGROUND", (0, 0), (0, 0), colors.lightgrey),
            ("BACKGROUND", (1, 0), (3, 0), colors.lightblue),
            ("BACKGROUND", (4, 0), (6, 0), colors.orange),
            ("BACKGROUND", (7, 0), (7, 0), colors.lightgrey),
            ("BACKGROUND", (8, 0), (9, 0), colors.lightgreen),

            ("ALIGN", (0, 0), (-1, 0), "CENTER"),

            # ✅ Cabeçalho 2 (linha 1) — MESMAS CORES da linha 0 (sem “quebrada”)
            ("BACKGROUND", (0, 1), (0, 1), colors.lightgrey),
            ("BACKGROUND", (1, 1), (3, 1), colors.lightblue),
            ("BACKGROUND", (4, 1), (6, 1), colors.orange),
            ("BACKGROUND", (7, 1), (7, 1), colors.lightgrey),
            ("BACKGROUND", (8, 1), (9, 1), colors.lightgreen),

            ("ALIGN", (0, 1), (-1, 1), "CENTER"),
        ])

        # spans
        style.add("SPAN", (1, 0), (3, 0))  # Entrada
        style.add("SPAN", (4, 0), (6, 0))  # Saída
        style.add("SPAN", (7, 0), (7, 1))  # Variações
        style.add("SPAN", (8, 0), (8, 1))  # Inicial
        style.add("SPAN", (9, 0), (9, 1))  # Final
        style.add("SPAN", (0, 0), (0, 1))  # Empresas

        table.setStyle(style)

        story.append(Paragraph(f"<b>{emp}</b>", styles["Heading2"]))
        story.append(Spacer(1, 6))
        story.append(table)

        if idx < len(EMPRESAS) - 1:
            story.append(Spacer(1, 14))
            story.append(PageBreak())

    # ✅ marca d'água em todas as páginas
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()

def empresa_to_logo_filename(empresa: str) -> str:
    nome = empresa.replace(" ", "_")
    nome = (nome.replace("ç", "c").replace("á", "a").replace("ã", "a").replace("â", "a")
                .replace("é", "e").replace("ê", "e").replace("í", "i")
                .replace("ó", "o").replace("ô", "o").replace("ú", "u"))
    return f"{nome}.png"


def render_header(pagina: str, empresa: str):
    col1, col2 = st.columns([1, 6], vertical_alignment="center")
    logo_path = os.path.join("logos", empresa_to_logo_filename(empresa))
    with col1:
        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)
        else:
            st.caption(".")
    with col2:
        st.markdown(f"## {pagina} — {empresa}")


# =========================
# AUTH / USUÁRIOS
# =========================
def hash_senha(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def autenticar(usuario: str, senha_digitada: str) -> Tuple[bool, Optional[str]]:
    cursor.execute("SELECT id, usuario, senha, senha_hash, nivel FROM usuarios WHERE usuario=?", (usuario,))
    row = cursor.fetchone()
    if not row:
        return False, None

    user_id, _, senha_legado, senha_hash_db, nivel = row
    senha_digitada = senha_digitada or ""

    if senha_hash_db:
        return (hash_senha(senha_digitada) == senha_hash_db), nivel

    # migração do legado texto puro -> hash
    if senha_legado is not None and senha_digitada == senha_legado:
        cursor.execute(
            "UPDATE usuarios SET senha_hash=?, senha=NULL WHERE id=?",
            (hash_senha(senha_digitada), user_id)
        )
        conn.commit()
        return True, nivel

    return False, None


def contar_admins() -> int:
    cursor.execute("SELECT COUNT(1) FROM usuarios WHERE nivel='admin'")
    return cursor.fetchone()[0] or 0


def atualizar_senha_por_usuario(usuario: str, nova_senha: str):
    cursor.execute(
        "UPDATE usuarios SET senha_hash=?, senha=NULL WHERE usuario=?",
        (hash_senha(nova_senha), usuario)
    )
    conn.commit()


def atualizar_senha_por_id(user_id: int, nova_senha: str):
    cursor.execute(
        "UPDATE usuarios SET senha_hash=?, senha=NULL WHERE id=?",
        (hash_senha(nova_senha), int(user_id))
    )
    conn.commit()


def atualizar_nivel_por_id(user_id: int, novo_nivel: str):
    cursor.execute("UPDATE usuarios SET nivel=? WHERE id=?", (novo_nivel, int(user_id)))
    conn.commit()


# =========================
# CATEGORIAS / CONTAS (GLOBAL)
# =========================
def obter_categorias_banco(tipo=None) -> List[str]:
    if tipo in (None, ""):
        cursor.execute("""
            SELECT nome FROM categorias
            WHERE empresa=? AND (tipo IS NULL OR tipo='')
            ORDER BY nome
        """, (GLOBAL,))
    else:
        cursor.execute("""
            SELECT nome FROM categorias
            WHERE empresa=? AND (tipo IS NULL OR tipo='' OR tipo=?)
            ORDER BY nome
        """, (GLOBAL, tipo))
    return [r[0] for r in cursor.fetchall()]


def criar_categoria(tipo_ui: str, nome: str) -> Tuple[bool, str]:
    nome = (nome or "").strip()
    if not nome:
        return False, "Digite o nome da categoria."

    tipo_db = None if tipo_ui == "Geral (Entradas e Despesas)" else ("entrada" if tipo_ui == "Entradas" else "saida")

    cursor.execute("""
        SELECT 1 FROM categorias
        WHERE empresa=? AND COALESCE(tipo,'')=COALESCE(?, '') AND lower(nome)=lower(?)
        LIMIT 1
    """, (GLOBAL, tipo_db, nome))
    if cursor.fetchone():
        return False, "Essa categoria já existe."

    cursor.execute(
        "INSERT INTO categorias (empresa, tipo, nome) VALUES (?, ?, ?)",
        (GLOBAL, tipo_db, nome)
    )
    conn.commit()
    return True, "Categoria criada!"


def excluir_categoria_por_id(cat_id: int):
    cursor.execute("DELETE FROM categorias WHERE id=? AND empresa=?", (int(cat_id), GLOBAL))
    conn.commit()


def obter_contas_banco() -> List[str]:
    cursor.execute("""
        SELECT nome FROM contas_bancarias
        WHERE empresa=?
        ORDER BY nome
    """, (GLOBAL,))
    return [r[0] for r in cursor.fetchall()]


def criar_conta_bancaria(nome: str) -> Tuple[bool, str]:
    nome = (nome or "").strip()
    if not nome:
        return False, "Digite o nome da conta bancária."

    cursor.execute("""
        SELECT 1 FROM contas_bancarias
        WHERE empresa=? AND lower(nome)=lower(?)
        LIMIT 1
    """, (GLOBAL, nome))
    if cursor.fetchone():
        return False, "Essa conta já existe."

    cursor.execute(
        "INSERT INTO contas_bancarias (empresa, nome) VALUES (?, ?)",
        (GLOBAL, nome)
    )
    conn.commit()
    return True, "Conta bancária criada!"


def excluir_conta_por_id(conta_id: int):
    cursor.execute("DELETE FROM contas_bancarias WHERE id=? AND empresa=?", (int(conta_id), GLOBAL))
    conn.commit()


# =========================
# PARCELAS / CONTAS FUTURAS
# =========================
def add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    last_day = calendar.monthrange(y, m)[1]
    day = min(d.day, last_day)
    return date(y, m, day)


def gerar_datas_debito(primeiro: date, parcelas: int):
    return [add_months(primeiro, i) for i in range(parcelas)]


def criar_ou_recriar_parcelas_agendadas(lancamento_id: int, primeiro: date, parcelas: int, situacao: str):
    cursor.execute("DELETE FROM parcelas_agendadas WHERE lancamento_id=?", (int(lancamento_id),))
    datas = gerar_datas_debito(primeiro, int(parcelas))
    paga_default = 1 if (situacao == "Pago") else 0
    for i, ddeb in enumerate(datas, start=1):
        cursor.execute(
            """
            INSERT OR REPLACE INTO parcelas_agendadas (lancamento_id, parcela_num, data_debito, paga)
            VALUES (?, ?, ?, ?)
            """,
            (int(lancamento_id), int(i), ddeb.isoformat(), int(paga_default))
        )
    conn.commit()


def obter_parcelas_agendadas(lancamento_id: int):
    cursor.execute("""
        SELECT parcela_num, data_debito, COALESCE(paga,0)
        FROM parcelas_agendadas
        WHERE lancamento_id=?
        ORDER BY parcela_num
    """, (int(lancamento_id),))
    return cursor.fetchall()


def salvar_parcelas_agendadas(lancamento_id: int, rows: List[dict]):
    for r in rows:
        p = int(r["Parcela"])
        iso = str(r["Data"])
        paga = 1 if bool(r["Paga"]) else 0
        cursor.execute("""
            INSERT OR REPLACE INTO parcelas_agendadas (lancamento_id, parcela_num, data_debito, paga)
            VALUES (?, ?, ?, ?)
        """, (int(lancamento_id), p, iso, paga))
    conn.commit()


def recomputar_situacao_lancamento(lancamento_id: int):
    cursor.execute("SELECT COUNT(1) FROM parcelas_agendadas WHERE lancamento_id=?", (int(lancamento_id),))
    total = cursor.fetchone()[0] or 0
    if total <= 0:
        return

    cursor.execute("""
        SELECT COUNT(1) FROM parcelas_agendadas
        WHERE lancamento_id=? AND COALESCE(paga,0)=1
    """, (int(lancamento_id),))
    pagas = cursor.fetchone()[0] or 0

    situacao = "Pago" if pagas == total else "Em aberto"
    cursor.execute("UPDATE dados SET situacao=? WHERE id=?", (situacao, int(lancamento_id)))
    conn.commit()


def deletar_lancamento_e_parcelas(lanc_id: int, empresa: str):
    cursor.execute("DELETE FROM parcelas_agendadas WHERE lancamento_id=?", (int(lanc_id),))
    cursor.execute("DELETE FROM dados WHERE id=? AND empresa=?", (int(lanc_id), empresa))
    conn.commit()


# =========================
# FECHAMENTO DE MÊS (TRAVAR EDIÇÕES)
# =========================
def is_mes_fechado(empresa: str, ano: int, mes: int) -> bool:
    try:
        cursor.execute(
            "SELECT COALESCE(fechado,0) FROM meses_fechados WHERE empresa=? AND ano=? AND mes=?",
            (empresa, int(ano), int(mes))
        )
        r = cursor.fetchone()
        return bool(int(r[0])) if r else False
    except Exception:
        return False


def fechar_mes(empresa: str, ano: int, mes: int, usuario: str):
    cursor.execute(
        """
        INSERT INTO meses_fechados (empresa, ano, mes, fechado, fechado_em, fechado_por)
        VALUES (?, ?, ?, 1, date('now'), ?)
        ON CONFLICT(empresa, ano, mes) DO UPDATE SET
            fechado=1,
            fechado_em=date('now'),
            fechado_por=excluded.fechado_por
        """,
        (empresa, int(ano), int(mes), usuario or "")
    )
    conn.commit()


def reabrir_mes(empresa: str, ano: int, mes: int):
    cursor.execute(
        """
        INSERT INTO meses_fechados (empresa, ano, mes, fechado, fechado_em, fechado_por)
        VALUES (?, ?, ?, 0, NULL, NULL)
        ON CONFLICT(empresa, ano, mes) DO UPDATE SET
            fechado=0,
            fechado_em=NULL,
            fechado_por=NULL
        """,
        (empresa, int(ano), int(mes))
    )
    conn.commit()


def get_info_mes(empresa: str, ano: int, mes: int):
    cursor.execute(
        "SELECT COALESCE(fechado,0), fechado_em, fechado_por FROM meses_fechados WHERE empresa=? AND ano=? AND mes=?",
        (empresa, int(ano), int(mes))
    )
    r = cursor.fetchone()
    if not r:
        return 0, None, None
    return int(r[0] or 0), r[1], r[2]




# =========================
# FECHAMENTO DE DIA (TRAVAR EDIÇÕES)
# =========================
def is_dia_fechado(empresa: str, conta_bancaria: str, data_iso: str) -> bool:
    try:
        cursor.execute(
            "SELECT 1 FROM dias_fechados WHERE empresa=? AND conta_bancaria=? AND data_ref=? AND COALESCE(fechado,1)=1",
            (empresa, conta_bancaria, data_iso)
        )
        return cursor.fetchone() is not None
    except Exception:
        return False


def fechar_dia(empresa: str, conta_bancaria: str, data_iso: str, usuario: str):
    cursor.execute(
        """
        INSERT INTO dias_fechados (empresa, conta_bancaria, data_ref, fechado, fechado_em, fechado_por)
        VALUES (?, ?, ?, 1, datetime('now'), ?)
        ON CONFLICT(empresa, conta_bancaria, data_ref)
        DO UPDATE SET fechado=1, fechado_em=datetime('now'), fechado_por=excluded.fechado_por
        """,
        (empresa, conta_bancaria, data_iso, usuario)
    )
    conn.commit()


def reabrir_dia(empresa: str, conta_bancaria: str, data_iso: str):
    cursor.execute(
        """
        INSERT INTO dias_fechados (empresa, conta_bancaria, data_ref, fechado, fechado_em, fechado_por)
        VALUES (?, ?, ?, 0, NULL, NULL)
        ON CONFLICT(empresa, conta_bancaria, data_ref)
        DO UPDATE SET fechado=0, fechado_em=NULL, fechado_por=NULL
        """,
        (empresa, conta_bancaria, data_iso)
    )
    conn.commit()


def get_info_dia(empresa: str, conta_bancaria: str, data_iso: str):
    cursor.execute(
        "SELECT COALESCE(fechado,0), fechado_em, fechado_por FROM dias_fechados WHERE empresa=? AND conta_bancaria=? AND data_ref=?",
        (empresa, conta_bancaria, data_iso)
    )
    r = cursor.fetchone()
    if not r:
        return 0, None, None
    return int(r[0] or 0), r[1], r[2]



# =========================
# RESUMO POR CONTA (SALDO INI / FINAL)
# =========================
def resumo_por_conta(empresa: str, dt_ini: date, dt_fim: date) -> pd.DataFrame:
    cursor.execute("""
        SELECT DISTINCT conta_bancaria
        FROM dados
        WHERE empresa=? AND conta_bancaria IS NOT NULL AND conta_bancaria <> ''
        ORDER BY conta_bancaria
    """, (empresa,))
    contas_mov = [r[0] for r in cursor.fetchall()]

    contas_cadastro = obter_contas_banco()
    contas = sorted(set(contas_cadastro + contas_mov))

    rows = []
    for conta in contas:
        cursor.execute("""
            SELECT COALESCE(SUM(
                CASE WHEN tipo='entrada' THEN valor ELSE -valor END
            ), 0)
            FROM dados
            WHERE empresa=? AND conta_bancaria=? AND date(data_operacao) < date(?)
        """, (empresa, conta, dt_ini.isoformat()))
        saldo_ini = float(cursor.fetchone()[0] or 0)

        cursor.execute("""
            SELECT COALESCE(SUM(valor), 0)
            FROM dados
            WHERE empresa=? AND conta_bancaria=? AND tipo='entrada'
              AND date(data_operacao) >= date(?) AND date(data_operacao) <= date(?)
        """, (empresa, conta, dt_ini.isoformat(), dt_fim.isoformat()))
        entradas = float(cursor.fetchone()[0] or 0)

        cursor.execute("""
            SELECT COALESCE(SUM(valor), 0)
            FROM dados
            WHERE empresa=? AND conta_bancaria=? AND tipo='saida'
              AND date(data_operacao) >= date(?) AND date(data_operacao) <= date(?)
        """, (empresa, conta, dt_ini.isoformat(), dt_fim.isoformat()))
        saidas = float(cursor.fetchone()[0] or 0)

        saldo_final = saldo_ini + entradas - saidas
        rows.append([conta, saldo_ini, entradas, saidas, saldo_final])

    df = pd.DataFrame(rows, columns=["Conta", "Saldo Inicial", "Entradas (Período)", "Saídas (Período)", "Saldo Final"])
    return df


# =========================
# LOGIN (CONFIG)
# =========================
try:
    import config  # arquivo na raiz do projeto
except Exception:
    class config:
        LOGIN_ATIVO = False  # login desativado (temporário)


def gate_login():
    """Controla o acesso ao sistema.

    Para desativar o login temporariamente, defina config.LOGIN_ATIVO = False
    (criando um arquivo config.py na raiz do projeto) OU edite aqui.
    """
    # ✅ Bypass de login (modo rápido / manutenção)
    if not getattr(config, "LOGIN_ATIVO", True):
        st.session_state.logado = True
        # assume admin para liberar todas as telas enquanto o login estiver desligado
        st.session_state.usuario = st.session_state.get("usuario") or "admin"
        st.session_state.nivel = st.session_state.get("nivel") or "admin"
        return

    if "logado" not in st.session_state:
        st.session_state.logado = False

    if st.session_state.logado:
        return

    st.title("Login — Financeiro")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        ok, nivel = autenticar(usuario, senha)
        if ok:
            st.session_state.logado = True
            st.session_state.usuario = usuario
            st.session_state.nivel = nivel
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos")

    st.stop()



# =========================
# SIDEBAR (MENU PROFISSIONAL)
# =========================
def sidebar_menu() -> Tuple[str, str]:
    st.sidebar.title("Financeiro")
    empresa = st.sidebar.selectbox("Empresa", EMPRESAS)

    # 🔒 Se for admin, mostra tudo
    if st.session_state.get("nivel") == "admin":
        secoes = [
            "Operações", "Análises", "Agenda", "Extrato",
            "Saldo Inicial/Final e Antes da Operação",
            "Relatório Diário Geral",
            "Configurações"
        ]
    else:
        # 🔒 Usuário comum NÃO vê Configurações
        secoes = [
            "Operações", "Análises", "Agenda", "Extrato",
            "Saldo Inicial/Final e Antes da Operação",
            "Relatório Diário Geral"
        ]

    # ==========================
    # ✅ Estado do menu (seção atual)
    # ==========================
    sec_key = "secao_menu"
    if sec_key not in st.session_state:
        st.session_state[sec_key] = secoes[0]
    if st.session_state.get(sec_key) not in secoes:
        st.session_state[sec_key] = secoes[0]

    # ==========================
    # 🔥 BOTÃO FIXO (DESTAQUE) – Relatório Diário Geral
    # ==========================
    st.sidebar.markdown("<div class='relatorio-btn'>", unsafe_allow_html=True)
    go_rel = st.sidebar.button(
        "📊 Relatório Diário Geral",
        use_container_width=True,
        key="btn_relatorio_diario_geral"
    )
    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    if go_rel:
        # força a navegação SEM duplicar item no rádio
        st.session_state["_pagina_forcada"] = "Relatório Diário Geral"
        st.rerun()

    st.sidebar.markdown("---")

    secoes_radio = [s for s in secoes if s != "Relatório Diário Geral"]

    # evita erro se o valor salvo não existir mais na lista do rádio
    if st.session_state.get(sec_key) not in secoes_radio:
        st.session_state[sec_key] = secoes_radio[0] if secoes_radio else secoes[0]

    secao = st.sidebar.radio("Seção", secoes_radio, key=sec_key)

    # ==========================
    # MAPEAMENTO
    # ==========================
    if secao == "Operações":
        pagina = "Lançamentos"
    elif secao == "Análises":
        pagina = "Relatórios"
    elif secao == "Agenda":
        pagina = "Contas a Pagar / Receber"
    elif secao == "Extrato":
        pagina = "Extrato da Conta"
    elif secao == "Saldo Inicial/Final e Antes da Operação":
        pagina = "Saldo Inicial/Final"
    elif secao == "Relatório Diário Geral":
        pagina = "Relatório Diário Geral"
    elif secao == "Configurações":
        opcoes = ["Alterar Minha Senha"]
        if st.session_state.get("nivel") == "admin":
            opcoes += ["Gerenciar Categorias", "Gerenciar Contas Bancárias", "Gerenciar Usuários"]
        pagina = st.sidebar.selectbox("Opções", opcoes)
    else:
        pagina = "Lançamentos"

    # ==========================
    # ✅ Se o botão forçou a página, respeita a navegação
    # ==========================
    pagina_forcada = st.session_state.pop("_pagina_forcada", None)
    if pagina_forcada:
        pagina = pagina_forcada

    st.sidebar.markdown("---")
    st.sidebar.write(f"Usuário: {st.session_state.get('usuario', '')}")
    st.sidebar.write(f"Nível: {st.session_state.get('nivel', '')}")

    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.session_state.usuario = ""
        st.session_state.nivel = ""
        st.rerun()

    return empresa, pagina


# =========================
# PÁGINAS
# =========================

def page_lancamentos(empresa: str):
    render_header("Lançamentos", empresa)
    st.subheader("Operações (Entradas e Despesas)")

    # =========================
    # CONTROLE POR MÊS (FILTRAR + TRANCAR)
    # =========================
    meses_pt = [
        "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
        "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"
    ]
    hoje = date.today()
    key_ano = f"lanc_ano_{empresa}"
    key_mes = f"lanc_mes_{empresa}"
    if key_ano not in st.session_state:
        st.session_state[key_ano] = hoje.year
    if key_mes not in st.session_state:
        st.session_state[key_mes] = hoje.month

    colm1, colm2, colm3 = st.columns([2, 1, 3])
    with colm1:
        mes_sel_nome = st.selectbox(
            "Mês",
            meses_pt,
            index=int(st.session_state[key_mes]) - 1,
            key=f"{key_mes}_ui"
        )
        mes_sel = meses_pt.index(mes_sel_nome) + 1
        st.session_state[key_mes] = mes_sel
    with colm2:
        ano_sel = st.number_input("Ano", min_value=2000, max_value=2100, step=1, value=int(st.session_state[key_ano]))
        st.session_state[key_ano] = int(ano_sel)
    with colm3:
        fechado, fechado_em, fechado_por = get_info_mes(empresa, int(ano_sel), int(mes_sel))
        if int(fechado) == 1:
            st.warning(f"🔒 Mês FECHADO — {mes_sel_nome}/{int(ano_sel)} (por {fechado_por or '—'} em {fechado_em or '—'})")
        else:
            st.info(f"✅ Mês ABERTO — {mes_sel_nome}/{int(ano_sel)}")

        if st.session_state.get("nivel") == "admin":
            cbtn1, cbtn2 = st.columns(2)
            with cbtn1:
                if st.button("Fechar mês", disabled=(int(fechado) == 1)):
                    fechar_mes(empresa, int(ano_sel), int(mes_sel), st.session_state.get("usuario", ""))
                    st.success("Mês fechado! Não será possível alterar lançamentos desse mês.")
                    st.rerun()
            with cbtn2:
                if st.button("Reabrir mês", disabled=(int(fechado) == 0)):
                    reabrir_mes(empresa, int(ano_sel), int(mes_sel))
                    st.success("Mês reaberto!")
                    st.rerun()

    secao = st.radio("Selecione", ["Despesas", "Entradas"], horizontal=True)
    tipo = "saida" if secao == "Despesas" else "entrada"

    st.markdown("### Novo lançamento")
    # Data default fica dentro do mês selecionado (pra não “sumir” depois)
    data_default = hoje
    if data_default.year != int(ano_sel) or data_default.month != int(mes_sel):
        data_default = date(int(ano_sel), int(mes_sel), 1)
    data_op = st.date_input("Data da Operação", value=data_default)

    categorias = obter_categorias_banco(tipo=tipo)
    contas = obter_contas_banco()

    colA, colB = st.columns(2)
    with colA:
        if categorias:
            categoria = st.selectbox("Categoria", categorias)
        else:
            st.warning("Nenhuma categoria cadastrada. (Admin > Configurações)")
            categoria = st.text_input("Categoria (temporário)")
    with colB:
        if contas:
            conta_bancaria = st.selectbox("Conta Bancária", contas)
        else:
            st.warning("Nenhuma conta cadastrada. (Admin > Configurações)")
            conta_bancaria = st.text_input("Conta Bancária (temporário)")

    descricao = st.text_input("Descrição da Operação")
    valor = st.number_input("Valor", step=0.01, min_value=0.0)

    colF, colS = st.columns(2)
    with colF:
        forma_pagamento = st.selectbox("Forma de Pagamento", FORMAS_PAGAMENTO)
    with colS:
        situacao = st.selectbox("Situação", SITUACOES)

    parcelas = None
    primeiro_debito = None
    edited_parc = None

    if forma_pagamento in ("Cheque", "Cartão", "Boleto"):
        colP, colD = st.columns(2)
        with colP:
            parcelas = st.number_input("Quantidade de parcelas", min_value=1, step=1, value=1)
        with colD:
            # Sugestão inicial (você pode editar todas as datas abaixo)
            primeiro_debito = st.date_input("Data do 1º débito (sugestão)", value=data_op)

        st.markdown("#### Datas das parcelas (editar manualmente)")
        datas_base = gerar_datas_debito(primeiro_debito, int(parcelas))
        df_parc_novo = pd.DataFrame({
            "Parcela": list(range(1, int(parcelas) + 1)),
            "Data": datas_base,
            "Paga": [True if situacao == "Pago" else False] * int(parcelas),
        })

        # Key muda quando parcelas/forma mudam => força refresh do editor
        editor_key = f"novas_parcelas_{forma_pagamento}_{int(parcelas)}_{situacao}"
        edited_parc = st.data_editor(
            df_parc_novo,
            use_container_width=True,
            num_rows="fixed",
            disabled=["Parcela"],
            key=editor_key
        )
    if st.button("Salvar lançamento", disabled=is_mes_fechado(empresa, int(data_op.year), int(data_op.month))):
        # 🔒 Bloqueio por mês fechado (pela data do lançamento)
        if is_mes_fechado(empresa, int(data_op.year), int(data_op.month)):
            st.error(f"Este mês está FECHADO ({data_op.month:02d}/{data_op.year}). Reabra o mês para lançar/alterar.")
            st.stop()
        # 🔒 Bloqueio por dia FECHADO (por conta)
        try:
            if is_dia_fechado(empresa, conta_bancaria, data_op.isoformat()):
                st.error(f"Este dia está FECHADO para a conta '{conta_bancaria}' ({data_op.strftime('%d/%m/%Y')}). Reabra o dia para lançar/alterar.")
                st.stop()
        except Exception:
            pass

        if not descricao:
            st.warning("Preencha a descrição.")
        elif not categoria:
            st.warning("Preencha a categoria.")
        elif not conta_bancaria:
            st.warning("Preencha a conta bancária.")
        elif valor <= 0:
            st.warning("Informe um valor maior que zero.")
        elif forma_pagamento in ("Cheque", "Cartão", "Boleto") and (not parcelas or int(parcelas) < 1):
            st.warning("Informe a quantidade de parcelas (mínimo 1).")
        elif forma_pagamento in ("Cheque", "Cartão", "Boleto") and (not primeiro_debito):
            st.warning("Informe a data do 1º débito.")
        else:
            # ====== PREPARO (parcelas manuais) ======
            parcelas_int = None
            primeiro_debito_db = None
            rows_to_save = None
            
            try:
                if forma_pagamento in ("Cheque", "Cartão", "Boleto"):
                    parcelas_int = int(parcelas)
                    if edited_parc is None or edited_parc.empty:
                        raise ValueError("Tabela de parcelas não carregou. Atualize a página e tente novamente.")
            
                    datas_list = []
                    rows_to_save = []
                    for _, row in edited_parc.iterrows():
                        d = row.get('Data')
                        if not isinstance(d, date):
                            d = pd.to_datetime(d).date()
                        datas_list.append(d)
                        rows_to_save.append({
                            'Parcela': int(row.get('Parcela')),
                            'Data': d.isoformat(),
                            'Paga': bool(row.get('Paga'))
                        })
            
                    # salva no lançamento a menor data das parcelas (para referência)
                    primeiro_debito_db = min(datas_list).isoformat() if datas_list else None
            except Exception as e:
                st.error(f"Erro nas parcelas: {e}")
                st.stop()
            
            # ====== INSERIR LANÇAMENTO ======
            cursor.execute(
                """
                INSERT INTO dados (
                    empresa, tipo, numero_item, data_operacao, descricao,
                    categoria, conta_bancaria, valor,
                    forma_pagamento, parcelas, primeiro_debito, situacao
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                ,
                (
                    empresa,
                    tipo,
                    None,
                    data_op.isoformat(),
                    descricao,
                    categoria,
                    conta_bancaria,
                    float(valor),
                    forma_pagamento,
                    parcelas_int,
                    primeiro_debito_db,
                    situacao
                )
            )
            conn.commit()
            
            # ====== SALVAR PARCELAS (manual) ======
            lanc_id = cursor.lastrowid
            if forma_pagamento in ("Cheque", "Cartão", "Boleto") and rows_to_save:
                salvar_parcelas_agendadas(int(lanc_id), rows_to_save)
                recomputar_situacao_lancamento(int(lanc_id))
            st.success(f"{secao} salva com sucesso!")
            st.rerun()

    st.markdown(f"### Lançamentos — {secao}")
    cursor.execute(
        """
        SELECT
            id, data_operacao, descricao,
            categoria, conta_bancaria, valor,
            forma_pagamento, parcelas, primeiro_debito, situacao
        FROM dados
        WHERE empresa=? AND tipo=?
          AND strftime('%Y', data_operacao)=?
          AND strftime('%m', data_operacao)=?
        ORDER BY id DESC
        """,
        (empresa, tipo, str(int(ano_sel)), f"{int(mes_sel):02d}")
    )
    linhas = cursor.fetchall()
    df_banco = pd.DataFrame(
        linhas,
        columns=["ID", "Data", "Descrição", "Categoria", "Conta", "Valor", "Forma", "Parcelas", "1º Débito", "Situação"]
    )
    df_show = format_df_dates(df_banco, ["Data", "1º Débito"])
    if "Valor" in df_show.columns:
        df_show["Valor"] = df_show["Valor"].apply(br_money)
    st.dataframe(df_show, use_container_width=True)

    st.markdown("### Excluir lançamento (opcional)")
    id_excluir = st.number_input("Digite o ID para excluir", min_value=0, step=1)
    if st.button("Excluir"):
        if id_excluir <= 0:
            st.warning("Informe um ID válido.")
        else:
            # 🔒 Não permite excluir lançamento de mês fechado
            cursor.execute("SELECT data_operacao, conta_bancaria FROM dados WHERE id=? AND empresa=?", (int(id_excluir), empresa))
            rr = cursor.fetchone()
            if not rr:
                st.warning("ID não encontrado nesta empresa.")
            else:
                try:
                    dtmp = date.fromisoformat(str(rr[0]))
                    if is_mes_fechado(empresa, int(dtmp.year), int(dtmp.month)):
                        st.error(f"Não posso excluir: mês FECHADO ({dtmp.month:02d}/{dtmp.year}).")
                        st.stop()
                    # 🔒 Não permite excluir lançamento de DIA fechado (por conta)
                    try:
                        conta_tmp = str(rr[1] or "")
                        if conta_tmp and is_dia_fechado(empresa, conta_tmp, dtmp.isoformat()):
                            st.error(f"Não posso excluir: dia FECHADO para a conta '{conta_tmp}' ({dtmp.strftime('%d/%m/%Y')}).")
                            st.stop()
                    except Exception:
                        pass
                except Exception:
                    pass

                deletar_lancamento_e_parcelas(int(id_excluir), empresa)
                st.success("Lançamento excluído.")
                st.rerun()


def page_relatorios(empresa: str):
    render_header("Relatórios", empresa)
    st.subheader("Relatórios (Banco)")

    colD1, colD2 = st.columns(2)
    with colD1:
        dt_ini = st.date_input("Data inicial", value=date.today().replace(day=1), key="rel_dt_ini")
    with colD2:
        dt_fim = st.date_input("Data final", value=date.today(), key="rel_dt_fim")

    colT, colSit = st.columns(2)
    with colT:
        filtro_tipo = st.selectbox("Tipo", ["Tudo", "Entradas", "Despesas"])
    with colSit:
        filtro_sit = st.selectbox("Situação", ["Todas"] + SITUACOES)

    wheres = ["empresa=?"]
    params = [empresa]

    wheres.append("date(data_operacao) >= date(?)")
    params.append(dt_ini.isoformat())
    wheres.append("date(data_operacao) <= date(?)")
    params.append(dt_fim.isoformat())

    if filtro_sit != "Todas":
        wheres.append("situacao=?")
        params.append(filtro_sit)

    cursor.execute("""
        SELECT DISTINCT categoria FROM dados
        WHERE empresa=? AND categoria IS NOT NULL AND categoria<>''
        ORDER BY categoria
    """, (empresa,))
    cats = [x[0] for x in cursor.fetchall()]

    cursor.execute("""
        SELECT DISTINCT conta_bancaria FROM dados
        WHERE empresa=? AND conta_bancaria IS NOT NULL AND conta_bancaria<>''
        ORDER BY conta_bancaria
    """, (empresa,))
    contas = [x[0] for x in cursor.fetchall()]

    cursor.execute("""
        SELECT DISTINCT forma_pagamento FROM dados
        WHERE empresa=? AND forma_pagamento IS NOT NULL AND forma_pagamento<>''
        ORDER BY forma_pagamento
    """, (empresa,))
    formas = [x[0] for x in cursor.fetchall()]

    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_cat = st.selectbox("Categoria", ["Todas"] + cats)
    with col2:
        filtro_conta = st.selectbox("Conta Bancária", ["Todas"] + contas)
    with col3:
        filtro_forma = st.selectbox("Forma", ["Todas"] + formas)

    if filtro_cat != "Todas":
        wheres.append("categoria=?")
        params.append(filtro_cat)

    if filtro_conta != "Todas":
        wheres.append("conta_bancaria=?")
        params.append(filtro_conta)

    if filtro_forma != "Todas":
        wheres.append("forma_pagamento=?")
        params.append(filtro_forma)

    if filtro_tipo == "Entradas":
        wheres.append("tipo='entrada'")
    elif filtro_tipo == "Despesas":
        wheres.append("tipo='saida'")

    where_sql = " AND ".join(wheres)

    cursor.execute(f"""
        SELECT
            id, tipo, data_operacao, descricao,
            categoria, conta_bancaria, valor,
            forma_pagamento, parcelas, primeiro_debito, situacao
        FROM dados
        WHERE {where_sql}
        ORDER BY id DESC
    """, tuple(params))

    linhas = cursor.fetchall()
    df_rel = pd.DataFrame(
        linhas,
        columns=["ID", "Tipo", "Data", "Descrição", "Categoria", "Conta", "Valor", "Forma", "Parcelas", "1º Débito", "Situação"]
    )

    df_rel_show = df_rel.copy()
    df_rel_show["Tipo"] = df_rel_show["Tipo"].replace({"entrada": "Entrada", "saida": "Despesa"})
    df_rel_show = format_df_dates(df_rel_show, ["Data", "1º Débito"])
    if "Valor" in df_rel_show.columns:
        df_rel_show["Valor"] = df_rel_show["Valor"].apply(br_money)

    st.dataframe(df_rel_show, use_container_width=True)

    st.markdown("### Resumo por conta bancária (Saldo inicial e final no período)")
    df_resumo = resumo_por_conta(empresa, dt_ini, dt_fim)
    df_resumo_show = df_resumo.copy()
    for c in ["Saldo Inicial", "Entradas (Período)", "Saídas (Período)", "Saldo Final"]:
        if c in df_resumo_show.columns:
            df_resumo_show[c] = df_resumo_show[c].apply(br_money)
    st.dataframe(df_resumo_show, use_container_width=True)

    st.markdown("### Exportar Relatório")
    csv_bytes = df_rel_show.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar CSV", data=csv_bytes, file_name="relatorio.csv", mime="text/csv")

    try:
        # Exportar com valores numéricos é melhor -> usa df_rel (sem BR money)
        df_rel_excel = format_df_dates(df_rel, ["Data", "1º Débito"])
        xlsx_bytes = df_to_excel_bytes(df_rel_excel, sheet_name="Relatorio")
        st.download_button(
            "Baixar Excel",
            data=xlsx_bytes,
            file_name="relatorio.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception:
        st.info("Excel não disponível (openpyxl).")

    try:
        pdf_bytes = df_to_pdf_bytes(
            df_rel_show,
            title=f"Relatório — {empresa} — {dt_ini.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"
        )
        st.download_button("Baixar PDF", data=pdf_bytes, file_name="relatorio.pdf", mime="application/pdf")
    except Exception:
        st.info("PDF não disponível (reportlab).")

    st.markdown("### Exportar Resumo por Conta")
    csv_res = df_resumo.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar CSV (Resumo)", data=csv_res, file_name="resumo_por_conta.csv", mime="text/csv")

    try:
        xlsx_res = df_to_excel_bytes(df_resumo, sheet_name="ResumoPorConta")
        st.download_button(
            "Baixar Excel (Resumo)",
            data=xlsx_res,
            file_name="resumo_por_conta.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception:
        st.info("Excel não disponível (openpyxl).")

    try:
        pdf_res = df_to_pdf_bytes(
            df_resumo_show,
            title=f"Resumo por Conta — {empresa} — {dt_ini.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"
        )
        st.download_button("Baixar PDF (Resumo)", data=pdf_res, file_name="resumo_por_conta.pdf", mime="application/pdf")
    except Exception:
        st.info("PDF não disponível (reportlab).")


def page_contas(empresa: str):
    render_header("Contas a Pagar / Receber", empresa)
    st.subheader("Agenda (parcelas futuras + controle de pagamento)")

    colA, colB, colC = st.columns(3)
    with colA:
        visao = st.selectbox("Visão", ["Em aberto", "Pago", "Tudo"])
    with colB:
        tipo_visao = st.selectbox("Tipo", ["Tudo", "Despesas (a pagar)", "Entradas (a receber)"])
    with colC:
        dias = st.number_input("Mostrar parcelas até (dias)", min_value=1, step=1, value=90)

    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_cat = st.text_input("Filtrar categoria (contém)", value="")
    with col2:
        filtro_conta = st.text_input("Filtrar conta (contém)", value="")
    with col3:
        so_parcelado = st.checkbox("Apenas parcelados (Cartão/Cheque/Boleto)", value=False)

    wheres = ["empresa=?"]
    params = [empresa]

    if visao == "Em aberto":
        wheres.append("COALESCE(situacao,'')='Em aberto'")
    elif visao == "Pago":
        wheres.append("COALESCE(situacao,'')='Pago'")

    if tipo_visao == "Despesas (a pagar)":
        wheres.append("tipo='saida'")
    elif tipo_visao == "Entradas (a receber)":
        wheres.append("tipo='entrada'")

    if filtro_cat.strip():
        wheres.append("LOWER(COALESCE(categoria,'')) LIKE ?")
        params.append(f"%{filtro_cat.strip().lower()}%")

    if filtro_conta.strip():
        wheres.append("LOWER(COALESCE(conta_bancaria,'')) LIKE ?")
        params.append(f"%{filtro_conta.strip().lower()}%")

    if so_parcelado:
        wheres.append("forma_pagamento IN ('Cheque','Cartão','Boleto') AND COALESCE(parcelas,0) >= 2")

    where_sql = " AND ".join(wheres)

    cursor.execute(f"""
        SELECT
            id, tipo, data_operacao, descricao,
            categoria, conta_bancaria, valor,
            forma_pagamento, parcelas, primeiro_debito, situacao
        FROM dados
        WHERE {where_sql}
        ORDER BY
            CASE WHEN COALESCE(situacao,'')='Em aberto' THEN 0 ELSE 1 END,
            COALESCE(data_operacao,'') DESC,
            id DESC
    """, tuple(params))

    rows = cursor.fetchall()
    df = pd.DataFrame(
        rows,
        columns=["ID", "Tipo", "Data Operação", "Descrição", "Categoria", "Conta", "Valor",
                 "Forma", "Parcelas", "1º Débito", "Situação"]
    )
    if not df.empty:
        df["Tipo"] = df["Tipo"].replace({"entrada": "Entrada", "saida": "Despesa"})
    df_show = format_df_dates(df, ["Data Operação", "1º Débito"])
    if "Valor" in df_show.columns:
        df_show["Valor"] = df_show["Valor"].apply(br_money)
    st.markdown("### Lançamentos")
    st.dataframe(df_show, use_container_width=True)

    st.markdown("### Próximos débitos (parcelas)")
    hoje = date.today()
    limite = hoje.toordinal() + int(dias)

    parcelas_linhas = []
    for r in rows:
        (_id, _tipo, _dataop, _desc, _cat, _conta, _valor, _forma, _parcelas, _pdeb, _sit) = r

        if _forma not in ("Cheque", "Cartão", "Boleto"):
            continue
        if not _parcelas or int(_parcelas) < 1:
            continue

        ag = obter_parcelas_agendadas(int(_id))

        # se não existir (banco antigo), cria automaticamente
        if (not ag) and _pdeb:
            try:
                primeiro = date.fromisoformat(_pdeb)
                criar_ou_recriar_parcelas_agendadas(int(_id), primeiro, int(_parcelas), _sit or "Em aberto")
                ag = obter_parcelas_agendadas(int(_id))
            except Exception:
                ag = []

        if not ag:
            continue

        valor_parcela = float(_valor) / int(_parcelas) if int(_parcelas) > 0 else float(_valor)

        for parcela_num, iso, paga in ag:
            try:
                ddeb = date.fromisoformat(iso)
            except Exception:
                continue
            if ddeb < hoje:
                continue
            if ddeb.toordinal() > limite:
                continue

            parcelas_linhas.append([
                int(_id),
                "Entrada" if _tipo == "entrada" else "Despesa",
                int(parcela_num),
                int(_parcelas),
                ddeb.strftime("%d/%m/%Y"),
                _desc,
                _cat,
                _conta,
                br_money(valor_parcela),
                _forma,
                "Sim" if int(paga) == 1 else "Não"
            ])

    df_parc = pd.DataFrame(parcelas_linhas, columns=[
        "ID Lanç.", "Tipo", "Parcela", "Total Parcelas", "Data Débito",
        "Descrição", "Categoria", "Conta", "Valor Parcela", "Forma", "Paga?"
    ])

    if df_parc.empty:
        st.info("Nenhuma parcela futura encontrada no período selecionado.")
    else:
        st.dataframe(df_parc, use_container_width=True)

    st.markdown("### Editar parcelas (datas e pagamento)")
    st.caption("Cheque/Cartão/Boleto: edita datas + marca paga.")

    id_editar = st.number_input("ID do lançamento parcelado", min_value=0, step=1)

    if id_editar > 0:
        cursor.execute("""
            SELECT forma_pagamento, parcelas, primeiro_debito, situacao, data_operacao
            FROM dados
            WHERE id=? AND empresa=?
        """, (int(id_editar), empresa))
        info = cursor.fetchone()

        if not info:
            st.warning("ID não encontrado nesta empresa.")
            return

        forma, qtd_parc, pdeb, sit, dataop_iso = info
        # 🔒 Se o mês do lançamento estiver fechado, bloqueia edição das parcelas
        try:
            dlock = date.fromisoformat(str(dataop_iso))
            if is_mes_fechado(empresa, int(dlock.year), int(dlock.month)):
                st.warning(f"🔒 Mês fechado ({dlock.month:02d}/{dlock.year}). Não é possível editar parcelas desse lançamento.")
                return
        except Exception:
            pass

        if forma not in ("Cheque", "Cartão", "Boleto"):
            st.warning("Esse lançamento não é Cheque/Cartão.")
            return
        if not qtd_parc or int(qtd_parc) < 1:
            st.warning("Esse lançamento não tem parcelas.")
            return

        ag = obter_parcelas_agendadas(int(id_editar))
        if (not ag) and pdeb:
            try:
                primeiro = date.fromisoformat(pdeb)
                criar_ou_recriar_parcelas_agendadas(int(id_editar), primeiro, int(qtd_parc), sit or "Em aberto")
                ag = obter_parcelas_agendadas(int(id_editar))
            except Exception:
                ag = []

        if not ag:
            st.error("Não foi possível carregar/criar as parcelas desse lançamento.")
            return

        df_edit = pd.DataFrame(ag, columns=["Parcela", "DataISO", "PagaInt"])
        df_edit["Data"] = df_edit["DataISO"].apply(lambda x: date.fromisoformat(x))
        df_edit["Paga"] = df_edit["PagaInt"].apply(lambda x: bool(int(x)))
        df_edit = df_edit[["Parcela", "Data", "Paga"]]

        disabled_cols = ["Parcela"]
        if forma not in ("Cheque", "Cartão", "Boleto"):
            disabled_cols.append("Data")

        edited = st.data_editor(
            df_edit,
            use_container_width=True,
            num_rows="fixed",
            disabled=disabled_cols
        )

        colS1, colS2 = st.columns(2)
        with colS1:
            if st.button("Salvar parcelas"):
                rows_to_save = []
                ok = True
                for _, row in edited.iterrows():
                    try:
                        p = int(row["Parcela"])
                        d = row["Data"]
                        if not isinstance(d, date):
                            ok = False
                            break
                        rows_to_save.append({
                            "Parcela": p,
                            "Data": d.isoformat(),
                            "Paga": bool(row["Paga"])
                        })
                    except Exception:
                        ok = False
                        break

                if not ok:
                    st.error("Alguma data está inválida. Ajuste e tente novamente.")
                else:
                    salvar_parcelas_agendadas(int(id_editar), rows_to_save)
                    recomputar_situacao_lancamento(int(id_editar))
                    st.success("Parcelas atualizadas!")
                    st.rerun()
        with colS2:
            if st.button("Marcar TODAS como pagas"):
                cursor.execute("UPDATE parcelas_agendadas SET paga=1 WHERE lancamento_id=?", (int(id_editar),))
                conn.commit()
                recomputar_situacao_lancamento(int(id_editar))
                st.success("Todas as parcelas marcadas como pagas.")
                st.rerun()


def page_extrato(empresa: str):
    render_header("Extrato", empresa)
    st.subheader("Extrato da Conta Bancária")

    contas = obter_contas_banco()
    conta_sel = st.selectbox("Conta Bancária", ["(Todas)"] + contas)

    colD1, colD2 = st.columns(2)
    with colD1:
        dt_ini = st.date_input("Data inicial", value=date.today().replace(day=1), key="ext_dt_ini")
    with colD2:
        dt_fim = st.date_input("Data final", value=date.today(), key="ext_dt_fim")

    wheres = ["empresa=?"]
    params = [empresa]

    if conta_sel != "(Todas)":
        wheres.append("conta_bancaria=?")
        params.append(conta_sel)

    wheres.append("date(data_operacao) >= date(?)")
    params.append(dt_ini.isoformat())
    wheres.append("date(data_operacao) <= date(?)")
    params.append(dt_fim.isoformat())

    where_sql = " AND ".join(wheres)

    cursor.execute(f"""
        SELECT
            id, tipo, data_operacao, descricao,
            categoria, conta_bancaria, valor,
            forma_pagamento, situacao
        FROM dados
        WHERE {where_sql}
        ORDER BY date(data_operacao) ASC, id ASC
    """, tuple(params))

    rows = cursor.fetchall()
    df_ext = pd.DataFrame(rows, columns=[
        "ID", "Tipo", "Data", "Descrição", "Categoria", "Conta", "Valor", "Forma", "Situação"
    ])

    if df_ext.empty:
        st.info("Nenhum lançamento no período.")
        return

    entradas = df_ext[df_ext["Tipo"] == "entrada"]["Valor"].sum()
    saidas = df_ext[df_ext["Tipo"] == "saida"]["Valor"].sum()
    saldo = entradas - saidas

    c1, c2, c3 = st.columns(3)
    c1.metric("Entradas", br_money(entradas))
    c2.metric("Saídas", br_money(saidas))
    c3.metric("Saldo (Entradas - Saídas)", br_money(saldo))

    df_show = df_ext.copy()
    df_show["Tipo"] = df_show["Tipo"].replace({"entrada": "Entrada", "saida": "Despesa"})
    df_show = format_df_dates(df_show, ["Data"])
    df_show["Valor"] = df_show["Valor"].apply(br_money)

    st.dataframe(df_show, use_container_width=True)

    st.markdown("### Exportar Extrato")
    csv_bytes = df_show.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar CSV", data=csv_bytes, file_name="extrato.csv", mime="text/csv")

    try:
        df_excel = df_ext.copy()
        df_excel["Tipo"] = df_excel["Tipo"].replace({"entrada": "Entrada", "saida": "Despesa"})
        df_excel = format_df_dates(df_excel, ["Data"])
        xlsx_bytes = df_to_excel_bytes(df_excel, sheet_name="Extrato")
        st.download_button(
            "Baixar Excel",
            data=xlsx_bytes,
            file_name="extrato.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception:
        st.info("Excel não disponível (openpyxl).")

    try:
        pdf_bytes = df_to_pdf_bytes(
            df_show,
            title=f"Extrato — {empresa} — {conta_sel} — {dt_ini.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"
        )
        st.download_button("Baixar PDF", data=pdf_bytes, file_name="extrato.pdf", mime="application/pdf")
    except Exception:
        st.info("PDF não disponível (reportlab).")





def page_extratos_diarios(empresa: str):
    render_header("Saldo Inicial/Final", empresa)
    st.subheader("Saldo Inicial/Final — Antes e Depois das Operações (por conta e dia)")

    contas = obter_contas_banco()
    if not contas:
        st.warning("Nenhuma conta bancária cadastrada. (Configurações > Gerenciar Contas Bancárias)")
        return

    st.markdown("### Lançar saldo do dia")
    col1, col2, col3 = st.columns(3)
    with col1:
        conta_sel = st.selectbox("Conta Bancária", contas, key="ed_conta")
    with col2:
        data_ref = st.date_input("Dia", value=date.today(), key="ed_data")
    with col3:
        # status do dia (aberto/fechado)
        fechado, fechado_em, fechado_por = get_info_dia(empresa, conta_sel, data_ref.isoformat())
        if int(fechado) == 1:
            st.error(f"📌 DIA FECHADO • {data_ref.strftime('%d/%m/%Y')} • {conta_sel}")
            if fechado_em or fechado_por:
                st.caption(f"Fechado em: {str(fechado_em) if fechado_em else '-'} • Por: {str(fechado_por) if fechado_por else '-'}")
        else:
            st.success("✅ DIA ABERTO")

    dia_fechado = is_dia_fechado(empresa, conta_sel, data_ref.isoformat())

    colA, colB = st.columns(2)
    with colA:
        saldo_ini = st.number_input(
            "Saldo no INÍCIO do dia (antes das operações)",
            step=0.01,
            value=0.0,
            key="ed_saldo_ini",
            disabled=dia_fechado
        )
    with colB:
        saldo_fim = st.number_input(
            "Saldo no FINAL do dia (após as operações)",
            step=0.01,
            value=0.0,
            key="ed_saldo_fim",
            disabled=dia_fechado
        )

    colS1, colS2, colS3 = st.columns([1, 1, 2])
    with colS1:
        if st.button("Salvar", disabled=dia_fechado):
            if is_dia_fechado(empresa, conta_sel, data_ref.isoformat()):
                st.error("Este dia está FECHADO. Reabra o dia para alterar os saldos.")
                st.stop()
            try:
                cursor.execute(
                    """
                    INSERT INTO extratos_diarios (empresa, conta_bancaria, data_ref, saldo_inicio, saldo_fim, usuario)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(empresa, conta_bancaria, data_ref)
                    DO UPDATE SET
                        saldo_inicio=excluded.saldo_inicio,
                        saldo_fim=excluded.saldo_fim,
                        usuario=excluded.usuario,
                        criado_em=datetime('now')
                    """,
                    (
                        empresa,
                        conta_sel,
                        data_ref.isoformat(),
                        float(saldo_ini),
                        float(saldo_fim),
                        st.session_state.get("usuario", "")
                    )
                )
                conn.commit()
                st.success("Salvos!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

    with colS2:
        # 🔒 Fechar/Reabrir dia (somente admin)
        if st.session_state.get("nivel") == "admin":
            if not dia_fechado:
                if st.button("Fechar dia"):
                    fechar_dia(empresa, conta_sel, data_ref.isoformat(), st.session_state.get("usuario", ""))
                    st.success("Dia fechado. Não será possível alterar esse dia.")
                    st.rerun()
            else:
                if st.button("Reabrir dia"):
                    reabrir_dia(empresa, conta_sel, data_ref.isoformat())
                    st.success("Dia reaberto.")
                    st.rerun()
        else:
            st.caption("Apenas admin pode fechar/reabrir o dia.")

    with colS3:
        st.caption("Dica: feche o dia quando terminar o lançamento de todas as operações daquele dia.")

    st.markdown("---")
    st.markdown("### Consultar saldos do mês")

    hoje = date.today()
    meses = [
        "01 - Janeiro", "02 - Fevereiro", "03 - Março", "04 - Abril", "05 - Maio", "06 - Junho",
        "07 - Julho", "08 - Agosto", "09 - Setembro", "10 - Outubro", "11 - Novembro", "12 - Dezembro"
    ]

    colf1, colf2, colf3 = st.columns(3)
    with colf1:
        conta_filtro = st.selectbox("Conta (filtro)", ["(Todas)"] + contas, key="ed_conta_filtro")
    with colf2:
        mes_sel = st.selectbox("Mês", meses, index=hoje.month - 1, key="ed_mes_filtro")
    with colf3:
        ano_sel = st.number_input("Ano", min_value=2000, max_value=2100, value=hoje.year, step=1, key="ed_ano_filtro")

    mes_num = int(str(mes_sel).split("-")[0].strip())

    wheres = ["empresa=?",
              "strftime('%m', date(data_ref))=?",
              "strftime('%Y', date(data_ref))=?"]
    params = [empresa, f"{mes_num:02d}", f"{int(ano_sel):04d}"]

    if conta_filtro != "(Todas)":
        wheres.append("conta_bancaria=?")
        params.append(conta_filtro)

    where_sql = " AND ".join(wheres)

    cursor.execute(
        f"""
        SELECT e.conta_bancaria, e.data_ref, e.saldo_inicio, e.saldo_fim, e.usuario,
               COALESCE(d.fechado,0) AS fechado
        FROM extratos_diarios e
        LEFT JOIN dias_fechados d
          ON d.empresa=e.empresa AND d.conta_bancaria=e.conta_bancaria AND d.data_ref=e.data_ref
        WHERE {where_sql}
        ORDER BY date(e.data_ref) ASC, e.conta_bancaria ASC
        """,
        tuple(params)
    )
    rows = cursor.fetchall()
    df = pd.DataFrame(rows, columns=["Conta", "Data", "Saldo Início", "Saldo Fim", "Usuário", "Fechado"])

    if df.empty:
        st.info("Nenhum saldo diário lançado para esse filtro.")
        return

    df_show = df.copy()
    df_show["Data"] = df_show["Data"].apply(iso_to_br)
    df_show["Saldo Início"] = df_show["Saldo Início"].apply(br_money)
    df_show["Saldo Fim"] = df_show["Saldo Fim"].apply(br_money)
    df_show["Fechado"] = df_show["Fechado"].apply(lambda x: "Sim" if int(x or 0) == 1 else "Não")

    st.dataframe(df_show, use_container_width=True)

    # Export
    csv_bytes = df_show.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar CSV (Saldos diários)", data=csv_bytes, file_name="saldos_diarios.csv", mime="text/csv")





def page_relatorio_diario_geral(empresa: str):
    render_header("Relatório Diário Geral", empresa)
    st.subheader("Relatório diário (saldo + movimentação do dia)")

    contas = obter_contas_banco()
    if not contas:
        st.warning("Nenhuma conta bancária cadastrada. (Configurações > Gerenciar Contas Bancárias)")
        return

    colf1, colf2 = st.columns([2, 2])
    with colf1:
        data_ref = st.date_input("Dia do relatório", value=date.today(), key="rdg_data")
    with colf2:
        conta_filtro = st.selectbox("Conta (filtro)", ["(Todas)"] + contas, key="rdg_conta")


    # ---------- PDF (todas as empresas) ----------
    try:
        pdf_all = relatorio_diario_geral_pdf_todas_empresas(data_ref)
        st.download_button(
            "📄 Baixar PDF (todas as empresas)",
            data=pdf_all,
            file_name=f"relatorio_diario_geral_{data_ref.isoformat()}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.info(f"PDF não disponível: {e}")

    # ---------- Helpers ----------

        def _sum_mov(tipo: str, conta: Optional[str]) -> float:
            if conta:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(valor), 0)
                    FROM dados
                    WHERE empresa=? AND tipo=? AND conta_bancaria=? AND date(data_operacao)=date(?)
                    """,
                    (empresa, tipo, conta, data_ref.isoformat())
                )
            else:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(valor), 0)
                    FROM dados
                    WHERE empresa=? AND tipo=? AND date(data_operacao)=date(?)
                    """,
                    (empresa, tipo, data_ref.isoformat())
                )
            return float(cursor.fetchone()[0] or 0)

        def _get_saldo(conta: str):
            cursor.execute(
                """
                SELECT saldo_inicio, saldo_fim, usuario
                FROM extratos_diarios
                WHERE empresa=? AND conta_bancaria=? AND date(data_ref)=date(?)
                """,
                (empresa, conta, data_ref.isoformat())
            )
            r = cursor.fetchone()
            if not r:
                return 0.0, 0.0, ""
            return float(r[0] or 0), float(r[1] or 0), (r[2] or "")

        # ---------- Monta resumo ----------
        contas_iter = contas if conta_filtro == "(Todas)" else [conta_filtro]

        linhas = []
        total_entradas = 0.0
        total_saidas = 0.0
        total_ini = 0.0
        total_fim = 0.0

        for conta in contas_iter:
            saldo_ini, saldo_fim, usuario = _get_saldo(conta)
            entradas = _sum_mov("entrada", conta)
            saidas = _sum_mov("saida", conta)

            calc_fim = saldo_ini + entradas - saidas
            diff = saldo_fim - calc_fim

            fechado = 1 if is_dia_fechado(empresa, conta, data_ref.isoformat()) else 0

            linhas.append([
                conta,
                saldo_ini,
                entradas,
                saidas,
                saldo_fim,
                calc_fim,
                diff,
                "Sim" if fechado == 1 else "Não",
                usuario
            ])

            total_ini += saldo_ini
            total_fim += saldo_fim
            total_entradas += entradas
            total_saidas += saidas

        df = pd.DataFrame(
            linhas,
            columns=[
                "Conta", "Saldo Inicial", "Entradas (dia)", "Saídas (dia)",
                "Saldo Final (informado)", "Saldo Final (calculado)", "Diferença", "Dia Fechado?", "Usuário (saldo)"
            ]
        )

        # ---------- Métricas ----------
        entradas_total = float(df["Entradas (dia)"].sum()) if not df.empty else 0.0
        saidas_total = float(df["Saídas (dia)"].sum()) if not df.empty else 0.0
        saldo_mov = entradas_total - saidas_total

        c1, c2, c3 = st.columns(3)
        c1.metric("Entradas (dia)", br_money(entradas_total))
        c2.metric("Saídas (dia)", br_money(saidas_total))
        c3.metric("Movimentação (Entradas - Saídas)", br_money(saldo_mov))

        st.markdown("### Resumo por conta")
        if df.empty:
            st.info("Sem dados para o filtro selecionado.")
        else:
            df_show = df.copy()
            for c in ["Saldo Inicial", "Entradas (dia)", "Saídas (dia)", "Saldo Final (informado)", "Saldo Final (calculado)", "Diferença"]:
                df_show[c] = df_show[c].apply(br_money)

            if (df["Diferença"].abs() > 0.009).any():
                st.warning("⚠️ Existe diferença entre o Saldo Final informado e o Saldo Final calculado em pelo menos uma conta.")

            st.dataframe(df_show, use_container_width=True)

            csv_bytes = df_show.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Baixar CSV (Relatório diário)",
                data=csv_bytes,
                file_name=f"relatorio_diario_{empresa}_{data_ref.isoformat()}.csv".replace("/", "-"),
                mime="text/csv"
            )

        st.markdown("---")
        st.markdown("### Operações do dia")

        wheres = ["empresa=?", "date(data_operacao)=date(?)"]
        params = [empresa, data_ref.isoformat()]

        if conta_filtro != "(Todas)":
            wheres.append("conta_bancaria=?")
            params.append(conta_filtro)

        where_sql = " AND ".join(wheres)

        cursor.execute(
            f"""
            SELECT
                id, tipo, data_operacao, descricao,
                categoria, conta_bancaria, valor, forma_pagamento, situacao
            FROM dados
            WHERE {where_sql}
            ORDER BY tipo DESC, id DESC
            """,
            tuple(params)
        )
        rows = cursor.fetchall()
        df_ops = pd.DataFrame(rows, columns=[
            "ID", "Tipo", "Data", "Descrição", "Categoria", "Conta", "Valor", "Forma", "Situação"
        ])

        if df_ops.empty:
            st.info("Nenhuma operação lançada nesse dia para o filtro.")
            return

        df_ops_show = df_ops.copy()
        df_ops_show["Tipo"] = df_ops_show["Tipo"].replace({"entrada": "Entrada", "saida": "Despesa"})
        df_ops_show["Data"] = df_ops_show["Data"].apply(iso_to_br)
        df_ops_show["Valor"] = df_ops_show["Valor"].apply(br_money)

        st.dataframe(df_ops_show, use_container_width=True)




def page_alterar_senha():
    render_header("Alterar Minha Senha", "—")
    st.subheader("Alterar minha senha")

    senha_atual = st.text_input("Senha atual", type="password")
    nova = st.text_input("Nova senha", type="password")
    nova2 = st.text_input("Confirmar nova senha", type="password")

    if st.button("Salvar nova senha"):
        ok, _ = autenticar(st.session_state.usuario, senha_atual)
        if not ok:
            st.error("Senha atual incorreta.")
        elif not nova or len(nova) < 4:
            st.warning("A nova senha precisa ter pelo menos 4 caracteres.")
        elif nova != nova2:
            st.warning("A confirmação não confere.")
        else:
            atualizar_senha_por_usuario(st.session_state.usuario, nova)
            st.success("Senha alterada com sucesso!")


def page_gerenciar_categorias():
    if st.session_state.nivel != "admin":
        st.error("Acesso negado. Apenas administradores.")
        st.stop()

    render_header("Gerenciar Categorias", "GLOBAL")
    st.subheader("Categorias (GLOBAL)")

    st.markdown("### Criar categoria")
    col1, col2 = st.columns([2, 3])
    with col1:
        tipo_cat_ui = st.selectbox("Tipo", ["Geral (Entradas e Despesas)", "Entradas", "Despesas"])
    with col2:
        nome_cat = st.text_input("Nome da categoria")

    if st.button("Adicionar categoria"):
        ok, msg = criar_categoria(tipo_cat_ui, nome_cat)
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.warning(msg)

    st.markdown("---")
    st.markdown("### Categorias cadastradas")
    cursor.execute("""
        SELECT id, tipo, nome
        FROM categorias
        WHERE empresa=?
        ORDER BY
            CASE
                WHEN tipo IS NULL OR tipo='' THEN 0
                WHEN tipo='entrada' THEN 1
                WHEN tipo='saida' THEN 2
                ELSE 9
            END,
            nome
    """, (GLOBAL,))
    rows = cursor.fetchall()

    def tipo_legivel(t):
        if t is None or t == "":
            return "Geral"
        if t == "entrada":
            return "Entradas"
        if t == "saida":
            return "Despesas"
        return t

    df_cats = pd.DataFrame(rows, columns=["ID", "Tipo", "Categoria"])
    if not df_cats.empty:
        df_cats["Tipo"] = df_cats["Tipo"].apply(tipo_legivel)
        st.dataframe(df_cats, use_container_width=True)
    else:
        st.info("Nenhuma categoria cadastrada.")

    st.markdown("### Excluir categoria")
    cat_id = st.number_input("ID da categoria para excluir", min_value=0, step=1)

    if st.button("Excluir categoria"):
        if cat_id <= 0:
            st.warning("Informe um ID válido.")
        else:
            cursor.execute("SELECT nome FROM categorias WHERE id=? AND empresa=?", (int(cat_id), GLOBAL))
            cat = cursor.fetchone()
            if not cat:
                st.warning("Categoria não encontrada.")
            else:
                nome_cat_ex = cat[0]
                cursor.execute("SELECT COUNT(1) FROM dados WHERE categoria=?", (nome_cat_ex,))
                qtd_uso = cursor.fetchone()[0] or 0
                if qtd_uso > 0:
                    st.error(f"Não posso excluir. Categoria usada em {qtd_uso} lançamento(s).")
                else:
                    excluir_categoria_por_id(cat_id)
                    st.success("Categoria excluída.")
                    st.rerun()


def page_gerenciar_contas_bancarias():
    if st.session_state.nivel != "admin":
        st.error("Acesso negado. Apenas administradores.")
        st.stop()

    render_header("Gerenciar Contas Bancárias", "GLOBAL")
    st.subheader("Contas bancárias (GLOBAL)")

    st.markdown("### Criar conta bancária")
    nome_conta = st.text_input("Nome da conta (ex: Itaú PJ, Caixa, Pix...)")

    if st.button("Adicionar conta bancária"):
        ok, msg = criar_conta_bancaria(nome_conta)
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.warning(msg)

    st.markdown("---")
    st.markdown("### Contas cadastradas")
    cursor.execute("""
        SELECT id, nome
        FROM contas_bancarias
        WHERE empresa=?
        ORDER BY nome
    """, (GLOBAL,))
    rows = cursor.fetchall()

    df_contas = pd.DataFrame(rows, columns=["ID", "Conta"])
    if not df_contas.empty:
        st.dataframe(df_contas, use_container_width=True)
    else:
        st.info("Nenhuma conta cadastrada.")

    st.markdown("### Excluir conta bancária")
    conta_id = st.number_input("ID da conta para excluir", min_value=0, step=1)

    if st.button("Excluir conta"):
        if conta_id <= 0:
            st.warning("Informe um ID válido.")
        else:
            cursor.execute("SELECT nome FROM contas_bancarias WHERE id=? AND empresa=?", (int(conta_id), GLOBAL))
            conta = cursor.fetchone()
            if not conta:
                st.warning("Conta não encontrada.")
            else:
                nome_conta_ex = conta[0]
                cursor.execute("SELECT COUNT(1) FROM dados WHERE conta_bancaria=?", (nome_conta_ex,))
                qtd_uso = cursor.fetchone()[0] or 0
                if qtd_uso > 0:
                    st.error(f"Não posso excluir. Conta usada em {qtd_uso} lançamento(s).")
                else:
                    excluir_conta_por_id(conta_id)
                    st.success("Conta excluída.")
                    st.rerun()


def page_gerenciar_usuarios():
    if st.session_state.nivel != "admin":
        st.error("Acesso negado. Apenas administradores.")
        st.stop()

    render_header("Gerenciar Usuários", "—")
    st.subheader("Usuários")

    st.markdown("### Criar novo usuário")
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        novo_usuario = st.text_input("Usuário (login)", key="novo_usuario")
    with col2:
        nova_senha = st.text_input("Senha", type="password", key="nova_senha")
    with col3:
        novo_nivel = st.selectbox("Nível", ["user", "admin"], key="novo_nivel")

    if st.button("Criar usuário"):
        u = (novo_usuario or "").strip()
        s = (nova_senha or "").strip()
        if not u:
            st.warning("Informe o usuário.")
        elif not s:
            st.warning("Informe a senha.")
        else:
            try:
                cursor.execute(
                    "INSERT INTO usuarios (usuario, senha, senha_hash, nivel) VALUES (?, NULL, ?, ?)",
                    (u, hash_senha(s), novo_nivel)
                )
                conn.commit()
                st.success("Usuário criado!")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Esse usuário já existe.")

    st.markdown("---")
    st.markdown("### Usuários cadastrados")
    cursor.execute("SELECT id, usuario, nivel FROM usuarios ORDER BY nivel DESC, usuario")
    users = cursor.fetchall()
    df_users = pd.DataFrame(users, columns=["ID", "Usuário", "Nível"])
    st.dataframe(df_users, use_container_width=True)

    st.markdown("### Alterar nível / Resetar senha")
    user_id_sel = st.number_input("ID do usuário", min_value=0, step=1, key="user_id_sel")

    colA, colB = st.columns(2)
    with colA:
        novo_nivel_sel = st.selectbox("Novo nível", ["user", "admin"], key="novo_nivel_sel")
        if st.button("Salvar nível"):
            if user_id_sel <= 0:
                st.warning("Informe um ID válido.")
            else:
                cursor.execute("SELECT usuario, nivel FROM usuarios WHERE id=?", (int(user_id_sel),))
                alvo = cursor.fetchone()
                if not alvo:
                    st.error("Usuário não encontrado.")
                else:
                    _, alvo_nivel = alvo
                    if alvo_nivel == "admin" and novo_nivel_sel != "admin" and contar_admins() <= 1:
                        st.error("Não é possível rebaixar o último administrador.")
                    else:
                        atualizar_nivel_por_id(user_id_sel, novo_nivel_sel)
                        st.success("Nível atualizado.")
                        st.rerun()

    with colB:
        nova_senha_reset = st.text_input("Nova senha (reset)", type="password", key="nova_senha_reset")
        if st.button("Resetar senha"):
            if user_id_sel <= 0:
                st.warning("Informe um ID válido.")
            elif not nova_senha_reset or len(nova_senha_reset) < 4:
                st.warning("Senha precisa ter pelo menos 4 caracteres.")
            else:
                atualizar_senha_por_id(user_id_sel, nova_senha_reset)
                st.success("Senha resetada.")
                st.rerun()

    st.markdown("### Excluir usuário")
    user_id_excluir = st.number_input("ID do usuário para excluir", min_value=0, step=1, key="user_id_excluir")

    if st.button("Excluir usuário"):
        if user_id_excluir <= 0:
            st.warning("Informe um ID válido.")
        else:
            cursor.execute("SELECT usuario, nivel FROM usuarios WHERE id=?", (int(user_id_excluir),))
            alvo = cursor.fetchone()
            if not alvo:
                st.warning("Usuário não encontrado.")
            else:
                alvo_usuario, alvo_nivel = alvo
                if alvo_usuario == st.session_state.usuario:
                    st.error("Você não pode excluir seu próprio usuário logado.")
                    st.stop()
                if alvo_nivel == "admin" and contar_admins() <= 1:
                    st.error("Não é possível excluir o último administrador.")
                    st.stop()

                cursor.execute("DELETE FROM usuarios WHERE id=?", (int(user_id_excluir),))
                conn.commit()
                st.success("Usuário excluído.")
                st.rerun()


# =========================
# APP (ROTEAMENTO)
# =========================
def run_app():
    init_db()
    gate_login()

    apply_light_theme()
    render_branding_sidebar()
    render_brandbar_topo()

    empresa, pagina = sidebar_menu()
    # Router
    if pagina == "Lançamentos":
        page_lancamentos(empresa)
    elif pagina == "Relatórios":
        page_relatorios(empresa)
    elif pagina == "Contas a Pagar / Receber":
        page_contas(empresa)
    elif pagina == "Extrato da Conta":
        page_extrato(empresa)
    elif pagina == "Saldo Inicial/Final":
        page_extratos_diarios(empresa)
    elif pagina == "Relatório Diário Geral":
        page_relatorio_diario_geral(empresa)
    elif pagina == "Alterar Minha Senha":
        page_alterar_senha()
    elif pagina == "Gerenciar Categorias":
        page_gerenciar_categorias()
    elif pagina == "Gerenciar Contas Bancárias":
        page_gerenciar_contas_bancarias()
    elif pagina == "Gerenciar Usuários":
        page_gerenciar_usuarios()
    else:
        st.error("Página não encontrada.")


if __name__ == "__main__":
    run_app()
