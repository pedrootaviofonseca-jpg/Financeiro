import db_adapter
import streamlit as st
import sqlite3
import pandas as pd
import math
from datetime import date, datetime, timedelta
from io import BytesIO
import os
import base64
from typing import Optional

# PDF (reportlab)
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# =========================
# CONFIG + INTERFACE (PADRÃO) — FUNDO VERMELHO
# =========================
st.set_page_config(page_title="LOCAÇÃO DE EQUIPAMENTOS", page_icon="🚜", layout="wide")

# ==========================================================
# ESTILO (mesma cara do modelo, mas com FUNDO VERMELHO)
# ==========================================================
st.markdown("""
<style>

/* ====== FUNDO VERMELHO ====== */
.stApp{
  background: linear-gradient(180deg, #4A0B0B 0%, #7A1111 55%, #A31616 100%);
  color: #F8FAFC;
}

/* ================= SIDEBAR ================= */
section[data-testid="stSidebar"]{
  background: linear-gradient(180deg, #0B4F8A 0%, #1E73BE 55%, #00A86B 120%);
}

section[data-testid="stSidebar"] *{
  color: #ffffff !important;
}

/* ================= ÁREA PRINCIPAL ================= */

/* Títulos */
h1, h2, h3 { color: #ffffff; }
a { color: #FFD1D1; }

/* Texto principal claro */
div[data-testid="stAppViewContainer"]{
  color: #F8FAFC !important;
}

/* Labels */
div[data-testid="stAppViewContainer"] label{
  color: #FFE7E7 !important;
  font-weight: 600;
}

/* ================= CARDS ================= */
.card{
  background: rgba(255,255,255,0.95);
  color: #111827;
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 10px 26px rgba(0,0,0,0.25);
}

/* Separador */
.hr{
  height: 1px;
  background: rgba(255,255,255,0.20);
  margin: 18px 0;
}

/* ================= INPUTS ================= */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
div[data-testid="stTextArea"] textarea{
  background: rgba(255,255,255,0.95) !important;
  border-color: rgba(0,0,0,0.15) !important;
}

div[data-testid="stAppViewContainer"] div[data-baseweb="input"] input{
  color: #111827 !important;
}

/* ================= BOTÕES ================= */
.stButton > button,
div[data-testid="stFormSubmitButton"] > button{
  background: linear-gradient(180deg, #B91C1C, #7F1D1D) !important;
  border: none !important;
  border-radius: 12px !important;
  color: #ffffff !important;
  padding: 0.60rem 1.0rem !important;
  box-shadow: 0 10px 20px rgba(0,0,0,0.25);
}

.stButton > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover{
  filter: brightness(1.08);
}

/* ================= DATAFRAME ================= */
[data-testid="stDataFrame"]{
  border-radius: 14px;
  overflow: hidden;
  background: rgba(255,255,255,0.95);
}

/* ================= TABELA CUSTOM ================= */
.wrap-table table{
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  background: rgba(255,255,255,0.95);
}

.wrap-table th{
  background: linear-gradient(180deg, #B91C1C 0%, #7F1D1D 100%) !important;
  color: #ffffff !important;
  font-weight: 700;
}

.wrap-table td{
  border: 1px solid rgba(0,0,0,0.10);
  padding: 10px 12px;
  vertical-align: top;
}

/* ================= BARRA DE TÍTULO (seções) ================= */
.section-title{
  background: linear-gradient(180deg, #B91C1C 0%, #7F1D1D 100%);
  color: #ffffff;
  border-radius: 14px;
  padding: 10px 14px;
  margin: 14px 0 10px 0;
  font-weight: 800;
  box-shadow: 0 8px 18px rgba(0,0,0,0.25);
}

/* ================= BRANDING ================= */
.brandbar{
  background: linear-gradient(90deg, #7F1D1D 0%, #B91C1C 55%, #DC2626 100%);
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
  color: rgba(255,255,255,0.90);
  font-weight: 600;
  font-size: 12px;
}

</style>
""", unsafe_allow_html=True)

# ==========================================================
# BRANDING (Logo + cabeçalho) — igual aos outros módulos
# Coloque um arquivo logo_app.png (ou logo.png) na mesma pasta do .py
# ==========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _find_logo_path() -> Optional[str]:
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

def render_branding():
    """Mostra logo no sidebar e um banner no topo."""
    logo_path = _find_logo_path()

    # Sidebar: logo + nome
    with st.sidebar:
        if logo_path:
            st.image(logo_path, use_container_width=True)
        st.markdown("### 🚜 Locação de Maquinário")
        st.caption("Clientes • Máquinas • Locações • Financeiro • Relatórios")

    # Topo: banner
    if logo_path:
        uri = _img_to_data_uri(logo_path)
        st.markdown(
            f"""
            <div class="brandbar">
              <img src="{uri}" style="height:56px; width:auto; border-radius:12px; background: rgba(255,255,255,0.12); padding:6px;" />
              <div>
                <div class="title">LOCAÇÃO DE EQUIPAMENTOS</div>
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
                <div class="title">LOCAÇÃO DE EQUIPAMENTOS</div>
                <div class="subtitle">Coloque um arquivo <b>logo_app.png</b> (ou logo.png) na mesma pasta do .py para aparecer aqui.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )

def section_title(texto: str):
    st.markdown(f'<div class="section-title">{texto}</div>', unsafe_allow_html=True)

def card_open():
    return  # desativado (evita a faixa branca)

def card_close():
    return  # desativado (evita a faixa branca)

# chama branding no topo (no lugar do st.title antigo)
render_branding()

# =========================
# BANCO (SQLite)
# =========================
conn = db_adapter.get_conn("locacao.db", schema="locacao")
cursor = db_adapter.get_cursor(conn)


def df_query(sql, params=()):
    return pd.read_sql_query(sql, conn, params=params)


def exec_sql(sql, params=()):
    cursor.execute(sql, params)
    conn.commit()


def coluna_existe(tabela: str, coluna: str) -> bool:
    try:
        info = df_query(f"PRAGMA table_info({tabela})")
        if info.empty:
            return False
        return coluna in info["name"].tolist()
    except Exception:
        return False


def criar_tabelas():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        documento TEXT,
        telefone TEXT,
        email TEXT,
        endereco TEXT,
        cliente_fixo INTEGER DEFAULT 0
    )
    """)
    if not coluna_existe("clientes", "cliente_fixo"):
        try:
            exec_sql("ALTER TABLE clientes ADD COLUMN cliente_fixo INTEGER DEFAULT 0")
        except Exception:
            pass

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS maquinas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT,
        descricao TEXT NOT NULL,
        categoria TEXT,
        valor_diaria REAL DEFAULT 0,
        valor_mensal REAL DEFAULT 0,
        quantidade_total INTEGER DEFAULT 1,
        quantidade_manutencao INTEGER DEFAULT 0,
        quantidade_disponivel INTEGER DEFAULT 1,
        observacoes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER NOT NULL,
        data_inicio TEXT NOT NULL,
        status TEXT DEFAULT 'Em andamento',            -- Em andamento / Finalizado / Cancelado
        modo_cobranca TEXT DEFAULT 'Diária',           -- Diária / Mensal
        frete_ida REAL DEFAULT 0,
        frete_volta REAL DEFAULT 0,
        desconto REAL DEFAULT 0,
        observacoes TEXT,
        criado_em TEXT,
        data_fim_real TEXT,
        total_final REAL DEFAULT 0,
        fechado_em TEXT,
        pago INTEGER DEFAULT 0,
        FOREIGN KEY(cliente_id) REFERENCES clientes(id)
    )
    """)
    if not coluna_existe("locacoes", "pago"):
        try:
            exec_sql("ALTER TABLE locacoes ADD COLUMN pago INTEGER DEFAULT 0")
        except Exception:
            pass

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locacao_itens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        locacao_id INTEGER NOT NULL,
        maquina_id INTEGER NOT NULL,
        quantidade INTEGER DEFAULT 1,
        valor_diaria REAL DEFAULT 0,
        valor_mensal REAL DEFAULT 0,
        FOREIGN KEY(locacao_id) REFERENCES locacoes(id),
        FOREIGN KEY(maquina_id) REFERENCES maquinas(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recebimentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        locacao_id INTEGER NOT NULL,
        data_pagamento TEXT NOT NULL,
        forma TEXT,
        valor REAL NOT NULL,
        observacoes TEXT,
        FOREIGN KEY(locacao_id) REFERENCES locacoes(id)
    )
    """)

    conn.commit()


criar_tabelas()

