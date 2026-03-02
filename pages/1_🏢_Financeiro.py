import db_adapter
import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import calendar
from datetime import date, timedelta
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

# Usa o adapter unificado (SQLite local / Postgres Supabase)
# DB_PATH = caminho do seu .db (já existe no seu código)
def get_conn():
    return db_adapter.get_conn(DB_PATH)

conn = get_conn()
cursor = db_adapter.get_cursor(conn)


def _get_active_schema() -> str:
    """
    Tenta descobrir o schema ativo no Postgres.
    - Se o db_adapter tiver current_schema(), usa ele.
    - Senão, usa 'public'.
    """
    try:
        if hasattr(db_adapter, "current_schema"):
            s = db_adapter.current_schema()
            if s:
                return str(s)
    except Exception:
        pass
    return "public"


def ensure_column(table: str, column: str, coltype: str):
    """
    Garante que a coluna existe em SQLite e Postgres.
    - SQLite: PRAGMA table_info
    - Postgres: information_schema.columns + ALTER TABLE ADD COLUMN IF NOT EXISTS

    Importante:
    - No Postgres, placeholders são %s (não '?')
    - table_schema precisa ser resolvido corretamente (schema ativo / public)
    """
    # Postgres
    if db_adapter.backend() == db_adapter.BACKEND_POSTGRES:
        schema = _get_active_schema()

        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name   = %s
              AND column_name  = %s
            LIMIT 1
            """,
            (schema, table, column),
        )
        exists = cursor.fetchone() is not None

        if not exists:
            # IF NOT EXISTS evita erro se rodar 2x
            cursor.execute(
                f'ALTER TABLE "{schema}"."{table}" ADD COLUMN IF NOT EXISTS "{column}" {coltype}'
            )
            conn.commit()
        return

    # SQLite
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [c[1] for c in cursor.fetchall()]
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
        conn.commit()


def init_db():
    """
    Criação/garantia de tabelas.
    Observação: SQLite aceita AUTOINCREMENT; Postgres não.
    Seu db_adapter normalmente converte isso; se não converter, o Postgres vai reclamar.
    """
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
        criado_em TEXT,         -- ISO: YYYY-MM-DD (data de criação do lançamento)
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
        data_quitacao TEXT,            -- ISO: YYYY-MM-DD (data efetiva de quitação)
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
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
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
    CREATE TABLE IF NOT EXISTS configuracoes_empresa (
        empresa TEXT PRIMARY KEY,
        trava_mes_apos_fim INTEGER DEFAULT 1,
        atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        atualizado_por TEXT
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

    # ✅ Garantias (não vai mais quebrar no Postgres)
    ensure_column("usuarios", "senha_hash", "TEXT")

    # Garantias para banco antigo (SQLite) e também seguro no Postgres
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
    ensure_column("dados", "criado_em", "TEXT")
    ensure_column("parcelas_agendadas", "paga", "INTEGER")
    ensure_column("parcelas_agendadas", "data_quitacao", "TEXT")
    ensure_column("extratos_diarios", "empresa", "TEXT")
    ensure_column("extratos_diarios", "conta_bancaria", "TEXT")
    ensure_column("extratos_diarios", "data_ref", "TEXT")
    ensure_column("extratos_diarios", "saldo_inicio", "REAL")
    ensure_column("extratos_diarios", "saldo_fim", "REAL")
    ensure_column("extratos_diarios", "usuario", "TEXT")
    ensure_column("extratos_diarios", "criado_em", "TEXT")

    # ✅ Migração: se o banco era antigo e não tinha 'criado_em',
    # preenche com 'data_operacao' para não quebrar filtros.
    try:
        cursor.execute(
            """
            UPDATE dados
            SET criado_em = COALESCE(NULLIF(criado_em,''), data_operacao)
            WHERE criado_em IS NULL OR criado_em=''
            """
        )
        conn.commit()
    except Exception:
        pass

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
        # ✅ Usa o critério do CAIXA (pagos no dia), não a tela de Lançamentos
        return caixa_mov_list_dia(emp, tipo, data_ref)

    def _sum_mov(emp: str, tipo: str) -> float:
        # ✅ Usa o critério do CAIXA (pagos no dia), não a tela de Lançamentos
        return caixa_sum_dia(emp, tipo, data_ref, conta=None)

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

        # ✅ Previsão de pagamento (próximo dia útil)
        prox = proximo_dia_util(data_ref)
        df_prev = obter_previsao_pagamento(emp, prox)

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
        base_widths = [70, 95, 155, 110, 95, 155, 110, 90, 100, 100]  # ajustado: colunas de VALOR maiores
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

        # ⚠️ Aviso de divergência (saldo final informado x calculado)
        try:
            calc_fim_emp = float(saldo_ini) + float(variacao)
            if abs(float(saldo_fim) - calc_fim_emp) > 0.009:
                story.append(Paragraph(
                    "<font color='red'><b>⚠️ Atenção:</b> existe variação de valores (o Extrato Final do Dia não confere com a movimentação do dia + saldo inicial).</font>",
                    styles["Normal"]
                ))
                story.append(Spacer(1, 6))
        except Exception:
            pass

        # 📌 Previsão de pagamento (próximo dia útil)
        try:
            story.append(Paragraph(f"Previsão de pagamento — {prox.strftime('%d/%m/%Y')}", styles["Heading3"]))
            if df_prev is None or df_prev.empty:
                story.append(Paragraph("Sem previsões de pagamento para o próximo dia útil.", styles["Normal"]))
            else:
                df_prev2 = df_prev.copy().head(20)
                total_prev = float(df_prev2["Valor"].sum()) if "Valor" in df_prev2.columns else 0.0

                prev_data = [[
                    H("Parcela", center=True),
                    H("Valor", center=True),
                    H("Descrição", center=True),
                    H("Categoria", center=True),
                    H("Forma", center=True),
                ]]

                for _, r in df_prev2.iterrows():
                    prev_data.append([
                        P(str(r.get("Parcela", "")), center=True),
                        P(br_money(r.get("Valor", 0)), center=True),
                        P(str(r.get("Descrição", ""))),
                        P(str(r.get("Categoria", ""))),
                        P(str(r.get("Forma", "")), center=True),
                    ])

                # linha total
                prev_data.append([
                    P("TOTAL", center=True),
                    P(br_money(total_prev), center=True),
                    P("", center=True),
                    P("", center=True),
                    P("", center=True),
                ])

                prev_widths = [70, 80, 260, 160, 110]
                total_w = sum(prev_widths)
                prev_colw = [(w / total_w) * usable_width for w in prev_widths]

                prev_table = Table(prev_data, repeatRows=1, colWidths=prev_colw)
                prev_table.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
                ]))
                story.append(prev_table)
            story.append(Spacer(1, 10))
        except Exception:
            # não derruba o PDF se der erro na previsão
            story.append(Spacer(1, 6))

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


def proximo_dia_util(d: date) -> date:
    """Retorna o próximo dia útil (D+1; se cair sábado/domingo, pula para segunda)."""
    nd = d + timedelta(days=1)
    while nd.weekday() >= 5:  # 5=sábado, 6=domingo
        nd += timedelta(days=1)
    return nd


def obter_previsao_pagamento(empresa: str, data_debito: date) -> pd.DataFrame:
    """Previsão de pagamentos (despesas) para uma data específica.

    Considera:
    - Parcelas agendadas NÃO pagas (parcelas_agendadas) vinculadas a lançamentos de SAÍDA.
    Valor por parcela = valor_total / parcelas (quando houver).
    """
    cursor.execute(
        """
        SELECT
            d.id,
            COALESCE(d.descricao,''),
            COALESCE(d.categoria,''),
            COALESCE(d.forma_pagamento,''),
            COALESCE(d.valor,0),
            COALESCE(d.parcelas,1),
            p.parcela_num,
            p.data_debito
        FROM parcelas_agendadas p
        JOIN dados d ON d.id = p.lancamento_id
        WHERE d.empresa=?
          AND d.tipo='saida'
          AND date(p.data_debito)=date(?)
          AND COALESCE(p.paga,0)=0
        ORDER BY p.data_debito ASC, d.id ASC, p.parcela_num ASC
        """,
        (empresa, data_debito.isoformat())
    )
    rows = []
    for (lanc_id, desc, cat, forma, valor_total, parcelas, parcela_num, dtdeb) in cursor.fetchall():
        try:
            parcelas_i = int(parcelas or 1)
            if parcelas_i <= 0:
                parcelas_i = 1
        except Exception:
            parcelas_i = 1

        try:
            vtot = float(valor_total or 0)
        except Exception:
            vtot = 0.0

        vparc = (vtot / parcelas_i) if parcelas_i else vtot

        rows.append({
            "Data": str(dtdeb),
            "Parcela": f"{int(parcela_num)}/{parcelas_i}",
            "Valor": float(vparc),
            "Descrição": str(desc or ""),
            "Categoria": str(cat or ""),
            "Forma": str(forma or ""),
            "LancamentoID": int(lanc_id),
        })

    df = pd.DataFrame(rows, columns=["Data", "Parcela", "Valor", "Descrição", "Categoria", "Forma", "LancamentoID"])
    return df



# =========================
# CAIXA (PAGOS) — HELPERS PARA USAR NO RELATÓRIO DIÁRIO
# =========================
def _caixa_linhas_pagas_no_dia(empresa: str, data_ref: date, tipo: Optional[str] = None, conta: Optional[str] = None):
    """Retorna linhas de 'pagamentos' do dia, no MESMO critério da página Caixa.

    Regras (igual ao Caixa):
    1) Parcelas pagas: parcelas_agendadas.paga=1 e data do pagamento = COALESCE(data_quitacao, data_debito)
    2) Lançamentos pagos sem parcelas: dados.situacao='Pago' e parcelas <= 1, usando data_operacao como data do pagamento.

    Campos retornados:
    - valor_item (float)
    - descricao (str)
    - categoria (str)
    - conta_bancaria (str)
    """
    iso = data_ref.isoformat()
    rows: List[Tuple[float, str, str, str]] = []

    # 1) Parcelas pagas no dia
    wh = [
        "d.empresa=?",
        "COALESCE(p.paga,0)=1",
        "date(COALESCE(p.data_quitacao, p.data_debito))=date(?)",
    ]
    params: List = [empresa, iso]

    if tipo in ("entrada", "saida"):
        wh.append("d.tipo=?")
        params.append(tipo)

    if conta:
        wh.append("COALESCE(d.conta_bancaria,'')=?")
        params.append(conta)

    where = " AND ".join(wh)
    cursor.execute(
        f"""
        SELECT
            COALESCE(d.valor,0) AS valor_total,
            COALESCE(d.parcelas,1) AS parcelas,
            COALESCE(d.descricao,'') AS descricao,
            COALESCE(d.categoria,'') AS categoria,
            COALESCE(d.conta_bancaria,'') AS conta_bancaria
        FROM parcelas_agendadas p
        JOIN dados d ON d.id = p.lancamento_id
        WHERE {where}
        ORDER BY d.id ASC, p.parcela_num ASC
        """,
        tuple(params)
    )
    for (valor_total, nparc, desc, cat, conta_b) in cursor.fetchall():
        try:
            n = int(nparc or 1)
            if n <= 0:
                n = 1
        except Exception:
            n = 1
        try:
            vtot = float(valor_total or 0)
        except Exception:
            vtot = 0.0
        vitem = vtot / n if n else vtot
        rows.append((float(vitem), str(desc or ""), str(cat or ""), str(conta_b or "")))

    # 2) Lançamentos pagos sem parcelas no dia
    wh2 = [
        "empresa=?",
        "situacao='Pago'",
        "date(data_operacao)=date(?)",
        "COALESCE(parcelas,0) <= 1",
    ]
    params2: List = [empresa, iso]

    if tipo in ("entrada", "saida"):
        wh2.append("tipo=?")
        params2.append(tipo)

    if conta:
        wh2.append("COALESCE(conta_bancaria,'')=?")
        params2.append(conta)

    where2 = " AND ".join(wh2)
    cursor.execute(
        f"""
        SELECT
            COALESCE(valor,0) AS valor_item,
            COALESCE(descricao,'') AS descricao,
            COALESCE(categoria,'') AS categoria,
            COALESCE(conta_bancaria,'') AS conta_bancaria
        FROM dados
        WHERE {where2}
        ORDER BY id ASC
        """,
        tuple(params2)
    )
    for (vitem, desc, cat, conta_b) in cursor.fetchall():
        try:
            v = float(vitem or 0)
        except Exception:
            v = 0.0
        rows.append((float(v), str(desc or ""), str(cat or ""), str(conta_b or "")))

    return rows


def caixa_mov_list_dia(empresa: str, tipo: str, data_ref: date) -> List[Tuple[float, str, str]]:
    """Lista (valor, descricao, categoria) do dia, puxando do CAIXA (pagos) e não do Lançamentos."""
    linhas = _caixa_linhas_pagas_no_dia(empresa, data_ref, tipo=tipo, conta=None)
    return [(v, d, c) for (v, d, c, _conta) in linhas]


def caixa_sum_dia(empresa: str, tipo: str, data_ref: date, conta: Optional[str] = None) -> float:
    """Soma do dia para um tipo (entrada/saida) usando a regra do CAIXA (pagos)."""
    linhas = _caixa_linhas_pagas_no_dia(empresa, data_ref, tipo=tipo, conta=conta)
    return float(sum([v for (v, _d, _c, _cb) in linhas]))



def proximo_dia_util(d: date) -> date:
    """Retorna o próximo dia útil.
    Regra pedida: normalmente D+1; se for sexta, pula para segunda.
    (Também pula sábado/domingo automaticamente.)
    """
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:  # 5=sábado, 6=domingo
        nxt = nxt + timedelta(days=1)
    return nxt


def previsao_despesas_proximo_dia(empresa: str, data_ref: date, conta: Optional[str] = None) -> pd.DataFrame:
    """Monta uma 'planilha' com previsão de despesas para o próximo dia útil.

    Inclui:
    - Parcelas agendadas (parcelas_agendadas) de lançamentos de SAÍDA ainda não pagas
      com vencimento no próximo dia útil;
    - Lançamentos futuros (dados.tipo='saida') com data_operacao exatamente no próximo dia útil
      e situação Em aberto (quando a pessoa já lançou a despesa para frente).
    """
    dt_prev = proximo_dia_util(data_ref)
    iso_prev = dt_prev.isoformat()

    rows: List[list] = []

    # 1) Parcelas agendadas (não pagas)
    sql = """
        SELECT
            d.id AS lanc_id,
            p.parcela_num,
            p.data_debito,
            d.descricao,
            d.categoria,
            d.conta_bancaria,
            d.valor,
            COALESCE(d.parcelas, 1) AS parcelas,
            d.forma_pagamento,
            d.situacao
        FROM parcelas_agendadas p
        JOIN dados d ON d.id = p.lancamento_id
        WHERE d.empresa=?
          AND d.tipo='saida'
          AND date(p.data_debito)=date(?)
          AND COALESCE(p.paga,0)=0
    """
    params = [empresa, iso_prev]
    if conta:
        sql += " AND d.conta_bancaria=? "
        params.append(conta)

    cursor.execute(sql, tuple(params))
    for (lanc_id, parcela_num, data_debito, desc, cat, conta_b, valor_total, nparc, forma, sit) in cursor.fetchall():
        try:
            nparc_i = int(nparc or 1)
        except Exception:
            nparc_i = 1
        valor_prev = float(valor_total or 0) / (nparc_i if nparc_i > 0 else 1)
        rows.append([
            iso_prev,
            "Parcela agendada",
            int(lanc_id),
            int(parcela_num),
            desc or "",
            cat or "",
            conta_b or "",
            float(valor_prev),
            forma or "",
            sit or "Em aberto",
        ])

    # 2) Lançamentos futuros (saída) já cadastrados para o próximo dia útil
    sql2 = """
        SELECT
            id, data_operacao, descricao, categoria, conta_bancaria, valor, forma_pagamento, situacao
        FROM dados
        WHERE empresa=?
          AND tipo='saida'
          AND date(data_operacao)=date(?)
          AND COALESCE(situacao,'Em aberto')='Em aberto'
    """
    params2 = [empresa, iso_prev]
    if conta:
        sql2 += " AND conta_bancaria=? "
        params2.append(conta)

    cursor.execute(sql2, tuple(params2))
    for (lanc_id, data_op, desc, cat, conta_b, valor, forma, sit) in cursor.fetchall():
        rows.append([
            iso_prev,
            "Lançamento futuro",
            int(lanc_id),
            "",  # parcela
            desc or "",
            cat or "",
            conta_b or "",
            float(valor or 0),
            forma or "",
            sit or "Em aberto",
        ])

    df = pd.DataFrame(rows, columns=[
        "Data (próx. dia útil)",
        "Origem",
        "ID Lançamento",
        "Parcela",
        "Descrição",
        "Categoria",
        "Conta",
        "Valor Previsto",
        "Forma",
        "Situação",
    ])
    if not df.empty:
        df = df.sort_values(by=["Conta", "Origem", "ID Lançamento"]).reset_index(drop=True)
    return df


def excel_multi_sheets_bytes(sheets: dict) -> bytes:
    """Gera um Excel com múltiplas abas.
    sheets = { 'NomeDaAba': dataframe, ... }
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, index=False, sheet_name=str(name)[:31])
    return output.getvalue()