# =========================
# HELPERS
# =========================
def to_iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def money(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def last_day_of_month(ano: int, mes: int) -> date:
    if mes == 12:
        return date(ano, 12, 31)
    return date(ano, mes + 1, 1) - timedelta(days=1)


def month_add(ano: int, mes: int, delta: int):
    idx = (ano * 12 + (mes - 1)) + delta
    novo_ano = idx // 12
    novo_mes = (idx % 12) + 1
    return novo_ano, novo_mes


def overlap_days(a_start: date, a_end: date, b_start: date, b_end: date) -> int:
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    if end < start:
        return 0
    return (end - start).days + 1


def recalcular_disponivel_por_uso(maquina_id: int):
    m = df_query("""
        SELECT quantidade_total, quantidade_manutencao
        FROM maquinas
        WHERE id=?
    """, (int(maquina_id),))
    if m.empty:
        return

    total = int(m.loc[0, "quantidade_total"] or 0)
    manut = int(m.loc[0, "quantidade_manutencao"] or 0)

    alugado = df_query("""
        SELECT COALESCE(SUM(li.quantidade),0) as qtd
        FROM locacao_itens li
        JOIN locacoes l ON l.id = li.locacao_id
        WHERE li.maquina_id = ?
          AND l.status = 'Em andamento'
    """, (int(maquina_id),))["qtd"][0]
    alugado = int(alugado or 0)

    disp = max(0, total - manut - alugado)
    exec_sql("UPDATE maquinas SET quantidade_disponivel=? WHERE id=?", (disp, int(maquina_id)))


def recalcular_disponivel_todas():
    ids = df_query("SELECT id FROM maquinas")
    for mid in ids["id"].tolist():
        recalcular_disponivel_por_uso(int(mid))


def calcular_periodo(data_ini_str: str, data_fim_str: str, modo: str) -> int:
    di = datetime.strptime(data_ini_str, "%Y-%m-%d").date()
    df = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
    dias = (df - di).days
    if dias < 0:
        return 0
    dias = max(1, dias + 1)
    if modo == "Mensal":
        return int(math.ceil(dias / 30.0))
    return int(dias)


def soma_recebida(loc_id: int) -> float:
    v = df_query("""
        SELECT COALESCE(SUM(valor),0) as total
        FROM recebimentos
        WHERE locacao_id=?
    """, (int(loc_id),))["total"][0]
    return float(v or 0)


def atualizar_pago(loc_id: int):
    l = df_query("SELECT total_final, status FROM locacoes WHERE id=?", (int(loc_id),))
    if l.empty:
        return
    status = (l.loc[0, "status"] or "").strip()
    total = float(l.loc[0, "total_final"] or 0)
    recebido = soma_recebida(loc_id)

    if status == "Finalizado" and total > 0 and recebido >= total - 0.00001:
        exec_sql("UPDATE locacoes SET pago=1 WHERE id=?", (int(loc_id),))
    else:
        exec_sql("UPDATE locacoes SET pago=0 WHERE id=?", (int(loc_id),))


def calcular_total_locacao(loc_id: int, data_fechamento: date):
    l = df_query("""
        SELECT id, data_inicio, modo_cobranca, frete_ida, frete_volta, desconto
        FROM locacoes WHERE id=?
    """, (int(loc_id),))
    if l.empty:
        return {"erro": "Locação não encontrada."}

    data_inicio = l.loc[0, "data_inicio"]
    modo = (l.loc[0, "modo_cobranca"] or "Diária").strip()
    frete_ida = float(l.loc[0, "frete_ida"] or 0)
    frete_volta = float(l.loc[0, "frete_volta"] or 0)
    desconto = float(l.loc[0, "desconto"] or 0)

    periodo = calcular_periodo(data_inicio, to_iso(data_fechamento), modo)
    if periodo <= 0:
        return {"erro": "A data de fechamento não pode ser menor que a data de início."}

    itens = df_query("""
        SELECT m.descricao, li.quantidade, li.valor_diaria, li.valor_mensal
        FROM locacao_itens li
        JOIN maquinas m ON m.id = li.maquina_id
        WHERE li.locacao_id=?
    """, (int(loc_id),))

    total_itens = 0.0
    detalhes = []
    for _, r in itens.iterrows():
        qtd = int(r["quantidade"] or 1)
        vd = float(r["valor_diaria"] or 0)
        vm = float(r["valor_mensal"] or 0)
        preco = vd if modo == "Diária" else vm
        subtotal = float(preco) * qtd * periodo
        total_itens += subtotal
        detalhes.append({
            "Máquina": r["descricao"],
            "Qtd": qtd,
            "Preço": money(preco),
            "Período": periodo,
            "Subtotal": money(subtotal),
        })

    total_geral = total_itens + frete_ida + frete_volta - desconto
    return {"modo": modo, "periodo": periodo, "detalhes": detalhes, "total_geral": total_geral}


def fechar_locacao(loc_id: int, data_fechamento: date):
    calc = calcular_total_locacao(loc_id, data_fechamento)
    if calc.get("erro"):
        return calc

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    exec_sql("""
        UPDATE locacoes
        SET status='Finalizado',
            data_fim_real=?,
            total_final=?,
            fechado_em=?
        WHERE id=?
    """, (to_iso(data_fechamento), float(calc["total_geral"]), agora, int(loc_id)))

    recalcular_disponivel_todas()
    atualizar_pago(loc_id)
    return calc


def reabrir_locacao_mesmos_itens(loc_id: int, nova_data_inicio: date) -> int:
    base = df_query("""
        SELECT cliente_id, modo_cobranca, frete_ida, frete_volta, desconto, observacoes
        FROM locacoes
        WHERE id=?
    """, (int(loc_id),))
    if base.empty:
        raise ValueError("Locação original não encontrada.")

    cliente_id = int(base.loc[0, "cliente_id"])
    modo = str(base.loc[0, "modo_cobranca"] or "Diária")
    frete_ida = float(base.loc[0, "frete_ida"] or 0)
    frete_volta = float(base.loc[0, "frete_volta"] or 0)
    desconto = float(base.loc[0, "desconto"] or 0)
    obs = str(base.loc[0, "observacoes"] or "")
    criado_em = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    exec_sql("""
        INSERT INTO locacoes (cliente_id, data_inicio, status, modo_cobranca,
                              frete_ida, frete_volta, desconto, observacoes, criado_em, pago)
        VALUES (?, ?, 'Em andamento', ?, ?, ?, ?, ?, ?, 0)
    """, (cliente_id, to_iso(nova_data_inicio), modo, frete_ida, frete_volta, desconto, obs, criado_em))

    novo_id = int(df_query("SELECT last_insert_rowid() as id")["id"][0])

    itens = df_query("""
        SELECT maquina_id, quantidade, valor_diaria, valor_mensal
        FROM locacao_itens
        WHERE locacao_id=?
    """, (int(loc_id),))

    for _, r in itens.iterrows():
        exec_sql("""
            INSERT INTO locacao_itens (locacao_id, maquina_id, quantidade, valor_diaria, valor_mensal)
            VALUES (?, ?, ?, ?, ?)
        """, (novo_id, int(r["maquina_id"]), int(r["quantidade"] or 1),
              float(r["valor_diaria"] or 0), float(r["valor_mensal"] or 0)))

    recalcular_disponivel_todas()
    return novo_id


def fechar_e_reabrir_todas_cliente(cliente_id: int, data_fechamento: date, reabrir_dia_seguinte: bool):
    abertas_ids = df_query("""
        SELECT id FROM locacoes
        WHERE status='Em andamento' AND cliente_id=?
        ORDER BY id
    """, (int(cliente_id),))

    if abertas_ids.empty:
        return {"erro": "Este cliente não tem locações abertas para fechar."}

    # fecha todas
    for loc_id in abertas_ids["id"].tolist():
        res = fechar_locacao(int(loc_id), data_fechamento)
        if res.get("erro"):
            return {"erro": f"Erro ao fechar a locação {loc_id}: {res['erro']}"}

    # reabre todas
    nova_data = data_fechamento + timedelta(days=1) if reabrir_dia_seguinte else data_fechamento
    novos = []
    for loc_id in abertas_ids["id"].tolist():
        novo_id = reabrir_locacao_mesmos_itens(int(loc_id), nova_data)
        novos.append(int(novo_id))

    return {"ok": True, "fechadas": abertas_ids["id"].tolist(), "reabertas": novos, "nova_data": nova_data}


# =========================
# RELATÓRIO (CÁLCULOS)
# =========================
def _locacoes_que_encostam_no_periodo(inicio: date, fim: date):
    return df_query("""
        SELECT l.id, l.data_inicio, l.data_fim_real, l.status, l.modo_cobranca
        FROM locacoes l
        WHERE date(l.data_inicio) <= date(?)
          AND (
                l.status='Em andamento'
                OR (l.status='Finalizado' AND l.data_fim_real IS NOT NULL AND date(l.data_fim_real) >= date(?))
              )
    """, (to_iso(fim), to_iso(inicio)))


def _itens_com_maquinas():
    return df_query("""
        SELECT li.locacao_id, li.maquina_id, li.quantidade, li.valor_diaria, li.valor_mensal,
               m.descricao
        FROM locacao_itens li
        JOIN maquinas m ON m.id = li.maquina_id
    """)


def calcular_estimada_por_maquina_no_periodo(inicio_mes: date, fim_analise: date) -> pd.DataFrame:
    locs = _locacoes_que_encostam_no_periodo(inicio_mes, fim_analise)
    itens = _itens_com_maquinas()
    if locs.empty or itens.empty:
        return pd.DataFrame(columns=["maquina_id", "descricao", "qtd_total", "valor_estimado"])

    base = itens.merge(locs, left_on="locacao_id", right_on="id", how="inner")

    def calc_valor_linha(row) -> float:
        di = datetime.strptime(row["data_inicio"], "%Y-%m-%d").date()
        if str(row["status"]) == "Finalizado" and row["data_fim_real"]:
            df = datetime.strptime(row["data_fim_real"], "%Y-%m-%d").date()
        else:
            df = fim_analise

        dias = overlap_days(di, df, inicio_mes, fim_analise)
        if dias <= 0:
            return 0.0

        qtd = int(row["quantidade"] or 0)
        modo = str(row["modo_cobranca"] or "Diária").strip()

        if modo == "Mensal":
            vm = float(row["valor_mensal"] or 0)
            return vm * qtd * (dias / 30.0)
        else:
            vd = float(row["valor_diaria"] or 0)
            return vd * qtd * dias

    base["valor_estimado"] = base.apply(calc_valor_linha, axis=1)

    resumo = base.groupby(["maquina_id", "descricao"], as_index=False).agg(
        qtd_total=("quantidade", "sum"),
        valor_estimado=("valor_estimado", "sum")
    )
    resumo["valor_estimado"] = resumo["valor_estimado"].astype(float)
    return resumo


def max_simultaneo_no_periodo(inicio_mes: date, fim_analise: date) -> pd.DataFrame:
    locs = _locacoes_que_encostam_no_periodo(inicio_mes, fim_analise)
    itens = _itens_com_maquinas()
    if locs.empty or itens.empty:
        return pd.DataFrame(columns=["maquina_id", "descricao", "pico_simultaneo"])

    base = itens.merge(locs, left_on="locacao_id", right_on="id", how="inner")

    events = {}   # maquina_id -> dict(date->delta)
    desc_map = {}

    for _, r in base.iterrows():
        mid = int(r["maquina_id"])
        desc_map[mid] = str(r["descricao"])
        qtd = int(r["quantidade"] or 0)
        if qtd <= 0:
            continue

        di = datetime.strptime(r["data_inicio"], "%Y-%m-%d").date()
        if str(r["status"]) == "Finalizado" and r["data_fim_real"]:
            df = datetime.strptime(r["data_fim_real"], "%Y-%m-%d").date()
        else:
            df = fim_analise

        start = max(di, inicio_mes)
        end = min(df, fim_analise)
        if end < start:
            continue

        ev = events.setdefault(mid, {})
        ev[start] = ev.get(start, 0) + qtd
        ev_end_next = end + timedelta(days=1)
        ev[ev_end_next] = ev.get(ev_end_next, 0) - qtd

    rows = []
    for mid, ev in events.items():
        pico = 0
        atual = 0
        for d in sorted(ev.keys()):
            atual += ev[d]
            pico = max(pico, atual)
        rows.append({"maquina_id": mid, "descricao": desc_map.get(mid, str(mid)), "pico_simultaneo": int(pico)})

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["maquina_id", "descricao", "pico_simultaneo"])
    return df.sort_values("pico_simultaneo", ascending=False)


def recebido_no_mes(inicio: date, fim: date) -> float:
    v = df_query("""
        SELECT COALESCE(SUM(valor),0) as recebido
        FROM recebimentos
        WHERE date(data_pagamento) >= date(?)
          AND date(data_pagamento) <= date(?)
    """, (to_iso(inicio), to_iso(fim)))["recebido"][0]
    return float(v or 0)


def faturado_fechado_no_mes(inicio: date, fim: date) -> float:
    v = df_query("""
        SELECT COALESCE(SUM(total_final),0) as faturado
        FROM locacoes
        WHERE status='Finalizado'
          AND data_fim_real IS NOT NULL
          AND date(data_fim_real) >= date(?)
          AND date(data_fim_real) <= date(?)
    """, (to_iso(inicio), to_iso(fim)))["faturado"][0]
    return float(v or 0)


# =========================
# PDF HELPERS
# =========================
def _pdf_table(data, col_widths=None):
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def gerar_pdf_locacao(loc_id: int) -> tuple[bytes, str]:
    styles = getSampleStyleSheet()
    buf = BytesIO()

    loc = df_query("""
        SELECT l.id, l.cliente_id, c.nome as cliente, c.documento, c.telefone, c.email,
               l.data_inicio, l.data_fim_real, l.status, l.modo_cobranca,
               l.frete_ida, l.frete_volta, l.desconto, l.total_final, l.observacoes
        FROM locacoes l
        JOIN clientes c ON c.id = l.cliente_id
        WHERE l.id = ?
    """, (int(loc_id),))
    if loc.empty:
        raise ValueError("Locação não encontrada.")

    r = loc.iloc[0].to_dict()

    itens = df_query("""
        SELECT m.descricao, li.quantidade, li.valor_diaria, li.valor_mensal
        FROM locacao_itens li
        JOIN maquinas m ON m.id = li.maquina_id
        WHERE li.locacao_id = ?
        ORDER BY m.descricao
    """, (int(loc_id),))

    recs = df_query("""
        SELECT data_pagamento, forma, valor
        FROM recebimentos
        WHERE locacao_id = ?
        ORDER BY date(data_pagamento)
    """, (int(loc_id),))

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36
    )

    story = []
    story.append(Paragraph("NOTA / RECIBO - LOCAÇÃO DE MAQUINÁRIO", styles["Title"]))
    story.append(Spacer(1, 12))

    info = [
        ["Locação", str(r["id"]), "Status", str(r["status"] or "")],
        ["Cliente", str(r["cliente"] or ""), "Documento", str(r.get("documento") or "")],
        ["Telefone", str(r.get("telefone") or ""), "E-mail", str(r.get("email") or "")],
        ["Início", str(r.get("data_inicio") or ""), "Fechamento", str(r.get("data_fim_real") or "-")],
        ["Cobrança", str(r.get("modo_cobranca") or ""), "Total final", money(r.get("total_final") or 0)],
    ]
    story.append(_pdf_table([["Campo", "Valor", "Campo", "Valor"]] + info, col_widths=[90, 180, 90, 180]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Itens da locação", styles["Heading2"]))
    if itens.empty:
        story.append(Paragraph("Sem itens cadastrados.", styles["Normal"]))
    else:
        linhas = [["Máquina", "Qtd", "Diária", "Mensal"]]
        for _, it in itens.iterrows():
            linhas.append([
                str(it["descricao"]),
                str(int(it["quantidade"] or 0)),
                money(it["valor_diaria"] or 0),
                money(it["valor_mensal"] or 0),
            ])
        story.append(_pdf_table(linhas, col_widths=[290, 50, 90, 90]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Ajustes", styles["Heading2"]))
    ajustes = [
        ["Frete ida", money(r.get("frete_ida") or 0)],
        ["Frete volta", money(r.get("frete_volta") or 0)],
        ["Desconto", money(r.get("desconto") or 0)],
    ]
    story.append(_pdf_table([["Item", "Valor"]] + ajustes, col_widths=[340, 180]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Pagamentos", styles["Heading2"]))
    recebido = 0.0
    if recs.empty:
        story.append(Paragraph("Nenhum recebimento registrado.", styles["Normal"]))
    else:
        linhas = [["Data", "Forma", "Valor (R$)"]]
        for _, rr in recs.iterrows():
            v = float(rr["valor"] or 0)
            recebido += v
            linhas.append([str(rr["data_pagamento"]), str(rr["forma"] or ""), money(v)])
        story.append(_pdf_table(linhas, col_widths=[120, 220, 180]))

    total_final = float(r.get("total_final") or 0)
    saldo = total_final - recebido
    story.append(Spacer(1, 10))
    story.append(_pdf_table(
        [["Resumo", "Valor"],
         ["Total final", money(total_final)],
         ["Recebido", money(recebido)],
         ["Saldo", money(saldo)]],
        col_widths=[340, 180]
    ))

    obs = (r.get("observacoes") or "").strip()
    if obs:
        story.append(Spacer(1, 12))
        story.append(Paragraph("Observações", styles["Heading2"]))
        story.append(Paragraph(obs.replace("\n", "<br/>"), styles["Normal"]))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()

    cliente_slug = "".join([c for c in str(r["cliente"]) if c.isalnum() or c in (" ", "_", "-")]).strip().replace(" ", "_")
    nome = f"locacao_{int(loc_id)}_{cliente_slug or 'cliente'}.pdf"
    return pdf_bytes, nome


def gerar_pdf_relatorio_mensal(
    ano: int,
    mes: int,
    inicio_mes: date,
    fim_analise: date,
    resumo_df: pd.DataFrame,
    pico_df: pd.DataFrame,
    situacao_df: pd.DataFrame,
    recebido_mes: float,
    faturado_mes: float,
    a_receber_mes: float,
    previsto_mes: float
) -> tuple[bytes, str]:
    styles = getSampleStyleSheet()
    buf = BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36
    )

    story = []
    story.append(Paragraph(f"RELATÓRIO MENSAL - {ano}-{mes:02d}", styles["Title"]))
    story.append(Paragraph(f"Período: {inicio_mes.strftime('%d/%m/%Y')} até {fim_analise.strftime('%d/%m/%Y')}", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Resumo Financeiro", styles["Heading2"]))
    story.append(_pdf_table(
        [["Item", "Valor"],
         ["Recebido no mês", money(recebido_mes)],
         ["Faturado (fechadas no mês)", money(faturado_mes)],
         ["A receber (fechadas do mês)", money(a_receber_mes)],
         ["Previsto (abertas + fechadas)", money(previsto_mes)]],
        col_widths=[340, 180]
    ))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Máquinas alugadas no mês (quantidade e valor estimado)", styles["Heading2"]))
    if resumo_df is None or resumo_df.empty:
        story.append(Paragraph("Sem dados no período.", styles["Normal"]))
    else:
        linhas = [["Máquina", "Qtd (somada)", "Valor estimado"]]
        tmp = resumo_df.sort_values("valor_estimado", ascending=False).head(35)
        for _, rr in tmp.iterrows():
            linhas.append([str(rr["descricao"]), str(int(rr["qtd_total"])), money(float(rr["valor_estimado"]))])
        story.append(_pdf_table(linhas, col_widths=[270, 90, 130]))
        story.append(Paragraph("Obs: lista limitada aos 35 primeiros no PDF.", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Pico do mês (máximo simultâneo por máquina)", styles["Heading2"]))
    if pico_df is None or pico_df.empty:
        story.append(Paragraph("Sem dados para o pico no período.", styles["Normal"]))
    else:
        linhas = [["Máquina", "Pico simultâneo"]]
        tmp = pico_df.sort_values("pico_simultaneo", ascending=False).head(35)
        for _, rr in tmp.iterrows():
            linhas.append([str(rr["descricao"]), str(int(rr["pico_simultaneo"]))])
        story.append(_pdf_table(linhas, col_widths=[400, 120]))
        story.append(Paragraph("Obs: lista limitada aos 35 primeiros no PDF.", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Situação atual por máquina (alugadas agora x disponíveis)", styles["Heading2"]))
    if situacao_df is None or situacao_df.empty:
        story.append(Paragraph("Sem máquinas cadastradas.", styles["Normal"]))
    else:
        linhas = [["Máquina", "Total", "Manut.", "Alugadas", "Disp."]]
        tmp = situacao_df.head(40)
        for _, rr in tmp.iterrows():
            linhas.append([
                str(rr["Máquina"]),
                str(int(rr["Total"])),
                str(int(rr["Manutenção"])),
                str(int(rr["Alugadas agora"])),
                str(int(rr["Disponíveis"])),
            ])
        story.append(_pdf_table(linhas, col_widths=[250, 60, 60, 70, 70]))
        story.append(Paragraph("Obs: lista limitada aos 40 primeiros no PDF.", styles["Normal"]))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    nome = f"relatorio_mensal_{ano}_{mes:02d}.pdf"
    return pdf_bytes, nome


# =========================
# NAVEGAÇÃO SEGURA
# =========================
MENU_OPCOES = [
    "Dashboard",
    "Clientes",
    "Máquinas",
    "Nova Locação",
    "Locações (abertas)",
    "Financeiro",
    "Relatórios"
]

if "goto_menu" not in st.session_state:
    st.session_state.goto_menu = None

if st.session_state.goto_menu in MENU_OPCOES:
    st.session_state.menu = st.session_state.goto_menu
    st.session_state.goto_menu = None

st.sidebar.title("Menu")
menu = st.sidebar.radio("Navegação", MENU_OPCOES, key="menu")

# =========================
# INIT
# =========================
recalcular_disponivel_todas()

# =========================
# DASHBOARD
# =========================
if menu == "Dashboard":
    section_title("📊 Visão Geral")
    card_open()

    total_tipos = df_query("SELECT COUNT(*) as total FROM maquinas")["total"][0]
    total_clientes = df_query("SELECT COUNT(*) as total FROM clientes")["total"][0]
    loc_abertas = df_query("SELECT COUNT(*) as total FROM locacoes WHERE status='Em andamento'")["total"][0]
    loc_fechadas = df_query("SELECT COUNT(*) as total FROM locacoes WHERE status='Finalizado'")["total"][0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tipos de máquinas", int(total_tipos))
    c2.metric("Clientes", int(total_clientes))
    c3.metric("Locações abertas", int(loc_abertas))
    c4.metric("Locações fechadas", int(loc_fechadas))

    # ❌ REMOVIDO st.divider()

    st.write("Estoque por tipo:")
    st.dataframe(df_query("""
        SELECT id, codigo, descricao, categoria,
               quantidade_total, quantidade_manutencao, quantidade_disponivel,
               valor_diaria, valor_mensal
        FROM maquinas
        ORDER BY descricao
    """), use_container_width=True)

    card_close()

# =========================
# CLIENTES
# =========================
elif menu == "Clientes":
    section_title("👤 Clientes")
    card_open()

    # ---------- FLAGS ----------
    if "cliente_salvo" not in st.session_state:
        st.session_state.cliente_salvo = False
    if "ultimo_cliente_id" not in st.session_state:
        st.session_state.ultimo_cliente_id = None

    # ---------- MENSAGEM PÓS-SALVAR ----------
    if st.session_state.cliente_salvo:
        st.success(f"Cliente salvo com sucesso! Nº {st.session_state.ultimo_cliente_id}")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Sim, cadastrar outro cliente"):
                for k in list(st.session_state.keys()):
                    if k.startswith("cl_"):
                        del st.session_state[k]
                st.session_state.cliente_salvo = False
                st.session_state.ultimo_cliente_id = None
                st.rerun()
        with c2:
            if st.button("➡️ Não, ver lista de clientes"):
                st.session_state.cliente_salvo = False
                st.session_state.ultimo_cliente_id = None
                st.rerun()
        st.stop()

    # ---------- CADASTRO ----------
    with st.expander("➕ Cadastrar cliente", expanded=True):
        with st.form("form_cliente", clear_on_submit=False):
            nome = st.text_input("Nome/Razão Social", key="cl_nome")
            documento = st.text_input("CPF/CNPJ", key="cl_documento")
            telefone = st.text_input("Telefone", key="cl_telefone")
            email = st.text_input("E-mail", key="cl_email")
            endereco = st.text_area("Endereço", key="cl_endereco")
            cliente_fixo = st.checkbox("Cliente fixo (recorrente)", value=False, key="cl_fixo")
            salvar_cliente = st.form_submit_button("Salvar Cliente")

        if salvar_cliente:
            if not (nome or "").strip():
                st.error("Informe o nome do cliente.")
            else:
                exec_sql("""
                    INSERT INTO clientes (nome, documento, telefone, email, endereco, cliente_fixo)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (nome, documento, telefone, email, endereco, 1 if cliente_fixo else 0))
                cid = int(df_query("SELECT last_insert_rowid() as id")["id"][0])

                st.session_state.cliente_salvo = True
                st.session_state.ultimo_cliente_id = cid
                st.rerun()

    st.divider()

    # ---------- LISTA ----------
    df_clientes = df_query("""
        SELECT id, nome, documento, telefone, email, endereco,
               COALESCE(cliente_fixo,0) as cliente_fixo
        FROM clientes
        ORDER BY nome
    """)

    if df_clientes.empty:
        st.info("Nenhum cliente cadastrado ainda.")
        st.stop()

    show = df_clientes.copy()
    show["cliente_fixo"] = show["cliente_fixo"].apply(lambda x: "SIM" if int(x) == 1 else "NÃO")
    show.rename(columns={
        "id": "ID",
        "nome": "Nome",
        "documento": "Documento",
        "telefone": "Telefone",
        "email": "E-mail",
        "endereco": "Endereço",
        "cliente_fixo": "Cliente fixo"
    }, inplace=True)

    st.dataframe(show, use_container_width=True)

    st.divider()

    # ---------- EDITAR / EXCLUIR ----------
    st.subheader("Editar / Excluir cliente")

    cliente_id = st.selectbox(
        "Selecione o cliente",
        options=df_clientes["id"].tolist(),
        format_func=lambda x: df_clientes.loc[df_clientes["id"] == x, "nome"].values[0]
    )

    atual = df_query("""
        SELECT id, nome, documento, telefone, email, endereco, COALESCE(cliente_fixo,0) as cliente_fixo
        FROM clientes
        WHERE id=?
    """, (int(cliente_id),))

    if atual.empty:
        st.warning("Cliente não encontrado.")
        st.stop()

    a = atual.iloc[0].to_dict()

    # Mostra quantas locações ele tem (pra bloquear exclusão se tiver)
    qtd_locs = df_query("SELECT COUNT(*) as n FROM locacoes WHERE cliente_id=?", (int(cliente_id),))["n"][0]
    qtd_locs = int(qtd_locs or 0)

    st.caption(f"Este cliente tem **{qtd_locs}** locação(ões) cadastrada(s).")

    col1, col2 = st.columns([2, 1])

    with col1:
        with st.form("form_editar_cliente"):
            nome_e = st.text_input("Nome/Razão Social", value=str(a.get("nome") or ""))
            documento_e = st.text_input("CPF/CNPJ", value=str(a.get("documento") or ""))
            telefone_e = st.text_input("Telefone", value=str(a.get("telefone") or ""))
            email_e = st.text_input("E-mail", value=str(a.get("email") or ""))
            endereco_e = st.text_area("Endereço", value=str(a.get("endereco") or ""))
            fixo_e = st.checkbox("Cliente fixo (recorrente)", value=(int(a.get("cliente_fixo") or 0) == 1))

            salvar_alt = st.form_submit_button("Salvar alterações")

        if salvar_alt:
            if not (nome_e or "").strip():
                st.error("Nome não pode ficar vazio.")
            else:
                exec_sql("""
                    UPDATE clientes
                    SET nome=?, documento=?, telefone=?, email=?, endereco=?, cliente_fixo=?
                    WHERE id=?
                """, (nome_e, documento_e, telefone_e, email_e, endereco_e, 1 if fixo_e else 0, int(cliente_id)))
                st.success("Cliente atualizado com sucesso!")
                st.rerun()

    with col2:
        st.markdown("#### Excluir")
        st.warning("A exclusão é permanente.")

        if qtd_locs > 0:
            st.info("Não dá pra excluir porque este cliente já tem locações. (Segurança)")
        else:
            confirm = st.checkbox("Confirmo que quero excluir este cliente")
            if st.button("🗑️ Excluir cliente", disabled=not confirm):
                exec_sql("DELETE FROM clientes WHERE id=?", (int(cliente_id),))
                st.success("Cliente excluído com sucesso!")
                st.rerun()


# =========================
# MÁQUINAS
# =========================
elif menu == "Máquinas":
    st.subheader("Máquinas / Equipamentos (por tipo + quantidade)")

    if "maquina_salva" not in st.session_state:
        st.session_state.maquina_salva = False
    if "ultima_maquina_id" not in st.session_state:
        st.session_state.ultima_maquina_id = None

    df_maquinas = df_query("""
        SELECT id, codigo, descricao, categoria,
               quantidade_total, quantidade_manutencao, quantidade_disponivel,
               valor_diaria, valor_mensal, observacoes
        FROM maquinas
        ORDER BY descricao
    """)

    st.dataframe(df_maquinas, use_container_width=True)
    st.divider()

    if st.session_state.maquina_salva:
        st.success(f"Máquina salva com sucesso! Nº {st.session_state.ultima_maquina_id}")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Sim, cadastrar outra máquina"):
                for k in list(st.session_state.keys()):
                    if k.startswith("mq_"):
                        del st.session_state[k]
                st.session_state.maquina_salva = False
                st.session_state.ultima_maquina_id = None
                st.rerun()
        with c2:
            if st.button("➡️ Não, voltar para lista"):
                st.session_state.maquina_salva = False
                st.session_state.ultima_maquina_id = None
                st.rerun()
        st.stop()

    with st.expander("➕ Cadastrar novo tipo de máquina", expanded=True):
        with st.form("form_maquina_nova", clear_on_submit=False):
            codigo = st.text_input("Código (opcional)", key="mq_codigo")
            descricao = st.text_input("Descrição (ex: Betoneira 400L)", key="mq_descricao")
            categoria = st.text_input("Categoria (ex: Concretagem)", key="mq_categoria")

            c1, c2 = st.columns(2)
            with c1:
                valor_diaria = st.number_input("Valor Diária (R$)", min_value=0.0, step=10.0, key="mq_valor_diaria")
            with c2:
                valor_mensal = st.number_input("Valor Mensal (R$)", min_value=0.0, step=50.0, key="mq_valor_mensal")

            c3, c4 = st.columns(2)
            with c3:
                quantidade_total = st.number_input("Quantidade total", min_value=1, step=1, value=1, key="mq_qtd_total")
            with c4:
                quantidade_manutencao = st.number_input("Em manutenção", min_value=0, step=1, value=0, key="mq_qtd_manut")

            observacoes = st.text_area("Observações", key="mq_obs")
            salvar_maquina = st.form_submit_button("Salvar Máquina")

        if salvar_maquina:
            if not (descricao or "").strip():
                st.error("Informe a descrição.")
            else:
                qtd_total = int(quantidade_total)
                qtd_manut = int(quantidade_manutencao)
                if qtd_manut > qtd_total:
                    st.error("Em manutenção não pode ser maior que a quantidade total.")
                else:
                    qtd_disp = max(0, qtd_total - qtd_manut)
                    exec_sql("""
                        INSERT INTO maquinas (codigo, descricao, categoria, valor_diaria, valor_mensal,
                                              quantidade_total, quantidade_manutencao, quantidade_disponivel, observacoes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (codigo, descricao, categoria, float(valor_diaria), float(valor_mensal),
                          qtd_total, qtd_manut, qtd_disp, observacoes))

                    mid = int(df_query("SELECT last_insert_rowid() as id")["id"][0])
                    recalcular_disponivel_por_uso(mid)

                    st.session_state.maquina_salva = True
                    st.session_state.ultima_maquina_id = mid
                    st.rerun()

    st.divider()
    with st.expander("✏️ Editar máquina cadastrada", expanded=False):
        if df_maquinas.empty:
            st.info("Cadastre pelo menos 1 máquina para editar.")
        else:
            mid = st.selectbox(
                "Selecione a máquina",
                options=df_maquinas["id"].tolist(),
                format_func=lambda x: df_maquinas.loc[df_maquinas["id"] == x, "descricao"].values[0],
                key="ed_maquina_id"
            )

            m = df_query("""
                SELECT id, codigo, descricao, categoria, valor_diaria, valor_mensal,
                       quantidade_total, quantidade_manutencao, observacoes
                FROM maquinas WHERE id=?
            """, (int(mid),))

            if not m.empty:
                kpref = f"ed_{int(mid)}_"
                with st.form(f"form_editar_{mid}", clear_on_submit=False):
                    codigo_e = st.text_input("Código", value=str(m.loc[0, "codigo"] or ""), key=kpref + "codigo")
                    descricao_e = st.text_input("Descrição", value=str(m.loc[0, "descricao"] or ""), key=kpref + "descricao")
                    categoria_e = st.text_input("Categoria", value=str(m.loc[0, "categoria"] or ""), key=kpref + "categoria")

                    c1, c2 = st.columns(2)
                    with c1:
                        diaria_e = st.number_input(
                            "Valor Diária (R$)", min_value=0.0, step=10.0,
                            value=float(m.loc[0, "valor_diaria"] or 0.0),
                            key=kpref + "diaria"
                        )
                    with c2:
                        mensal_e = st.number_input(
                            "Valor Mensal (R$)", min_value=0.0, step=50.0,
                            value=float(m.loc[0, "valor_mensal"] or 0.0),
                            key=kpref + "mensal"
                        )

                    c3, c4 = st.columns(2)
                    with c3:
                        total_e = st.number_input(
                            "Quantidade total", min_value=1, step=1,
                            value=int(m.loc[0, "quantidade_total"] or 1),
                            key=kpref + "total"
                        )
                    with c4:
                        manut_e = st.number_input(
                            "Em manutenção", min_value=0, step=1,
                            value=int(m.loc[0, "quantidade_manutencao"] or 0),
                            key=kpref + "manut"
                        )

                    obs_e = st.text_area("Observações", value=str(m.loc[0, "observacoes"] or ""), key=kpref + "obs")
                    salvar_edicao = st.form_submit_button("Salvar Alterações")

                if salvar_edicao:
                    if not (descricao_e or "").strip():
                        st.error("Descrição não pode ficar vazia.")
                    elif int(manut_e) > int(total_e):
                        st.error("Em manutenção não pode ser maior que a quantidade total.")
                    else:
                        exec_sql("""
                            UPDATE maquinas
                            SET codigo=?, descricao=?, categoria=?,
                                valor_diaria=?, valor_mensal=?,
                                quantidade_total=?, quantidade_manutencao=?,
                                observacoes=?
                            WHERE id=?
                        """, (codigo_e, descricao_e, categoria_e,
                              float(diaria_e), float(mensal_e),
                              int(total_e), int(manut_e),
                              obs_e, int(mid)))

                        recalcular_disponivel_por_uso(int(mid))
                        st.success("Máquina atualizada com sucesso!")
                        st.rerun()

# =========================
# NOVA LOCAÇÃO
# =========================
elif menu == "Nova Locação":
    section_title("🧾 Nova Locação")
    card_open()

    if "locacao_salva" not in st.session_state:
        st.session_state.locacao_salva = False
    if "ultimo_loc_id" not in st.session_state:
        st.session_state.ultimo_loc_id = None

    clientes = df_query("SELECT id, nome FROM clientes ORDER BY nome")
    maquinas = df_query("""
        SELECT id, descricao, categoria, valor_diaria, valor_mensal,
               quantidade_disponivel
        FROM maquinas
        ORDER BY descricao
    """)

    if clientes.empty:
        st.warning("Cadastre um cliente primeiro (Menu > Clientes).")
    elif maquinas.empty:
        st.warning("Cadastre pelo menos 1 tipo de máquina (Menu > Máquinas).")
    else:
        if st.session_state.locacao_salva:
            st.success(f"Locação salva com sucesso! Nº {st.session_state.ultimo_loc_id}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Sim, cadastrar outra locação"):
                    for k in list(st.session_state.keys()):
                        if k.startswith("nl_") or k.startswith("qtd_"):
                            del st.session_state[k]
                    st.session_state.locacao_salva = False
                    st.session_state.ultimo_loc_id = None
                    st.rerun()
            with c2:
                if st.button("➡️ Não, ir para Locações (abertas)"):
                    st.session_state.locacao_salva = False
                    st.session_state.ultimo_loc_id = None
                    st.session_state.goto_menu = "Locações (abertas)"
                    st.rerun()
            st.stop()

        with st.form("form_nova_locacao", clear_on_submit=False):
            c1, c2 = st.columns([1, 1])
            with c1:
                cliente_id = st.selectbox(
                    "Cliente",
                    options=clientes["id"].tolist(),
                    format_func=lambda x: clientes.loc[clientes["id"] == x, "nome"].values[0],
                    key="nl_cliente_id"
                )
                data_inicio = st.date_input("Data início", value=date.today(), key="nl_data_inicio")
                modo_cobranca = st.selectbox("Cobrança", ["Diária", "Mensal"], key="nl_modo_cobranca")
            with c2:
                frete_ida = st.number_input("Frete ida (R$)", min_value=0.0, step=10.0, value=0.0, key="nl_frete_ida")
                frete_volta = st.number_input("Frete volta (R$)", min_value=0.0, step=10.0, value=0.0, key="nl_frete_volta")
                desconto = st.number_input("Desconto (R$)", min_value=0.0, step=10.0, value=0.0, key="nl_desconto")
                observacoes = st.text_area("Observações", key="nl_observacoes")

            st.divider()
            st.write("Selecione as máquinas e quantidade (só aparece o que tem disponível):")

            itens = []
            for _, row in maquinas.iterrows():
                mid = int(row["id"])
                disp = int(row["quantidade_disponivel"] or 0)
                if disp <= 0:
                    continue

                descricao = row["descricao"]
                cat = row["categoria"] if row["categoria"] else "-"
                vd = float(row["valor_diaria"] or 0)
                vm = float(row["valor_mensal"] or 0)

                colx1, colx2, colx3, colx4 = st.columns([3, 2, 2, 2])
                with colx1:
                    st.write(f"**{descricao}**  \nCategoria: {cat}")
                with colx2:
                    st.write(f"Disponível: **{disp}**")
                with colx3:
                    st.write(f"Diária: **{money(vd)}**  \nMensal: **{money(vm)}**")
                with colx4:
                    qtd = st.number_input("Qtd", min_value=0, max_value=disp, step=1, value=0, key=f"qtd_{mid}")

                if qtd > 0:
                    itens.append({
                        "maquina_id": mid,
                        "descricao": descricao,
                        "quantidade": int(qtd),
                        "valor_diaria": vd,
                        "valor_mensal": vm
                    })

            st.divider()
            st.write("Resumo (o total será calculado no fechamento):")
            if itens:
                st.dataframe(pd.DataFrame([{"Máquina": i["descricao"], "Qtd": i["quantidade"]} for i in itens]),
                             use_container_width=True)
            else:
                st.info("Selecione pelo menos 1 máquina (quantidade maior que 0).")

            salvar = st.form_submit_button("Salvar Locação")

        if salvar:
            if not itens:
                st.error("Selecione pelo menos 1 máquina (quantidade maior que 0).")
            else:
                criado_em = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                exec_sql("""
                    INSERT INTO locacoes (cliente_id, data_inicio, status, modo_cobranca,
                                          frete_ida, frete_volta, desconto, observacoes, criado_em, pago)
                    VALUES (?, ?, 'Em andamento', ?, ?, ?, ?, ?, ?, 0)
                """, (
                    int(cliente_id),
                    to_iso(data_inicio),
                    modo_cobranca,
                    float(frete_ida),
                    float(frete_volta),
                    float(desconto),
                    observacoes,
                    criado_em
                ))

                loc_id = int(df_query("SELECT last_insert_rowid() as id")["id"][0])

                for i in itens:
                    exec_sql("""
                        INSERT INTO locacao_itens (locacao_id, maquina_id, quantidade, valor_diaria, valor_mensal)
                        VALUES (?, ?, ?, ?, ?)
                    """, (loc_id, int(i["maquina_id"]), int(i["quantidade"]),
                          float(i["valor_diaria"]), float(i["valor_mensal"])))

                recalcular_disponivel_todas()
                st.session_state.locacao_salva = True
                st.session_state.ultimo_loc_id = loc_id
                st.rerun()

# =========================
# LOCAÇÕES ABERTAS (FECHAR 1 ou FECHAR TODAS DO CLIENTE FIXO)
# =========================
elif menu == "Locações (abertas)":
    st.subheader("Locações Abertas (Em andamento)")

    if "mostrar_fechar_locacao" not in st.session_state:
        st.session_state.mostrar_fechar_locacao = False

    abertas = df_query("""
        SELECT l.id,
               c.nome as cliente,
               l.data_inicio,
               l.modo_cobranca,
               COALESCE(c.cliente_fixo,0) as cliente_fixo,
               l.cliente_id
        FROM locacoes l
        JOIN clientes c ON c.id = l.cliente_id
        WHERE l.status = 'Em andamento'
        ORDER BY l.id DESC
    """)

    if abertas.empty:
        st.info("Não há locações abertas no momento.")
    else:
        show = abertas[["id", "cliente", "data_inicio", "modo_cobranca", "cliente_fixo"]].copy()
        show.rename(columns={
            "id": "Locação",
            "cliente": "Cliente",
            "data_inicio": "Início",
            "modo_cobranca": "Cobrança",
            "cliente_fixo": "Cliente fixo"
        }, inplace=True)
        show["Cliente fixo"] = show["Cliente fixo"].apply(lambda x: "SIM" if int(x) == 1 else "NÃO")
        st.dataframe(show, use_container_width=True)

        st.divider()

        label_btn = "🔒 Abrir fechamento" if not st.session_state.mostrar_fechar_locacao else "🔓 Fechar tela de fechamento"
        if st.button(label_btn):
            st.session_state.mostrar_fechar_locacao = not st.session_state.mostrar_fechar_locacao
            st.rerun()

        if st.session_state.mostrar_fechar_locacao:
            st.markdown("### Fechar 1 locação")

            escolha = st.selectbox(
                "Selecione a locação aberta",
                options=abertas["id"].tolist(),
                format_func=lambda x: f"Locação {x} - {abertas.loc[abertas['id']==x,'cliente'].values[0]}",
                key="fechar_uma_loc"
            )

            loc = df_query("""
                SELECT l.id, l.cliente_id, c.nome as cliente, COALESCE(c.cliente_fixo,0) as cliente_fixo,
                       l.data_inicio, l.modo_cobranca
                FROM locacoes l
                JOIN clientes c ON c.id = l.cliente_id
                WHERE l.id=?
            """, (int(escolha),))

            cliente_fixo = int(loc.loc[0, "cliente_fixo"] or 0) == 1 if not loc.empty else False
            st.caption(f"Cliente fixo: {'SIM' if cliente_fixo else 'NÃO'}")

            itens = df_query("""
                SELECT m.descricao, li.quantidade
                FROM locacao_itens li
                JOIN maquinas m ON m.id = li.maquina_id
                WHERE li.locacao_id=?
            """, (int(escolha),))

            if not itens.empty:
                st.write("Itens:")
                st.dataframe(itens, use_container_width=True)

            data_fech = st.date_input("Data de fechamento (pode ser pra trás)", value=date.today(), key="data_fech_uma")

            calc = calcular_total_locacao(int(escolha), data_fech)
            if calc.get("erro"):
                st.error(calc["erro"])
            else:
                st.write(f"**Cobrança:** {calc['modo']}")
                st.write(f"**Período cobrado:** {calc['periodo']} {'mes(es)' if calc['modo']=='Mensal' else 'dia(s)'}")
                st.metric("Total geral (no fechamento)", money(calc["total_geral"]))
                st.dataframe(pd.DataFrame(calc["detalhes"]), use_container_width=True)

                modo_reabrir = st.radio(
                    "Reabrir como?",
                    ["Mesmo dia", "Dia seguinte"],
                    index=0,
                    horizontal=True,
                    key="modo_reabrir_uma"
                )
                reabrir_dia_seguinte = (modo_reabrir == "Dia seguinte")
                reabrir = st.checkbox("✅ Fechar e reabrir igual (mesmos itens/quantidades)", value=cliente_fixo, key="chk_reabrir_uma")

                cA, cB = st.columns(2)
                with cA:
                    if st.button("Confirmar Fechamento", key="btn_fechar_uma"):
                        res = fechar_locacao(int(escolha), data_fech)
                        if res.get("erro"):
                            st.error(res["erro"])
                        else:
                            st.success("Locação fechada com sucesso! Foi para o Financeiro.")

                            # PDF da locação fechada (nota/recibo)
                            try:
                                pdf_bytes, pdf_name = gerar_pdf_locacao(int(escolha))
                                st.download_button(
                                    "⬇️ Baixar PDF da locação (nota/recibo)",
                                    data=pdf_bytes,
                                    file_name=pdf_name,
                                    mime="application/pdf"
                                )
                            except Exception as e:
                                st.warning(f"Fechou, mas não conseguiu gerar o PDF: {e}")

                            st.session_state.mostrar_fechar_locacao = False

                with cB:
                    if st.button("Confirmar Fechamento + Reabrir", key="btn_fechar_reabrir_uma"):
                        if not reabrir:
                            st.warning("Marque a opção de reabrir igual para usar este botão.")
                        else:
                            res = fechar_locacao(int(escolha), data_fech)
                            if res.get("erro"):
                                st.error(res["erro"])
                            else:
                                nova_data = data_fech + timedelta(days=1) if reabrir_dia_seguinte else data_fech
                                try:
                                    novo_id = reabrir_locacao_mesmos_itens(int(escolha), nova_data)
                                    st.success(f"Fechada e reaberta! Nova locação: Nº {novo_id} (início {to_iso(nova_data)})")

                                    # PDF da locação FECHADA (nota/recibo)
                                    try:
                                        pdf_bytes, pdf_name = gerar_pdf_locacao(int(escolha))
                                        st.download_button(
                                            "⬇️ Baixar PDF da locação fechada (nota/recibo)",
                                            data=pdf_bytes,
                                            file_name=pdf_name,
                                            mime="application/pdf"
                                        )
                                    except Exception as e:
                                        st.warning(f"Fechou, mas não conseguiu gerar o PDF: {e}")

                                    st.session_state.mostrar_fechar_locacao = False
                                except Exception as e:
                                    st.error(f"Fechou, mas não conseguiu reabrir: {e}")

            st.divider()

            st.markdown("### Fechar TODAS as locações do cliente fixo e reabrir (1 clique)")

            fixos_abertos = df_query("""
                SELECT DISTINCT c.id, c.nome
                FROM clientes c
                JOIN locacoes l ON l.cliente_id = c.id
                WHERE COALESCE(c.cliente_fixo,0)=1
                  AND l.status='Em andamento'
                ORDER BY c.nome
            """)

            if fixos_abertos.empty:
                st.info("Nenhum cliente fixo com locações abertas no momento.")
            else:
                cliente_sel = st.selectbox(
                    "Cliente fixo",
                    options=fixos_abertos["id"].tolist(),
                    format_func=lambda x: fixos_abertos.loc[fixos_abertos["id"] == x, "nome"].values[0],
                    key="cliente_fixo_sel"
                )

                locs_cliente = df_query("""
                    SELECT l.id, l.data_inicio, l.modo_cobranca
                    FROM locacoes l
                    WHERE l.status='Em andamento' AND l.cliente_id=?
                    ORDER BY l.id
                """, (int(cliente_sel),))
                st.write("Locações que serão fechadas e reabertas:")
                st.dataframe(locs_cliente, use_container_width=True)

                data_fech_todas = st.date_input("Data de fechamento (para todas)", value=date.today(), key="data_fech_todas")

                modo_reabrir_todas = st.radio(
                    "Reabrir todas como?",
                    ["Mesmo dia", "Dia seguinte"],
                    index=0,
                    horizontal=True,
                    key="modo_reabrir_todas"
                )
                reabrir_dia_seguinte_todas = (modo_reabrir_todas == "Dia seguinte")

                if st.button("✅ Fechar TODAS e Reabrir", key="btn_fechar_todas_reabrir"):
                    res = fechar_e_reabrir_todas_cliente(
                        int(cliente_sel),
                        data_fech_todas,
                        reabrir_dia_seguinte_todas
                    )
                    if res.get("erro"):
                        st.error(res["erro"])
                    else:
                        st.success(
                            f"Concluído! Fechadas: {len(res['fechadas'])} | Reabertas: {len(res['reabertas'])} | "
                            f"Início das reabertas: {to_iso(res['nova_data'])}"
                        )

                        # PDFs (opcional): gerar um por locação fechada, com botões de download
                        st.info("PDFs das locações fechadas (nota/recibo):")
                        for loc_id_fechada in res["fechadas"]:
                            try:
                                pdf_bytes, pdf_name = gerar_pdf_locacao(int(loc_id_fechada))
                                st.download_button(
                                    f"⬇️ Baixar PDF - Locação {loc_id_fechada}",
                                    data=pdf_bytes,
                                    file_name=pdf_name,
                                    mime="application/pdf",
                                    key=f"pdf_lote_{loc_id_fechada}"
                                )
                            except Exception as e:
                                st.warning(f"Locação {loc_id_fechada}: não deu para gerar PDF ({e})")

                        st.session_state.mostrar_fechar_locacao = False

# =========================
# FINANCEIRO
# =========================
elif menu == "Financeiro":
    section_title("💰 Financeiro (Locações fechadas)")
    card_open()

    ids_fechadas = df_query("SELECT id FROM locacoes WHERE status='Finalizado'")
    for _id in ids_fechadas["id"].tolist():
        atualizar_pago(int(_id))

    filtro = st.selectbox("Filtrar", ["Todas", "Pagas", "Em aberto"])

    base = df_query("""
        SELECT l.id,
               c.nome as cliente,
               l.data_inicio,
               l.data_fim_real,
               l.total_final,
               l.pago
        FROM locacoes l
        JOIN clientes c ON c.id = l.cliente_id
        WHERE l.status = 'Finalizado'
        ORDER BY l.id DESC
    """)

    if base.empty:
        st.info("Ainda não há locações fechadas.")
    else:
        receb = df_query("""
            SELECT locacao_id, COALESCE(SUM(valor),0) as recebido
            FROM recebimentos
            GROUP BY locacao_id
        """)
        base = base.merge(receb, how="left", left_on="id", right_on="locacao_id")
        base["recebido"] = base.get("recebido", 0).fillna(0).astype(float)
        base["saldo"] = base["total_final"].astype(float) - base["recebido"]
        base["status_pagamento"] = base["pago"].apply(lambda x: "PAGA" if int(x) == 1 else "EM ABERTO")

        if filtro == "Pagas":
            base = base[base["pago"] == 1]
        elif filtro == "Em aberto":
            base = base[base["pago"] == 0]

        mostrar = base[["id", "cliente", "data_inicio", "data_fim_real", "total_final", "recebido", "saldo", "status_pagamento"]].copy()
        mostrar.rename(columns={
            "id": "Locação",
            "cliente": "Cliente",
            "data_inicio": "Início",
            "data_fim_real": "Fechamento",
            "total_final": "Total",
            "recebido": "Recebido",
            "saldo": "Saldo",
            "status_pagamento": "Pagamento"
        }, inplace=True)

        st.dataframe(mostrar, use_container_width=True)

        st.divider()
        st.subheader("Registrar recebimento (para locação fechada)")

        fechadas_ids = mostrar["Locação"].tolist()
        if not fechadas_ids:
            st.info("Nenhuma locação para receber neste filtro.")
        else:
            loc_id = st.selectbox("Locação", options=fechadas_ids)

            resumo = df_query("""
                SELECT l.id, c.nome as cliente, l.total_final, l.pago
                FROM locacoes l
                JOIN clientes c ON c.id = l.cliente_id
                WHERE l.id=?
            """, (int(loc_id),))
            if not resumo.empty:
                total = float(resumo.loc[0, "total_final"] or 0)
                recebido = soma_recebida(int(loc_id))
                saldo = total - recebido
                st.write(f"Cliente: **{resumo.loc[0,'cliente']}**")
                st.write(f"Total: **{money(total)}** | Recebido: **{money(recebido)}** | Saldo: **{money(saldo)}**")

            data_pag = st.date_input("Data pagamento", value=date.today())
            forma = st.selectbox("Forma", ["Dinheiro", "Pix", "Cartão", "Boleto", "Transferência"])
            valor = st.number_input("Valor (R$)", min_value=0.0, step=10.0, value=0.0)
            obs = st.text_input("Obs (opcional)")

            if st.button("Salvar Recebimento"):
                if valor <= 0:
                    st.error("Informe um valor maior que zero.")
                else:
                    exec_sql("""
                        INSERT INTO recebimentos (locacao_id, data_pagamento, forma, valor, observacoes)
                        VALUES (?, ?, ?, ?, ?)
                    """, (int(loc_id), to_iso(data_pag), forma, float(valor), obs))

                    atualizar_pago(int(loc_id))
                    st.success("Recebimento salvo! Pagamento atualizado automaticamente.")
                    st.rerun()

        st.divider()
        st.subheader("Recebimentos registrados")
        st.dataframe(df_query("""
            SELECT r.id, r.locacao_id, r.data_pagamento, r.forma, r.valor, r.observacoes
            FROM recebimentos r
            ORDER BY r.id DESC
        """), use_container_width=True)

# =========================
# RELATÓRIOS (MENSAL + PICO + COMPARATIVO + PDF)
# =========================
elif menu == "Relatórios":
    st.subheader("Relatório Mensal")

    hoje = date.today()

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        mes = st.selectbox("Mês", list(range(1, 13)), index=hoje.month - 1)
    with c2:
        anos = list(range(hoje.year - 5, hoje.year + 1))
        ano = st.selectbox("Ano", anos, index=len(anos) - 1)
    with c3:
        considerar_ate_hoje = st.checkbox(
            "Se for o mês atual, considerar somente até hoje (evita projeção até o fim do mês)",
            value=True
        )

    inicio_mes = date(ano, mes, 1)
    fim_mes = last_day_of_month(ano, mes)

    fim_analise = fim_mes
    if considerar_ate_hoje and (ano == hoje.year and mes == hoje.month):
        fim_analise = hoje

    st.caption(f"Período do relatório: {inicio_mes.strftime('%d/%m/%Y')} até {fim_analise.strftime('%d/%m/%Y')}")

    st.divider()

    # 1) Máquinas no mês
    st.markdown("### 1) Máquinas alugadas no mês (quantidade e valor estimado)")
    resumo = calcular_estimada_por_maquina_no_periodo(inicio_mes, fim_analise)

    if resumo.empty:
        st.info("Nenhuma locação com itens no período selecionado.")
        previsto_mes = 0.0
    else:
        previsto_mes = float(resumo["valor_estimado"].sum())

        colA, colB, colC = st.columns(3)
        colA.metric("Tipos de máquinas no mês", int(resumo.shape[0]))
        colB.metric("Qtd (somada) no mês", int(resumo["qtd_total"].sum()))
        colC.metric("Valor estimado do mês", money(previsto_mes))

        resumo_show = resumo.copy()
        resumo_show.rename(columns={
            "descricao": "Máquina",
            "qtd_total": "Quantidade (somada)",
            "valor_estimado": "Valor estimado (R$)"
        }, inplace=True)

        st.dataframe(resumo_show.sort_values("Valor estimado (R$)", ascending=False), use_container_width=True)

        st.download_button(
            "⬇️ Baixar CSV - Máquinas no mês",
            data=resumo_show.to_csv(index=False).encode("utf-8"),
            file_name=f"relatorio_maquinas_mes_{ano}_{mes:02d}.csv",
            mime="text/csv"
        )

    st.divider()

    # 1.1) Pico do mês
    st.markdown("### 1.1) Pico do mês: máximo simultâneo por máquina")
    pico = max_simultaneo_no_periodo(inicio_mes, fim_analise)

    if pico.empty:
        st.info("Sem dados suficientes para calcular o pico do mês.")
    else:
        pico_show = pico.copy()
        pico_show.rename(columns={
            "descricao": "Máquina",
            "pico_simultaneo": "Pico simultâneo (máx)"
        }, inplace=True)
        st.dataframe(pico_show, use_container_width=True)

        st.download_button(
            "⬇️ Baixar CSV - Pico simultâneo",
            data=pico_show.to_csv(index=False).encode("utf-8"),
            file_name=f"pico_simultaneo_{ano}_{mes:02d}.csv",
            mime="text/csv"
        )

    st.divider()

    # 2) Situação atual
    st.markdown("### 2) Situação atual por máquina (alugadas agora x disponíveis)")

    alugadas_agora = df_query("""
        SELECT li.maquina_id, COALESCE(SUM(li.quantidade),0) as alugadas
        FROM locacao_itens li
        JOIN locacoes l ON l.id = li.locacao_id
        WHERE l.status='Em andamento'
        GROUP BY li.maquina_id
    """)

    maq = df_query("""
        SELECT id, descricao, categoria,
               quantidade_total, quantidade_manutencao, quantidade_disponivel,
               valor_diaria, valor_mensal
        FROM maquinas
        ORDER BY descricao
    """)

    if maq.empty:
        st.info("Nenhuma máquina cadastrada.")
        rel_show = pd.DataFrame(columns=["Máquina", "Total", "Manutenção", "Alugadas agora", "Disponíveis", "Diária", "Mensal", "Categoria"])
    else:
        rel = maq.merge(alugadas_agora, how="left", left_on="id", right_on="maquina_id")
        rel["alugadas"] = rel["alugadas"].fillna(0).astype(int)
        rel["quantidade_total"] = rel["quantidade_total"].fillna(0).astype(int)
        rel["quantidade_manutencao"] = rel["quantidade_manutencao"].fillna(0).astype(int)
        rel["quantidade_disponivel"] = rel["quantidade_disponivel"].fillna(0).astype(int)

        rel_show = rel[[
            "descricao", "categoria",
            "quantidade_total", "quantidade_manutencao", "alugadas", "quantidade_disponivel",
            "valor_diaria", "valor_mensal"
        ]].copy()

        rel_show.rename(columns={
            "descricao": "Máquina",
            "categoria": "Categoria",
            "quantidade_total": "Total",
            "quantidade_manutencao": "Manutenção",
            "alugadas": "Alugadas agora",
            "quantidade_disponivel": "Disponíveis",
            "valor_diaria": "Diária",
            "valor_mensal": "Mensal"
        }, inplace=True)

        st.dataframe(rel_show, use_container_width=True)

        st.download_button(
            "⬇️ Baixar CSV - Situação atual por máquina",
            data=rel_show.to_csv(index=False).encode("utf-8"),
            file_name=f"situacao_maquinas_{hoje.strftime('%Y_%m_%d')}.csv",
            mime="text/csv"
        )

    st.divider()

    # 3) Financeiro do mês
    st.markdown("### 3) Financeiro do mês (recebido x a receber)")

    recebido_mes = recebido_no_mes(inicio_mes, fim_analise)
    faturado_mes = faturado_fechado_no_mes(inicio_mes, fim_analise)

    fechadas_ids = df_query("""
        SELECT id
        FROM locacoes
        WHERE status='Finalizado'
          AND data_fim_real IS NOT NULL
          AND date(data_fim_real) >= date(?)
          AND date(data_fim_real) <= date(?)
    """, (to_iso(inicio_mes), to_iso(fim_analise)))

    recebido_dessas = 0.0
    if not fechadas_ids.empty:
        ids_list = [int(x) for x in fechadas_ids["id"].tolist()]
        if len(ids_list) == 1:
            recebido_dessas = df_query("""
                SELECT COALESCE(SUM(valor),0) as recebido
                FROM recebimentos
                WHERE locacao_id = ?
                  AND date(data_pagamento) <= date(?)
            """, (ids_list[0], to_iso(fim_analise)))["recebido"][0]
        else:
            placeholders = ",".join(["?"] * len(ids_list))
            recebido_dessas = df_query(f"""
                SELECT COALESCE(SUM(valor),0) as recebido
                FROM recebimentos
                WHERE locacao_id IN ({placeholders})
                  AND date(data_pagamento) <= date(?)
            """, (*ids_list, to_iso(fim_analise)))["recebido"][0]

    recebido_dessas = float(recebido_dessas or 0)
    a_receber_mes = float(faturado_mes - recebido_dessas)

    # previsto_mes já calculado acima
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Recebido no mês", money(recebido_mes))
    c2.metric("Faturado (fechadas no mês)", money(faturado_mes))
    c3.metric("A receber (fechadas do mês)", money(a_receber_mes))
    c4.metric("Previsto (abertas + fechadas)", money(previsto_mes))

    st.caption("Obs: 'Previsto' é uma estimativa calculada pelo período de uso dentro do mês (mesmo sem fechar).")

    st.divider()

    # 4) Comparativo mês a mês (12 meses)
    st.markdown("### 4) Comparativo mês a mês (últimos 12 meses)")

    pontos = []
    for i in range(-11, 1):
        a, m = month_add(ano, mes, i)
        ini = date(a, m, 1)
        fim = last_day_of_month(a, m)

        fim_ref = fim
        if considerar_ate_hoje and (a == hoje.year and m == hoje.month):
            fim_ref = hoje

        rec = recebido_no_mes(ini, fim_ref)
        fat = faturado_fechado_no_mes(ini, fim_ref)
        prev_df = calcular_estimada_por_maquina_no_periodo(ini, fim_ref)
        prev = float(prev_df["valor_estimado"].sum()) if not prev_df.empty else 0.0

        pontos.append({
            "Mês": f"{a}-{m:02d}",
            "Recebido": rec,
            "Faturado (fechadas)": fat,
            "Previsto": prev
        })

    serie = pd.DataFrame(pontos).set_index("Mês")
    st.line_chart(serie)

    st.download_button(
        "⬇️ Baixar CSV - Comparativo mês a mês",
        data=serie.reset_index().to_csv(index=False).encode("utf-8"),
        file_name=f"comparativo_12m_{ano}_{mes:02d}.csv",
        mime="text/csv"
    )

    st.divider()

    # 5) PDF do relatório mensal
    st.markdown("### 5) Exportar Relatório Mensal em PDF")

    try:
        pdf_bytes, pdf_name = gerar_pdf_relatorio_mensal(
            ano=ano,
            mes=mes,
            inicio_mes=inicio_mes,
            fim_analise=fim_analise,
            resumo_df=resumo,      # colunas: descricao, qtd_total, valor_estimado
            pico_df=pico,          # colunas: descricao, pico_simultaneo
            situacao_df=rel_show,  # colunas renomeadas (Máquina, Total, ...)
            recebido_mes=recebido_mes,
            faturado_mes=faturado_mes,
            a_receber_mes=a_receber_mes,
            previsto_mes=previsto_mes
        )

        st.download_button(
            "⬇️ Baixar PDF do Relatório Mensal",
            data=pdf_bytes,
            file_name=pdf_name,
            mime="application/pdf"
        )
    except Exception as e:
        st.warning(f"Não foi possível gerar o PDF do relatório: {e}")


# fecha card (segurança)
try:
    card_close()
except Exception:
    pass