def criar_ou_recriar_parcelas_agendadas(lancamento_id: int, primeiro: date, parcelas: int, situacao: str):
    cursor.execute("DELETE FROM parcelas_agendadas WHERE lancamento_id=?", (int(lancamento_id),))
    datas = gerar_datas_debito(primeiro, int(parcelas))
    paga_default = 1 if (situacao == "Pago") else 0
    for i, ddeb in enumerate(datas, start=1):
        quit_iso = ddeb.isoformat() if int(paga_default) == 1 else None
        cursor.execute(
            """
            INSERT OR REPLACE INTO parcelas_agendadas (lancamento_id, parcela_num, data_debito, paga, data_quitacao)
            VALUES (?, ?, ?, ?, ?)
            """,
            (int(lancamento_id), int(i), ddeb.isoformat(), int(paga_default), quit_iso)
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
        quit_iso = iso if paga == 1 else None
        cursor.execute("""
            INSERT OR REPLACE INTO parcelas_agendadas (lancamento_id, parcela_num, data_debito, paga, data_quitacao)
            VALUES (?, ?, ?, ?, ?)
        """, (int(lancamento_id), p, iso, paga, quit_iso))
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


def get_trava_mes_apos_fim(empresa: str) -> bool:
    """Se True, bloqueia lançamentos/edições em meses anteriores ao mês atual (mês já encerrado)."""
    try:
        cursor.execute(
            "SELECT COALESCE(trava_mes_apos_fim,1) FROM configuracoes_empresa WHERE empresa=?",
            (empresa,)
        )
        r = cursor.fetchone()
        if r is None:
            cursor.execute(
                "INSERT OR IGNORE INTO configuracoes_empresa (empresa, trava_mes_apos_fim) VALUES (?,1)",
                (empresa,)
            )
            conn.commit()
            return True
        return bool(int(r[0]))
    except Exception:
        return True


def set_trava_mes_apos_fim(empresa: str, valor: bool, usuario: str):
    v = 1 if valor else 0
    cursor.execute(
        "INSERT INTO configuracoes_empresa (empresa, trava_mes_apos_fim, atualizado_por) VALUES (?,?,?) "
        "ON CONFLICT(empresa) DO UPDATE SET trava_mes_apos_fim=excluded.trava_mes_apos_fim, "
        "atualizado_em=datetime('now'), atualizado_por=excluded.atualizado_por",
        (empresa, v, usuario)
    )
    conn.commit()

def is_mes_fechado(empresa: str, ano: int, mes: int) -> bool:
    """Retorna True se o mês estiver fechado manualmente OU (opcional) se já tiver encerrado."""
    # 1) Fechamento automático: mês já acabou
    try:
        if get_trava_mes_apos_fim(empresa):
            hoje = date.today()
            if (int(ano), int(mes)) < (int(hoje.year), int(hoje.month)):
                return True
    except Exception:
        # se der erro no auto, não derruba o app; segue para o manual
        pass

    # 2) Fechamento manual (tabela meses_fechados)
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



def checar_pronto_pdf_todas_empresas(data_ref: date):
    """Valida se o PDF (todas as empresas) pode ser gerado.

    Regra: Para o dia do relatório, TODA conta "relevante" precisa:
    - ter saldo_inicio e saldo_fim preenchidos em extratos_diarios
    - e estar com o dia FECHADO em dias_fechados

    Conta "relevante" = conta que teve movimento no dia OU que já tem extrato lançado no dia.
    """
    pendencias: List[str] = []

    for emp in EMPRESAS:
        cursor.execute(
            """
            SELECT DISTINCT conta_bancaria
            FROM dados
            WHERE empresa=? AND date(data_operacao)=date(?)
              AND conta_bancaria IS NOT NULL AND conta_bancaria <> ''
            """,
            (emp, data_ref.isoformat())
        )
        contas_mov = {r[0] for r in cursor.fetchall()}

        cursor.execute(
            """
            SELECT DISTINCT conta_bancaria
            FROM extratos_diarios
            WHERE empresa=? AND date(data_ref)=date(?)
              AND conta_bancaria IS NOT NULL AND conta_bancaria <> ''
            """,
            (emp, data_ref.isoformat())
        )
        contas_ext = {r[0] for r in cursor.fetchall()}

        contas_relevantes = sorted(contas_mov.union(contas_ext))
        if not contas_relevantes:
            continue

        for conta in contas_relevantes:
            cursor.execute(
                """
                SELECT saldo_inicio, saldo_fim
                FROM extratos_diarios
                WHERE empresa=? AND conta_bancaria=? AND date(data_ref)=date(?)
                LIMIT 1
                """,
                (emp, conta, data_ref.isoformat())
            )
            row = cursor.fetchone()

            if (not row) or (row[0] is None) or (row[1] is None):
                pendencias.append(f"{emp} • {conta}: falta saldo inicial/final")
                continue

            if not is_dia_fechado(emp, conta, data_ref.isoformat()):
                pendencias.append(f"{emp} • {conta}: dia NÃO está fechado")

    ok = (len(pendencias) == 0)
    return ok, pendencias



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
            "Operações",
            "Lançamentos",
            "Caixa",
            "Agenda",
            "Saldo Inicial/Final",
            "Relatório Diário Geral",
            "Configurações"
        ]
    else:
        # 🔒 Usuário comum NÃO vê Configurações
        secoes = [
            "Operações",
            "Lançamentos",
            "Caixa",
            "Agenda",
            "Saldo Inicial/Final",
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
        pagina = "Operações"
    elif secao == "Lançamentos":
        pagina = "Lançamentos"
    elif secao == "Caixa":
        pagina = "Caixa"
    elif secao == "Agenda":
        pagina = "Contas a Pagar / Receber"
    elif secao == "Saldo Inicial/Final":
        pagina = "Saldo Inicial/Final"
    elif secao == "Relatório Diário Geral":
        pagina = "Relatório Diário Geral"
    elif secao == "Configurações":
        opcoes = ["Alterar Minha Senha"]
        if st.session_state.get("nivel") == "admin":
            opcoes += ["Trava automática de mês", "Gerenciar Categorias", "Gerenciar Contas Bancárias", "Gerenciar Usuários"]
        pagina = st.sidebar.selectbox("Opções", opcoes)
    else:
        pagina = "Operações"

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

def page_operacoes(empresa: str):
    render_header("Operações", empresa)
    st.subheader("Lançamentos (Entradas e Despesas)")

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
                if st.button("Fechar mês", disabled=(int(fechado) == 1), key=f"op_fechar_mes_{empresa}"):
                    fechar_mes(empresa, int(ano_sel), int(mes_sel), st.session_state.get("usuario", ""))
                    st.success("Mês fechado! Não será possível alterar lançamentos desse mês.")
                    st.rerun()
            with cbtn2:
                if st.button("Reabrir mês", disabled=(int(fechado) == 0), key=f"op_reabrir_mes_{empresa}"):
                    reabrir_mes(empresa, int(ano_sel), int(mes_sel))
                    st.success("Mês reaberto!")
                    st.rerun()

    # =========================
    # SUB-TELAS (HOME / CRIAR / EDITAR / EXCLUIR)
    # =========================
    view_key = f"operacoes_view_{empresa}"
    if view_key not in st.session_state:
        st.session_state[view_key] = "home"

    def goto(v: str):
        st.session_state[view_key] = v
        st.rerun()

    def btn_voltar():
        if st.button("⬅️ Voltar", key=f"op_voltar_{empresa}_{st.session_state[view_key]}"):
            goto("home")

    # -------- HOME: 3 botões --------
    if st.session_state[view_key] == "home":
        st.markdown("### O que você deseja fazer?")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("➕ Criar lançamento", use_container_width=True, key=f"op_btn_criar_{empresa}"):
                goto("criar")
        with c2:
            if st.button("✏️ Editar lançamento", use_container_width=True, key=f"op_btn_editar_{empresa}"):
                goto("editar")
        with c3:
            if st.button("🗑️ Excluir lançamentos", use_container_width=True, key=f"op_btn_excluir_{empresa}"):
                goto("excluir")

        st.info("Dica: depois que você concluir uma ação, o sistema volta automaticamente para esta tela.")
        return

    # =========================
    # TELA: CRIAR LANÇAMENTO
    # =========================
    if st.session_state[view_key] == "criar":
        btn_voltar()

        secao = st.radio("Selecione", ["Despesas", "Entradas"], horizontal=True, key=f"op_secao_{empresa}")
        tipo = "saida" if secao == "Despesas" else "entrada"

        st.markdown("### Criar novo lançamento")

        # Data default fica dentro do mês selecionado (pra não “sumir” depois)
        data_default = hoje
        if data_default.year != int(ano_sel) or data_default.month != int(mes_sel):
            data_default = date(int(ano_sel), int(mes_sel), 1)
        data_op = st.date_input("Data da Operação", value=data_default, key=f"op_data_{empresa}")

        categorias = obter_categorias_banco(tipo=tipo)

        # ✅ Conta bancária removida do formulário
        conta_bancaria = None

        if categorias:
            categoria = st.selectbox("Categoria", categorias, key=f"op_cat_{empresa}")
        else:
            st.warning("Nenhuma categoria cadastrada. (Admin > Configurações)")
            categoria = st.text_input("Categoria (temporário)", key=f"op_cat_tmp_{empresa}")

        descricao = st.text_input("Descrição da Operação", key=f"op_desc_{empresa}")
        valor = st.number_input("Valor", step=0.01, min_value=0.0, key=f"op_val_{empresa}")

        colF, colS = st.columns(2)
        with colF:
            forma_pagamento = st.selectbox("Forma de Pagamento", FORMAS_PAGAMENTO, key=f"op_forma_{empresa}")
        with colS:
            situacao = st.selectbox("Situação", SITUACOES, key=f"op_sit_{empresa}")

        parcelas = None
        primeiro_debito = None
        edited_parc = None

        if forma_pagamento in ("Cheque", "Cartão", "Boleto"):
            colP, colD = st.columns(2)
            with colP:
                parcelas = st.number_input("Quantidade de parcelas", min_value=1, step=1, value=1, key=f"op_parc_{empresa}")
            with colD:
                primeiro_debito = st.date_input("Data do 1º débito (sugestão)", value=data_op, key=f"op_primeiro_{empresa}")

            st.markdown("#### Datas das parcelas (editar manualmente)")
            datas_base = gerar_datas_debito(primeiro_debito, int(parcelas))
            df_parc_novo = pd.DataFrame({
                "Parcela": list(range(1, int(parcelas) + 1)),
                "Data": datas_base,
                "Paga": [True if situacao == "Pago" else False] * int(parcelas),
            })

            editor_key = f"novas_parcelas_{empresa}_{forma_pagamento}_{int(parcelas)}_{situacao}"
            edited_parc = st.data_editor(
                df_parc_novo,
                use_container_width=True,
                num_rows="fixed",
                disabled=["Parcela"],
                key=editor_key
            )

        if st.button("Salvar lançamento", disabled=is_mes_fechado(empresa, int(data_op.year), int(data_op.month)), key=f"op_salvar_{empresa}"):
            # 🔒 Bloqueio por mês fechado (pela data do lançamento)
            if is_mes_fechado(empresa, int(data_op.year), int(data_op.month)):
                st.error(f"Este mês está FECHADO ({data_op.month:02d}/{data_op.year}). Reabra o mês para lançar/alterar.")
                st.stop()

            # (Bloqueio de dia por conta fica inativo porque conta_bancaria está removida)
            if not descricao:
                st.warning("Preencha a descrição.")
            elif not categoria:
                st.warning("Preencha a categoria.")
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

                        primeiro_debito_db = min(datas_list).isoformat() if datas_list else None
                except Exception as e:
                    st.error(f"Erro nas parcelas: {e}")
                    st.stop()

                # ====== INSERIR LANÇAMENTO ======
                criado_em_iso = date.today().isoformat()
                cursor.execute(
                    """
                    INSERT INTO dados (
                        empresa, tipo, numero_item, data_operacao, descricao,
                        categoria, conta_bancaria, valor,
                        forma_pagamento, parcelas, primeiro_debito, situacao, criado_em
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
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
                        situacao,
                        criado_em_iso
                    )
                )
                conn.commit()

                # ====== SALVAR PARCELAS (manual) ======
                lanc_id = cursor.lastrowid
                if forma_pagamento in ("Cheque", "Cartão", "Boleto") and rows_to_save:
                    salvar_parcelas_agendadas(int(lanc_id), rows_to_save)
                    recomputar_situacao_lancamento(int(lanc_id))

                st.success(f"{secao} salva com sucesso!")
                # volta para a home
                st.session_state[view_key] = "home"
                st.rerun()

        return

    # =========================
    # TELA: EDITAR LANÇAMENTO
    # =========================
    if st.session_state[view_key] == "editar":
        btn_voltar()

        st.markdown("### Editar lançamento")

        edit_id_key = f"op_edit_id_{empresa}"
        if edit_id_key not in st.session_state:
            st.session_state[edit_id_key] = 0

        col_id, col_btn = st.columns([2, 1])
        with col_id:
            edit_id = st.number_input("ID do lançamento", min_value=0, step=1, key=edit_id_key)
        with col_btn:
            carregar = st.button("Carregar", use_container_width=True, key=f"op_btn_carregar_{empresa}")

        if not (carregar or int(edit_id) > 0):
            st.info("Informe o ID e clique em **Carregar**.")
            return

        cursor.execute(
            """
            SELECT id, tipo, data_operacao, descricao, categoria, conta_bancaria, valor, forma_pagamento, parcelas, primeiro_debito, situacao
            FROM dados
            WHERE id=? AND empresa=?
            """,
            (int(edit_id), empresa)
        )
        row = cursor.fetchone()
        if not row:
            st.warning("ID não encontrado nesta empresa.")
            return

        (
            _id, tipo_db, data_iso, desc_db, cat_db, conta_db,
            valor_db, forma_db, parcelas_db, primeiro_db, sit_db
        ) = row

        # 🔒 Não permite editar lançamento de mês fechado (pela data atual do lançamento)
        try:
            dtmp = date.fromisoformat(str(data_iso))
            if is_mes_fechado(empresa, int(dtmp.year), int(dtmp.month)):
                st.error(f"Não posso editar: mês FECHADO ({dtmp.month:02d}/{dtmp.year}). Reabra o mês para editar.")
                return
        except Exception:
            pass

        with st.form(key=f"form_editar_{empresa}_{int(_id)}"):
            colA, colB = st.columns(2)
            with colA:
                tipo_ui = st.selectbox("Tipo", ["entrada", "saida"], index=0 if (tipo_db or "entrada") == "entrada" else 1)
                data_op = st.date_input("Data da Operação", value=date.fromisoformat(str(data_iso)))
                situacao = st.selectbox("Situação", SITUACOES, index=SITUACOES.index(sit_db) if sit_db in SITUACOES else 0)
            with colB:
                categorias = obter_categorias_banco(tipo=tipo_ui)
                if categorias:
                    categoria = st.selectbox("Categoria", categorias, index=categorias.index(cat_db) if cat_db in categorias else 0)
                else:
                    categoria = st.text_input("Categoria", value=str(cat_db or ""))

                descricao = st.text_input("Descrição da Operação", value=str(desc_db or ""))
                valor = st.number_input("Valor", step=0.01, min_value=0.0, value=float(valor_db or 0.0))

            forma_pagamento = st.selectbox(
                "Forma de Pagamento",
                FORMAS_PAGAMENTO,
                index=FORMAS_PAGAMENTO.index(forma_db) if forma_db in FORMAS_PAGAMENTO else 0
            )

            # Conta fica interna (campo existe no banco, mas no app está removido)
            conta_bancaria = conta_db if (conta_db not in (None, "")) else None

            parcelas_int = None
            primeiro_debito_db = None
            rows_to_save = None

            if forma_pagamento in ("Cheque", "Cartão", "Boleto"):
                st.markdown("#### Parcelas")

                # carrega parcelas existentes (se houver)
                parcelas_exist = obter_parcelas_agendadas(int(_id))
                if parcelas_exist:
                    df_parc = pd.DataFrame([{
                        "Parcela": int(pn),
                        "Data": date.fromisoformat(str(dt)),
                        "Paga": bool(int(pg or 0)),
                    } for (pn, dt, pg) in parcelas_exist])
                else:
                    # fallback: gera por primeiro_debito/parcelas do lançamento
                    try:
                        parcelas_fallback = int(parcelas_db or 1)
                        if parcelas_fallback <= 0:
                            parcelas_fallback = 1
                    except Exception:
                        parcelas_fallback = 1
                    try:
                        first_dt = date.fromisoformat(str(primeiro_db)) if primeiro_db else date.fromisoformat(str(data_iso))
                    except Exception:
                        first_dt = date.fromisoformat(str(data_iso))
                    datas_base = gerar_datas_debito(first_dt, parcelas_fallback)
                    df_parc = pd.DataFrame({
                        "Parcela": list(range(1, parcelas_fallback + 1)),
                        "Data": datas_base,
                        "Paga": [True if str(sit_db or "") == "Pago" else False] * parcelas_fallback
                    })

                # permite alterar quantidade de parcelas (regenera a tabela)
                colp1, colp2 = st.columns([1, 2])
                with colp1:
                    parcelas_novas = st.number_input("Qtd. parcelas", min_value=1, step=1, value=int(len(df_parc)), key=f"op_edit_qtd_{empresa}_{int(_id)}")
                with colp2:
                    first_date = st.date_input("Data base (1ª parcela)", value=df_parc["Data"].min() if not df_parc.empty else date.today(), key=f"op_edit_base_{empresa}_{int(_id)}")

                if int(parcelas_novas) != int(len(df_parc)):
                    datas_base2 = gerar_datas_debito(first_date, int(parcelas_novas))
                    df_parc = pd.DataFrame({
                        "Parcela": list(range(1, int(parcelas_novas) + 1)),
                        "Data": datas_base2,
                        "Paga": [False] * int(parcelas_novas)
                    })

                editor_key = f"edit_parcelas_{empresa}_{int(_id)}_{int(parcelas_novas)}_{forma_pagamento}"
                edited_parc = st.data_editor(
                    df_parc,
                    use_container_width=True,
                    num_rows="fixed",
                    disabled=["Parcela"],
                    key=editor_key
                )

                # prepara para salvar
                try:
                    parcelas_int = int(parcelas_novas)
                    datas_list = []
                    rows_to_save = []
                    for _, rr in edited_parc.iterrows():
                        d = rr.get("Data")
                        if not isinstance(d, date):
                            d = pd.to_datetime(d).date()
                        datas_list.append(d)
                        rows_to_save.append({
                            "Parcela": int(rr.get("Parcela")),
                            "Data": d.isoformat(),
                            "Paga": bool(rr.get("Paga")),
                        })
                    primeiro_debito_db = min(datas_list).isoformat() if datas_list else None
                except Exception as e:
                    st.error(f"Erro nas parcelas: {e}")
                    st.stop()

            salvar = st.form_submit_button("Salvar alterações")

        if salvar:
            # 🔒 Bloqueio por mês fechado (pela NOVA data)
            if is_mes_fechado(empresa, int(data_op.year), int(data_op.month)):
                st.error(f"Este mês está FECHADO ({data_op.month:02d}/{data_op.year}). Reabra o mês para editar.")
                st.stop()

            if not descricao:
                st.warning("Preencha a descrição.")
                st.stop()
            if not categoria:
                st.warning("Preencha a categoria.")
                st.stop()
            if float(valor or 0) <= 0:
                st.warning("Informe um valor maior que zero.")
                st.stop()

            cursor.execute(
                """
                UPDATE dados
                SET tipo=?, data_operacao=?, descricao=?, categoria=?, valor=?, forma_pagamento=?, parcelas=?, primeiro_debito=?, situacao=?
                WHERE id=? AND empresa=?
                """,
                (
                    tipo_ui,
                    data_op.isoformat(),
                    descricao,
                    categoria,
                    float(valor),
                    forma_pagamento,
                    parcelas_int,
                    primeiro_debito_db,
                    situacao,
                    int(_id),
                    empresa
                )
            )
            conn.commit()

            # atualiza parcelas (se necessário)
            if forma_pagamento in ("Cheque", "Cartão", "Boleto"):
                cursor.execute("DELETE FROM parcelas_agendadas WHERE lancamento_id=?", (int(_id),))
                conn.commit()
                if rows_to_save:
                    salvar_parcelas_agendadas(int(_id), rows_to_save)
                    recomputar_situacao_lancamento(int(_id))
            else:
                # se mudou para forma sem parcelas, limpa parcelas antigas
                cursor.execute("DELETE FROM parcelas_agendadas WHERE lancamento_id=?", (int(_id),))
                conn.commit()

            st.success("Lançamento atualizado com sucesso!")
            st.session_state[view_key] = "home"
            st.rerun()

        return

    # =========================
    # TELA: EXCLUIR LANÇAMENTO
    # =========================
    if st.session_state[view_key] == "excluir":
        btn_voltar()

        st.markdown("### Excluir lançamento")
        st.caption("Atenção: essa ação remove o lançamento e todas as parcelas vinculadas (se existirem).")

        id_excluir = st.number_input("Digite o ID para excluir", min_value=0, step=1, key=f"op_del_id_{empresa}")
        if st.button("Excluir agora", key=f"op_btn_excluir_agora_{empresa}"):
            if id_excluir <= 0:
                st.warning("Informe um ID válido.")
                return

            # 🔒 Não permite excluir lançamento de mês fechado
            cursor.execute("SELECT data_operacao, conta_bancaria FROM dados WHERE id=? AND empresa=?", (int(id_excluir), empresa))
            rr = cursor.fetchone()
            if not rr:
                st.warning("ID não encontrado nesta empresa.")
                return

            try:
                dtmp = date.fromisoformat(str(rr[0]))
                if is_mes_fechado(empresa, int(dtmp.year), int(dtmp.month)):
                    st.error(f"Não posso excluir: mês FECHADO ({dtmp.month:02d}/{dtmp.year}).")
                    return
                # Bloqueio por dia fechado (se existir conta no lançamento — legado)
                try:
                    conta_tmp = str(rr[1] or "")
                    if conta_tmp and is_dia_fechado(empresa, conta_tmp, dtmp.isoformat()):
                        st.error(f"Não posso excluir: dia FECHADO para a conta '{conta_tmp}' ({dtmp.strftime('%d/%m/%Y')}).")
                        return
                except Exception:
                    pass
            except Exception:
                pass

            deletar_lancamento_e_parcelas(int(id_excluir), empresa)
            st.success("Lançamento excluído.")
            st.session_state[view_key] = "home"
            st.rerun()

        return


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
        pass
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
        pass
    try:
        pdf_res = df_to_pdf_bytes(
            df_resumo_show,
            title=f"Resumo por Conta — {empresa} — {dt_ini.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"
        )
        st.download_button("Baixar PDF (Resumo)", data=pdf_res, file_name="resumo_por_conta.pdf", mime="application/pdf")
    except Exception:
        st.info("PDF não disponível (reportlab).")






def page_lancamentos(empresa: str):
    """Página nova: lista TODOS os lançamentos do mês (entradas e saídas)."""
    render_header("Lançamentos", empresa)
    st.subheader("Tudo lançado no mês (Entradas + Despesas)")

    meses_pt = [
        "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
        "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"
    ]
    hoje = date.today()

    # chaves por empresa para manter seleção
    key_ano = f"lancmes_ano_{empresa}"
    key_mes = f"lancmes_mes_{empresa}"
    if key_ano not in st.session_state:
        st.session_state[key_ano] = hoje.year
    if key_mes not in st.session_state:
        st.session_state[key_mes] = hoje.month

    c1, c2, c3 = st.columns([2, 1, 3])
    with c1:
        mes_nome = st.selectbox(
            "Mês",
            meses_pt,
            index=int(st.session_state[key_mes]) - 1,
            key=f"{key_mes}_ui"
        )
        mes_sel = meses_pt.index(mes_nome) + 1
        st.session_state[key_mes] = mes_sel
    with c2:
        ano_sel = st.number_input(
            "Ano",
            min_value=2000,
            max_value=2100,
            step=1,
            value=int(st.session_state[key_ano]),
            key=f"{key_ano}_ui"
        )
        st.session_state[key_ano] = int(ano_sel)
    with c3:
        st.caption("Dica: use esta tela para conferir tudo que foi lançado no mês, e exportar.")

    # filtros extras
    colf1, colf2 = st.columns([2, 2])
    with colf1:
        tipo_filtro = st.selectbox("Tipo", ["(Todos)", "Entrada", "Saída"], index=0, key=f"lancmes_tipo_{empresa}")
    with colf2:
        situacao_filtro = st.selectbox("Situação", ["(Todas)", "Pago", "Em aberto"], index=0, key=f"lancmes_sit_{empresa}")

    # ✅ Regra: aqui deve mostrar apenas os LANÇAMENTOS DO MÊS em que foram CRIADOS (data do lançamento),
    # e NÃO os lançamentos de outros meses que apenas têm parcelas pagas/vencendo agora.
    # Por isso o filtro é por data_operacao (data do lançamento), e não por parcelas/data_quitacao.
    wheres = ["empresa=?",
              "strftime('%m', date(data_operacao))=?",
              "strftime('%Y', date(data_operacao))=?"]
    params = [empresa, f"{int(mes_sel):02d}", f"{int(ano_sel):04d}"]
    # 🚫 Remove registros "movimentação de parcela" antigos (ex.: "2/8", "3/4") que por engano ficam na tabela dados.
    # Esses registros não são lançamentos criados no mês; eles devem aparecer só no Caixa.
    wheres.append("NOT (COALESCE(parcelas,0) <= 1 AND TRIM(descricao) GLOB '* [0-9]/[0-9]*')")


    if tipo_filtro != "(Todos)":
        wheres.append("tipo=?")
        params.append("entrada" if tipo_filtro == "Entrada" else "saida")

    if situacao_filtro != "(Todas)":
        wheres.append("situacao=?")
        params.append(situacao_filtro)

    sql = f"""
        SELECT
            id,
            tipo,
            data_operacao,
            descricao,
            categoria,
            valor,
            forma_pagamento,
            parcelas,
            primeiro_debito,
            situacao,
            criado_em
        FROM dados
        WHERE {' AND '.join(wheres)}
        ORDER BY date(data_operacao) ASC, id ASC
    """

    cursor.execute(sql, tuple(params))
    rows = cursor.fetchall()

    if not rows:
        st.info("Nenhum lançamento encontrado para o filtro selecionado.")
        return

    df = pd.DataFrame(rows, columns=[
        "ID", "Tipo", "Data", "Descrição", "Categoria", "Valor",
        "Forma", "Parcelas", "1º Débito", "Situação", "Criado em"
    ])

    # melhorias visuais
    df["Tipo"] = df["Tipo"].apply(lambda x: "Entrada" if str(x) == "entrada" else "Saída")
    df = format_df_dates(df, ["Data", "1º Débito", "Criado em"])

    st.markdown("### Lançamentos do mês")

    df_show = df.copy()
    # formata valor em BR
    if "Valor" in df_show.columns:
        df_show["Valor"] = df_show["Valor"].apply(br_money)

    st.dataframe(df_show, use_container_width=True, hide_index=True)
    # export
    st.download_button(
        "Baixar PDF (Lançamentos do mês)",
        data=df_to_pdf_bytes(df_show, title=f"Lançamentos do mês — {empresa} — {int(mes_sel):02d}/{int(ano_sel)}"),
        file_name=f"lancamentos_{empresa}_{int(ano_sel)}_{int(mes_sel):02d}.pdf".replace("/", "-"),
        mime="application/pdf",
        use_container_width=True,
        )

    st.caption("Obs.: esta tela mostra apenas os lançamentos do mês pela coluna Data (data_operacao). Parcelas pagas/vencendo em outros meses aparecem no Caixa, não aqui.")




def page_caixa(empresa: str):
    """Página: Caixa — mostra tudo que foi PAGO no mês (inclui parcelas pagas no mês)."""
    render_header("Caixa", empresa)
    st.subheader("Caixa — lançamentos pagos no mês")

    meses_pt = [
        "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
        "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"
    ]
    hoje = date.today()

    key_ano = f"caixa_ano_{empresa}"
    key_mes = f"caixa_mes_{empresa}"
    if key_ano not in st.session_state:
        st.session_state[key_ano] = hoje.year
    if key_mes not in st.session_state:
        st.session_state[key_mes] = hoje.month

    c1, c2, c3 = st.columns([2, 1, 2])
    with c1:
        mes_nome = st.selectbox(
            "Mês",
            meses_pt,
            index=int(st.session_state[key_mes]) - 1,
            key=f"{key_mes}_ui"
        )
        mes_sel = meses_pt.index(mes_nome) + 1
        st.session_state[key_mes] = mes_sel
    with c2:
        ano_sel = st.number_input(
            "Ano",
            min_value=2000,
            max_value=2100,
            step=1,
            value=int(st.session_state[key_ano]),
            key=f"{key_ano}_ui"
        )
        st.session_state[key_ano] = int(ano_sel)
    with c3:
        tipo_filtro = st.selectbox("Tipo", ["(Todos)", "Entrada", "Saída"], index=0, key=f"caixa_tipo_{empresa}")

    # filtros opcionais (categoria)
    colf1 = st.columns(1)[0]
    with colf1:
        cursor.execute(
            """
            SELECT DISTINCT categoria
            FROM dados
            WHERE empresa=? AND categoria IS NOT NULL AND categoria<>''
            ORDER BY categoria
            """,
            (empresa,)
        )
        cats = [r[0] for r in cursor.fetchall()]
        cat_filtro = st.selectbox("Categoria", ["(Todas)"] + cats, key=f"caixa_cat_{empresa}")

    # =========================
    # 1) Parcelas pagas no mês (usa data_quitacao se existir; senão data_debito)
    # =========================
    wh_parc = [
        "d.empresa=?",
        "COALESCE(p.paga,0)=1",
        "strftime('%m', date(COALESCE(p.data_quitacao, p.data_debito)))=?",
        "strftime('%Y', date(COALESCE(p.data_quitacao, p.data_debito)))=?",
    ]
    params_parc = [empresa, f"{int(mes_sel):02d}", f"{int(ano_sel):04d}"]

    if tipo_filtro != "(Todos)":
        wh_parc.append("d.tipo=?")
        params_parc.append("entrada" if tipo_filtro == "Entrada" else "saida")

    if cat_filtro != "(Todas)":
        wh_parc.append("COALESCE(d.categoria,'')=?")
        params_parc.append(cat_filtro)

    where_parc = " AND ".join(wh_parc)
    cursor.execute(
        f"""
        SELECT
            d.id AS lancamento_id,
            d.tipo,
            COALESCE(p.data_quitacao, p.data_debito) AS data_pagamento,
            d.descricao,
            d.categoria,
            d.valor,
            d.parcelas,
            p.parcela_num,
            d.forma_pagamento
        FROM parcelas_agendadas p
        JOIN dados d ON d.id = p.lancamento_id
        WHERE {where_parc}
        ORDER BY date(COALESCE(p.data_quitacao, p.data_debito)) ASC, d.id ASC, p.parcela_num ASC
        """,
        tuple(params_parc)
    )
    rows_parc = cursor.fetchall()

    df_parc = pd.DataFrame(
        rows_parc,
        columns=["Lançamento ID", "Tipo", "Data Pagamento", "Descrição", "Categoria", "Valor (lanç.)", "Parcelas", "Parcela", "Forma"]
    )
    if not df_parc.empty:
        # valor por parcela (se tiver parcelas)
        def _valor_item(r):
            try:
                v = float(r.get("Valor (lanç.)") or 0)
                n = int(r.get("Parcelas") or 0)
                if n and n > 0:
                    return v / n
                return v
            except Exception:
                return r.get("Valor (lanç.)")
        df_parc["Valor"] = df_parc.apply(_valor_item, axis=1)
        df_parc.drop(columns=["Valor (lanç.)"], inplace=True)

    # =========================
    # 2) Lançamentos pagos (sem parcelas) — usa data_operacao no mês
    # =========================
    wh_sem = [
        "empresa=?",
        "situacao='Pago'",
        "strftime('%m', date(criado_em))=?",
        "strftime('%Y', date(criado_em))=?",
        # sem parcelas cadastradas
        "COALESCE(parcelas,0) <= 1"
    ]
    params_sem = [empresa, f"{int(mes_sel):02d}", f"{int(ano_sel):04d}"]
    if tipo_filtro != "(Todos)":
        wh_sem.append("tipo=?")
        params_sem.append("entrada" if tipo_filtro == "Entrada" else "saida")
    if cat_filtro != "(Todas)":
        wh_sem.append("COALESCE(categoria,'')=?")
        params_sem.append(cat_filtro)

    where_sem = " AND ".join(wh_sem)
    cursor.execute(
        f"""
        SELECT
            id AS lancamento_id,
            tipo,
            data_operacao AS data_pagamento,
            descricao,
            categoria,
            valor,
            1 AS parcelas,
            NULL AS parcela_num,
            forma_pagamento
        FROM dados
        WHERE {where_sem}
        ORDER BY date(data_operacao) ASC, id ASC
        """,
        tuple(params_sem)
    )
    rows_sem = cursor.fetchall()
    df_sem = pd.DataFrame(
        rows_sem,
        columns=["Lançamento ID", "Tipo", "Data Pagamento", "Descrição", "Categoria", "Valor", "Parcelas", "Parcela", "Forma"]
    )

    # =========================
    # União
    # =========================
    df = pd.concat([df_parc, df_sem], ignore_index=True)
    if df.empty:
        st.info("Nenhum lançamento pago encontrado para esse mês/filtros.")
        return

    df["Tipo"] = df["Tipo"].replace({"entrada": "Entrada", "saida": "Saída"})
    df["Data Pagamento"] = df["Data Pagamento"].apply(iso_to_br)
    df["Valor"] = df["Valor"].apply(br_money)

    # Métricas
    # (calcula com valores numéricos do df original para não sofrer com br_money)
    df_num = pd.concat([df_parc, df_sem], ignore_index=True)
    if not df_num.empty:
        try:
            # garante Valor numérico
            if "Valor" not in df_num.columns:
                df_num["Valor"] = 0.0
            df_num["Valor"] = df_num["Valor"].apply(lambda x: float(x or 0))
        except Exception:
            pass

    total_ent = float(df_num.loc[df_num["Tipo"] == "entrada", "Valor"].sum()) if not df_num.empty else 0.0
    total_sai = float(df_num.loc[df_num["Tipo"] == "saida", "Valor"].sum()) if not df_num.empty else 0.0
    saldo = total_ent - total_sai

    m1, m2, m3 = st.columns(3)
    m1.metric("Entradas pagas", br_money(total_ent))
    m2.metric("Saídas pagas", br_money(total_sai))
    m3.metric("Saldo (Entradas - Saídas)", br_money(saldo))

    # Tabela
    st.markdown("### Lançamentos pagos (mês)")
    df_show = df.copy()
    df_show = df_show[["Data Pagamento", "Tipo", "Descrição", "Categoria", "Forma", "Parcela", "Valor", "Lançamento ID"]]
    st.dataframe(df_show, use_container_width=True)

    # Export
    st.markdown("### Exportar")
    try:
        titulo_pdf = f"Caixa — {empresa} — {mes_nome}/{int(ano_sel)}"
        pdf_bytes = df_to_pdf_bytes(df_show, title=titulo_pdf, max_rows=800)
        st.download_button(
            "Baixar PDF (Caixa)",
            data=pdf_bytes,
            file_name=f"caixa_{empresa}_{int(ano_sel)}_{int(mes_sel):02d}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Não foi possível gerar o PDF: {e}")
def page_contas(empresa: str):
    render_header("Contas a Pagar / Receber", empresa)
    st.subheader("Agenda (somente parcelas agendadas + pagamento)")

    hoje = date.today()

    colA, colB, colC = st.columns(3)
    with colA:
        visao = st.selectbox("Visão", ["Em aberto", "Pago", "Tudo"])
    with colB:
        tipo_visao = st.selectbox("Tipo", ["Tudo", "Despesas (a pagar)", "Entradas (a receber)"])
    with colC:
        dias = st.number_input("Mostrar parcelas até (dias)", min_value=1, step=1, value=90)

    col1, col2 = st.columns(2)
    with col1:
        filtro_cat = st.text_input("Filtrar categoria (contém)", value="")
    with col2:
        filtro_desc = st.text_input("Filtrar descrição (contém)", value="")

    dt_fim = date.fromordinal(hoje.toordinal() + int(dias))

    wheres = ["d.empresa=?"]
    params = [empresa]

    # janela (somente agendadas no período)
    wheres.append("date(pa.data_debito) >= date(?)")
    params.append(hoje.isoformat())
    wheres.append("date(pa.data_debito) <= date(?)")
    params.append(dt_fim.isoformat())

    # visão por parcela (paga?)
    if visao == "Em aberto":
        wheres.append("COALESCE(pa.paga,0)=0")
    elif visao == "Pago":
        wheres.append("COALESCE(pa.paga,0)=1")

    # tipo
    if tipo_visao == "Despesas (a pagar)":
        wheres.append("d.tipo='saida'")
    elif tipo_visao == "Entradas (a receber)":
        wheres.append("d.tipo='entrada'")

    if filtro_cat.strip():
        wheres.append("LOWER(COALESCE(d.categoria,'')) LIKE ?")
        params.append(f"%{filtro_cat.strip().lower()}%")

    if filtro_desc.strip():
        wheres.append("LOWER(COALESCE(d.descricao,'')) LIKE ?")
        params.append(f"%{filtro_desc.strip().lower()}%")

    where_sql = " AND ".join(wheres)

    cursor.execute(f"""
        SELECT
            pa.lancamento_id,
            d.tipo,
            pa.parcela_num,
            COALESCE(d.parcelas, 1) AS total_parcelas,
            pa.data_debito,
            pa.data_quitacao,
            d.descricao,
            d.categoria,
            d.conta_bancaria,
            d.valor,
            d.forma_pagamento,
            COALESCE(pa.paga,0) AS paga
        FROM parcelas_agendadas pa
        JOIN dados d ON d.id = pa.lancamento_id
        WHERE {where_sql}
        ORDER BY date(pa.data_debito) ASC, pa.lancamento_id ASC, pa.parcela_num ASC
    """, tuple(params))

    rows = cursor.fetchall()

    if not rows:
        st.info("Nenhuma parcela agendada encontrada no período selecionado.")
        return

    def _iso_to_date_or_none(iso):
        try:
            if iso is None or str(iso).strip() == "":
                return None
            return date.fromisoformat(str(iso))
        except Exception:
            try:
                return pd.to_datetime(iso).date()
            except Exception:
                return None

    linhas = []
    for (lanc_id, tipo, parcela_num, total_parcelas, data_debito_iso, data_quit_iso, desc, cat, conta, valor_total, forma, paga) in rows:
        try:
            total_parcelas_int = int(total_parcelas or 1)
        except Exception:
            total_parcelas_int = 1

        try:
            valor_total_f = float(valor_total or 0)
        except Exception:
            valor_total_f = 0.0

        valor_parcela = (valor_total_f / total_parcelas_int) if total_parcelas_int > 0 else valor_total_f

        deb_date = _iso_to_date_or_none(data_debito_iso)
        quit_date = _iso_to_date_or_none(data_quit_iso)

        linhas.append({
            "ID Lanç.": int(lanc_id),
            "Tipo": "Entrada" if str(tipo) == "entrada" else "Saída",
            "Parcela": int(parcela_num or 0),
            "Total Parcelas": int(total_parcelas_int),
            "Vencimento": deb_date,
            "Quitado em": quit_date,
            "Descrição": desc or "",
            "Categoria": cat or "",
            "Conta": conta or "",
            "Valor Parcela": float(valor_parcela or 0),
            "Forma": forma or "",
            "Paga": bool(int(paga or 0)),
            "__debito_iso": str(data_debito_iso),
            "__quit_iso": (str(data_quit_iso) if data_quit_iso is not None else "")
        })

    df = pd.DataFrame(linhas)

    # formata valor (mas mantém a coluna numérica para salvar)
    df_show = df.copy()
    if "Valor Parcela" in df_show.columns:
        df_show["Valor Parcela"] = df_show["Valor Parcela"].apply(br_money)

    st.markdown("### Parcelas agendadas (marque como paga e informe a data de quitação)")
    st.caption("✅ Dica: quando marcar **Paga**, preencha **Quitado em** (data real que foi pago/recebido).")

    cols_show = [
        "ID Lanç.", "Tipo", "Parcela", "Total Parcelas",
        "Vencimento", "Quitado em",
        "Descrição", "Categoria", "Conta", "Valor Parcela", "Forma", "Paga"
    ]

    df_edit = st.data_editor(
        df_show[cols_show],
        use_container_width=True,
        num_rows="fixed",
        # deixa editar só Paga e Quitado em
        disabled=[c for c in cols_show if c not in ("Paga", "Quitado em")],
        key=f"agenda_parcelas_{empresa}_{visao}_{tipo_visao}_{int(dias)}"
    )

    if st.button("Salvar pagamentos"):
        try:
            df_merge = df.copy()

            # pega valores editados
            paga_new_series = df_edit["Paga"].astype(bool).values
            quit_new_series = df_edit["Quitado em"].values  # pode vir date/None/str

            df_merge["Paga_novo"] = paga_new_series

            # normaliza quit_new para ISO (ou "")
            quit_iso_list = []
            for v in quit_new_series:
                d = None
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    d = None
                else:
                    if isinstance(v, date):
                        d = v
                    else:
                        try:
                            d = pd.to_datetime(v).date()
                        except Exception:
                            d = None
                quit_iso_list.append(d.isoformat() if isinstance(d, date) else "")

            df_merge["Quit_novo_iso"] = quit_iso_list

            # regra: se marcou como paga e não informou data, usa hoje
            mask_needs_today = (df_merge["Paga_novo"] == True) & ((df_merge["Quit_novo_iso"] == "") | (df_merge["Quit_novo_iso"].isna()))
            if mask_needs_today.any():
                df_merge.loc[mask_needs_today, "Quit_novo_iso"] = hoje.isoformat()

            # se desmarcou paga, zera data de quitação
            mask_unpaid = (df_merge["Paga_novo"] == False)
            df_merge.loc[mask_unpaid, "Quit_novo_iso"] = ""

            # identifica alterações (paga mudou OU data_quitacao mudou)
            df_merge["Paga_old"] = df_merge["Paga"].astype(bool)
            df_merge["Quit_old_iso"] = df_merge["__quit_iso"].fillna("").astype(str)

            alterados = df_merge[
                (df_merge["Paga_novo"] != df_merge["Paga_old"]) |
                (df_merge["Quit_novo_iso"].fillna("").astype(str) != df_merge["Quit_old_iso"])
            ]

            if alterados.empty:
                st.info("Nenhuma alteração para salvar.")
                return

            touched_lancs = set()
            for _, r in alterados.iterrows():
                lanc_id = int(r["ID Lanç."])
                parcela_num = int(r["Parcela"])
                debito_iso = str(r["__debito_iso"])
                paga_new = 1 if bool(r["Paga_novo"]) else 0
                quit_iso = str(r["Quit_novo_iso"] or "").strip() or None

                cursor.execute(
                    """
                    UPDATE parcelas_agendadas
                    SET paga=?, data_quitacao=?
                    WHERE lancamento_id=? AND parcela_num=? AND date(data_debito)=date(?)
                    """,
                    (paga_new, quit_iso, lanc_id, parcela_num, debito_iso)
                )
                touched_lancs.add(lanc_id)

            conn.commit()

            # atualiza situação dos lançamentos (Pago/Em aberto)
            for lanc_id in touched_lancs:
                try:
                    recomputar_situacao_lancamento(int(lanc_id))
                except Exception:
                    pass

            st.success("Pagamentos atualizados! ✅ Agora o Caixa considera a data de quitação.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar pagamentos: {e}")




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
        pass
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

    # ✅ Oculta o filtro "Conta Bancária"
    # Mantém a lógica interna (tabelas extratos_diarios / dias_fechados) usando uma conta padrão.
    conta_sel = contas[0]  # conta padrão

    col1, col2 = st.columns([2, 3])
    with col1:
        data_ref = st.date_input("Dia", value=date.today(), key="ed_data")
    with col2:
        # status do dia (aberto/fechado)
        fechado, fechado_em, fechado_por = get_info_dia(empresa, conta_sel, data_ref.isoformat())
        if int(fechado) == 1:
            st.error(f"📌 DIA FECHADO • {data_ref.strftime('%d/%m/%Y')} • {conta_sel}")
            if fechado_em or fechado_por:
                st.caption(f"Fechado em: {str(fechado_em) if fechado_em else '-'} • Por: {str(fechado_por) if fechado_por else '-'}")
        else:
            st.success("✅ DIA ABERTO")

    dia_fechado = is_dia_fechado(empresa, conta_sel, data_ref.isoformat())

    # ✅ Carrega automaticamente os saldos já lançados para o dia
    # (assim, ao entrar na página ou após salvar, os valores aparecem nos campos)
    load_key = f"_extrato_load_{empresa}"
    if load_key not in st.session_state:
        st.session_state[load_key] = {"data": None}

    iso_dia = data_ref.isoformat()
    # Só recarrega quando trocar o dia (não sobrescreve o que o usuário está digitando)
    if st.session_state[load_key].get("data") != iso_dia:
        try:
            cursor.execute(
                """
                SELECT saldo_inicio, saldo_fim
                FROM extratos_diarios
                WHERE empresa=? AND conta_bancaria=? AND date(data_ref)=date(?)
                LIMIT 1
                """,
                (empresa, conta_sel, iso_dia)
            )
            r = cursor.fetchone()
            ini_db = float(r[0]) if (r and r[0] is not None) else 0.0
            fim_db = float(r[1]) if (r and r[1] is not None) else 0.0
            st.session_state["ed_saldo_ini"] = ini_db
            st.session_state["ed_saldo_fim"] = fim_db
        except Exception:
            # se der qualquer erro, não derruba a página
            st.session_state["ed_saldo_ini"] = st.session_state.get("ed_saldo_ini", 0.0)
            st.session_state["ed_saldo_fim"] = st.session_state.get("ed_saldo_fim", 0.0)

        st.session_state[load_key]["data"] = iso_dia

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
    st.markdown("### Consultar saldos do dia")

    dia_ref = st.date_input("Dia", value=date.today(), key="ed_dia_consulta")

    cursor.execute(
        """
        SELECT
            e.conta_bancaria,
            e.data_ref,
            e.saldo_inicio,
            e.saldo_fim,
            e.usuario,
            COALESCE(d.fechado,0) AS fechado
        FROM extratos_diarios e
        LEFT JOIN dias_fechados d
          ON d.empresa=e.empresa
         AND d.conta_bancaria=e.conta_bancaria
         AND d.data_ref=e.data_ref
        WHERE e.empresa=?
          AND date(e.data_ref)=date(?)
        ORDER BY e.conta_bancaria ASC
        """,
        (empresa, dia_ref.isoformat())
    )
    rows = cursor.fetchall()
    df = pd.DataFrame(rows, columns=["Conta", "Data", "Saldo Início", "Saldo Fim", "Usuário", "Fechado"])

    if df.empty:
        st.info("Nenhum saldo diário lançado para esse dia.")
        return

    df_show = df.copy()
    df_show["Data"] = df_show["Data"].apply(iso_to_br)
    df_show["Saldo Início"] = df_show["Saldo Início"].apply(br_money)
    df_show["Saldo Fim"] = df_show["Saldo Fim"].apply(br_money)
    df_show["Fechado"] = df_show["Fechado"].apply(lambda x: "Sim" if int(x or 0) == 1 else "Não")

    # ✅ Oculta a coluna "Conta" na interface (mantém no banco/consulta interna)
    df_show_ui = df_show.drop(columns=["Conta"], errors="ignore")

    st.dataframe(df_show_ui, use_container_width=True)

    # Export (sem a coluna Conta)
    csv_bytes = df_show_ui.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Baixar CSV (Saldos do dia)",
        data=csv_bytes,
        file_name=f"saldos_diarios_{dia_ref.isoformat()}.csv",
        mime="text/csv"
    )





def page_relatorio_diario_geral(empresa: str):
    render_header("Relatório Diário Geral", empresa)
    st.subheader("Relatório diário (saldo + movimentação do dia)")

    contas = obter_contas_banco()  # pode estar vazio, sem problemas

    # ✅ Sem filtro por conta (pedido)
    data_ref = st.date_input("Dia do relatório", value=date.today(), key="rdg_data")

    # ---------- PDF (todas as empresas) ----------
    # 🔒 Só libera se o dia estiver FECHADO em Saldo Inicial/Final (todas as contas relevantes)
    def _stay_on_relatorio():
        st.session_state["_pagina_forcada"] = "Relatório Diário Geral"

    ok_pdf, pend = checar_pronto_pdf_todas_empresas(data_ref)

    if not ok_pdf:
        st.warning("🔒 Para liberar o PDF (todas as empresas), feche o dia em **Saldo Inicial/Final** e preencha **Saldo Início/Fim**.")
        with st.expander("Ver pendências"):
            for p in pend:
                st.write(f"• {p}")

    try:
        pdf_all = b""
        if ok_pdf:
            pdf_all = relatorio_diario_geral_pdf_todas_empresas(data_ref)

        st.download_button(
            "📄 Baixar PDF (todas as empresas)",
            data=pdf_all,
            file_name=f"relatorio_diario_geral_{data_ref.isoformat()}.pdf",
            mime="application/pdf",
            disabled=(not ok_pdf),
            on_click=_stay_on_relatorio
        )
    except Exception as e:
        st.info(f"PDF não disponível: {e}")

    # ---------- Totais do dia (MOVIMENTAÇÃO = CAIXA) ----------
    # Aqui SEMPRE puxa os valores do CAIXA (pagos no dia), independente de conta bancária.
    entradas_total = float(caixa_sum_dia(empresa, "entrada", data_ref, conta=None))
    saidas_total = float(caixa_sum_dia(empresa, "saida", data_ref, conta=None))
    saldo_mov = float(entradas_total - saidas_total)

    # ---------- Saldos do extrato (se existir) ----------
    # Se houver extratos por conta, soma tudo; se não houver, fica 0.
    try:
        cursor.execute(
            """
            SELECT COALESCE(SUM(saldo_inicio),0), COALESCE(SUM(saldo_fim),0)
            FROM extratos_diarios
            WHERE empresa=? AND date(data_ref)=date(?)
            """,
            (empresa, data_ref.isoformat())
        )
        r = cursor.fetchone() or (0, 0)
        total_ini = float(r[0] or 0)
        total_fim = float(r[1] or 0)
    except Exception:
        total_ini, total_fim = 0.0, 0.0

    # ---------- Métricas ----------

    c1, c2, c3 = st.columns(3)
    c1.metric("Entradas (dia)", br_money(entradas_total))
    c2.metric("Saídas (dia)", br_money(saidas_total))
    c3.metric("Movimentação (Entradas - Saídas)", br_money(saldo_mov))

    # ⚠️ Alerta: movimentação x extrato final (conferência geral)
    try:
        if abs((float(total_ini) + float(saldo_mov)) - float(total_fim)) > 0.009:
            st.warning("⚠️ Atenção: existe variação de valores — o Extrato Final do Dia NÃO confere com (Saldo Inicial + Entradas - Saídas).")
    except Exception:
        pass

    # 📌 Previsão de pagamento (próximo dia útil)
    try:
        prox = proximo_dia_util(data_ref)
        df_prev = obter_previsao_pagamento(empresa, prox)
        st.markdown(f"### Previsão de pagamento — {prox.strftime('%d/%m/%Y')}")
        if df_prev.empty:
            st.info("Sem previsões de pagamento para o próximo dia útil.")
        else:
            dfp = df_prev.copy()
            dfp = format_df_dates(dfp, ["Data"])
            dfp["Valor"] = dfp["Valor"].apply(br_money)
            st.dataframe(dfp.drop(columns=["LancamentoID"], errors="ignore"), use_container_width=True)
            try:
                st.caption(f"Total previsto: {br_money(df_prev['Valor'].sum())}")
            except Exception:
                pass
    except Exception as e:
        st.info(f"Não foi possível calcular a previsão de pagamento: {e}")

    st.markdown("---")
    st.markdown("### Lançamentos do dia")

    cursor.execute(
        f"""
        SELECT
            id, tipo, data_operacao, descricao,
            categoria, valor, forma_pagamento, situacao
        FROM dados
        WHERE empresa=? AND date(data_operacao)=date(?)
        ORDER BY tipo DESC, id DESC
        """,
        (empresa, data_ref.isoformat())
    )
    rows = cursor.fetchall()
    df_ops = pd.DataFrame(rows, columns=[
        "ID", "Tipo", "Data", "Descrição", "Categoria", "Valor", "Forma", "Situação"
    ])

    if df_ops.empty:
        st.info("Nenhuma operação lançada nesse dia para o filtro.")
        # (não retorna) — ainda mostramos a previsão do próximo dia útil abaixo

    df_ops_show = df_ops.copy()
    df_ops_show["Tipo"] = df_ops_show["Tipo"].replace({"entrada": "Entrada", "saida": "Despesa"})
    df_ops_show["Data"] = df_ops_show["Data"].apply(iso_to_br)
    df_ops_show["Valor"] = df_ops_show["Valor"].apply(br_money)

    st.dataframe(df_ops_show, use_container_width=True)

    # =========================
    # CAIXA DO DIA (PAGOS NO DIA) — mesma lógica da página Caixa
    # =========================
    st.markdown("---")
    st.markdown("### Caixa do Dia")

    # 1) Parcelas pagas no dia (usa data_quitacao se existir; senão data_debito)
    cursor.execute(
        """
        SELECT
            d.id AS lancamento_id,
            d.tipo,
            COALESCE(p.data_quitacao, p.data_debito) AS data_pagamento,
            COALESCE(d.descricao,'') AS descricao,
            COALESCE(d.categoria,'') AS categoria,
            COALESCE(d.valor,0) AS valor_total,
            COALESCE(d.parcelas,1) AS parcelas,
            p.parcela_num,
            COALESCE(d.forma_pagamento,'') AS forma
        FROM parcelas_agendadas p
        JOIN dados d ON d.id = p.lancamento_id
        WHERE d.empresa=?
          AND COALESCE(p.paga,0)=1
          AND date(COALESCE(p.data_quitacao, p.data_debito))=date(?)
        ORDER BY date(COALESCE(p.data_quitacao, p.data_debito)) ASC, d.id ASC, p.parcela_num ASC
        """,
        (empresa, data_ref.isoformat())
    )
    rows_parc_dia = cursor.fetchall()

    # 2) Lançamentos pagos sem parcelas no dia (usa data_operacao como data do pagamento)
    cursor.execute(
        """
        SELECT
            id AS lancamento_id,
            tipo,
            data_operacao AS data_pagamento,
            COALESCE(descricao,'') AS descricao,
            COALESCE(categoria,'') AS categoria,
            COALESCE(valor,0) AS valor_total,
            1 AS parcelas,
            NULL AS parcela_num,
            COALESCE(forma_pagamento,'') AS forma
        FROM dados
        WHERE empresa=?
          AND situacao='Pago'
          AND date(data_operacao)=date(?)
          AND COALESCE(parcelas,0) <= 1
        ORDER BY id ASC
        """,
        (empresa, data_ref.isoformat())
    )
    rows_sem_dia = cursor.fetchall()

    # Monta DataFrame unificado
    df_caixa_dia = pd.DataFrame(
        list(rows_parc_dia) + list(rows_sem_dia),
        columns=[
            "Lançamento ID", "Tipo", "Data Pagamento", "Descrição", "Categoria",
            "Valor (lanç.)", "Parcelas", "Parcela", "Forma"
        ]
    )

    if df_caixa_dia.empty:
        st.info("Nenhuma movimentação no Caixa neste dia.")
    else:
        # calcula valor por parcela (se tiver parcelas)
        def _valor_item_dia(r):
            try:
                v = float(r.get("Valor (lanç.)") or 0)
                n = int(r.get("Parcelas") or 1)
                if n <= 0:
                    n = 1
                return v / n
            except Exception:
                return r.get("Valor (lanç.)")

        df_caixa_dia["Valor"] = df_caixa_dia.apply(_valor_item_dia, axis=1)
        df_caixa_dia.drop(columns=["Valor (lanç.)"], inplace=True)

        # formata pra tela
        df_caixa_show = df_caixa_dia.copy()
        df_caixa_show["Tipo"] = df_caixa_show["Tipo"].replace({"entrada": "Entrada", "saida": "Saída"})
        df_caixa_show["Data Pagamento"] = df_caixa_show["Data Pagamento"].apply(iso_to_br)
        df_caixa_show["Valor"] = df_caixa_show["Valor"].apply(br_money)

        # reordena colunas
        df_caixa_show = df_caixa_show[[
            "Lançamento ID", "Tipo", "Data Pagamento", "Descrição", "Categoria", "Parcela", "Valor", "Forma"
        ]]

        st.dataframe(df_caixa_show, use_container_width=True)

    st.markdown("---")
    dt_prev = proximo_dia_util(data_ref)
    st.markdown(f"### 📆 Previsão de despesas — próximo dia útil ({dt_prev.strftime('%d/%m/%Y')})")
    df_prev = previsao_despesas_proximo_dia(empresa, data_ref, None)
    if df_prev.empty:
        st.info("Nenhuma despesa prevista (parcelas ou lançamentos futuros) para o próximo dia útil.")
    else:
        df_prev_show = df_prev.copy()
        df_prev_show["Data (próx. dia útil)"] = df_prev_show["Data (próx. dia útil)"].apply(iso_to_br)
        df_prev_show["Valor Previsto"] = df_prev_show["Valor Previsto"].apply(br_money)
        st.dataframe(df_prev_show, use_container_width=True)

        total_prev = float(df_prev["Valor Previsto"].sum())
        st.metric("Total previsto (despesas)", br_money(total_prev))

        csv_prev = df_prev_show.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Baixar CSV (Previsão próximo dia útil)",
            data=csv_prev,
            file_name=f"previsao_despesas_{empresa}_{dt_prev.isoformat()}.csv".replace("/", "-"),
            mime="text/csv"
        )

    # Excel com abas: Resumo, Operações, Previsão
    try:
        # Resumo (totais do dia)
        resumo_xlsx = pd.DataFrame([
            {
                "Empresa": empresa,
                "Data": data_ref.isoformat(),
                "Saldo Inicial (total)": br_money(total_ini),
                "Entradas (dia)": br_money(entradas_total),
                "Saídas (dia)": br_money(saidas_total),
                "Movimentação (E-S)": br_money(saldo_mov),
                "Saldo Final (informado, total)": br_money(total_fim),
                "Saldo Final (calculado, total)": br_money(float(total_ini) + float(saldo_mov)),
                "Diferença": br_money(float(total_fim) - (float(total_ini) + float(saldo_mov))),
            }
        ])

        ops_xlsx = df_ops_show.copy() if "df_ops_show" in locals() else df_ops.copy()
        prev_xlsx = df_prev_show.copy() if "df_prev_show" in locals() else df_prev.copy()

        xlsx_bytes = excel_multi_sheets_bytes({
            "Resumo": resumo_xlsx,
            "Operacoes_dia": ops_xlsx,
            "Previsao_prox_dia": prev_xlsx,
        })
        st.download_button(
            "📥 Baixar Excel (Relatório + Previsão)",
            data=xlsx_bytes,
            file_name=f"relatorio_diario_com_previsao_{empresa}_{data_ref.isoformat()}.xlsx".replace("/", "-"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        pass
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


def page_trava_mes(empresa: str):
    render_header("Configurações", empresa)
    if st.session_state.get("nivel") != "admin":
        st.error("Apenas administradores podem alterar esta configuração.")
        st.stop()

    st.subheader("Trava automática de mês (quando o mês já acabou)")

    usuario = st.session_state.get("usuario", "sistema")
    hoje = date.today()

    st.info(
        f"""Quando ativado, o sistema **bloqueia novos lançamentos/edições** em meses anteriores ao mês atual.
Hoje: **{hoje.strftime('%d/%m/%Y')}** (mês atual: **{hoje.month:02d}/{hoje.year}**)."""
    )

    atual = get_trava_mes_apos_fim(empresa)
    novo = st.checkbox("Ativar trava automática para meses encerrados", value=bool(atual))

    if st.button("Salvar configuração"):
        set_trava_mes_apos_fim(empresa, bool(novo), usuario)
        st.success("Configuração salva.")
        st.rerun()



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
    if pagina == "Operações":
        page_operacoes(empresa)
    elif pagina == "Lançamentos":
        page_lancamentos(empresa)
    elif pagina == "Caixa":
        page_caixa(empresa)
    elif pagina == "Contas a Pagar / Receber":
        page_contas(empresa)
    elif pagina == "Saldo Inicial/Final":
        page_extratos_diarios(empresa)
    elif pagina == "Relatório Diário Geral":
        page_relatorio_diario_geral(empresa)
    elif pagina == "Trava automática de mês":
        page_trava_mes(empresa)
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
