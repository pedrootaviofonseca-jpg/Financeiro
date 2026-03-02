import db_adapter
import streamlit as st
import sqlite3
import pandas as pd
import math
import os
import re
import json
import base64
from datetime import datetime
from typing import Optional, Set, Tuple

from io import BytesIO

# PDF (reportlab)
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="Sistema Engenharia", page_icon="🏗️", layout="wide")

# ==========================================================
# TRAVA DE CÁLCULO (snapshot para PDF)
# ==========================================================
if "calc_locked" not in st.session_state:
  st.session_state.calc_locked = False
if "lock_ctx" not in st.session_state:
  st.session_state.lock_ctx = None
if "lock_time" not in st.session_state:
  st.session_state.lock_time = None
if "snapshot_resultado" not in st.session_state:
  st.session_state.snapshot_resultado = None
if "snapshot_qtd" not in st.session_state:
  st.session_state.snapshot_qtd = None
if "snapshot_arm_por_bitola" not in st.session_state:
  st.session_state.snapshot_arm_por_bitola = None


# ==========================================================
# TRAVA DO FINANCEIRO (snapshot para proposta por obra)
# ==========================================================
if "fin_locked" not in st.session_state:
  st.session_state.fin_locked = False
if "fin_lock_time" not in st.session_state:
  st.session_state.fin_lock_time = None
if "fin_lock_obra_id" not in st.session_state:
  st.session_state.fin_lock_obra_id = None
if "fin_snapshot" not in st.session_state:
  st.session_state.fin_snapshot = None



# ==========================================================
# ESTILO
# ==========================================================
st.markdown("""
<style>

/* ====== FUNDO VERDE CORPORATIVO ====== */
.stApp{
  background: linear-gradient(180deg, #0F3D2E 0%, #145A3A 55%, #1B7A4B 100%);
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

/* Títulos */
h1, h2, h3 { color: #ffffff; }
a { color: #9BE7C4; }

/* Texto principal claro */
div[data-testid="stAppViewContainer"]{
  color: #F1F5F9 !important;
}

/* Labels */
div[data-testid="stAppViewContainer"] label{
  color: #E2F8EC !important;
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
div[data-baseweb="input"] > div{
  background: rgba(255,255,255,0.95) !important;
  border-color: rgba(0,0,0,0.15) !important;
}

/* TEXTO DOS INPUTS */
div[data-testid="stAppViewContainer"] div[data-baseweb="input"] input{
  color: #111827 !important;
}

/* ================= CORREÇÃO SELECTBOX ================= */
/* Força texto preto dentro das listas */
div[data-baseweb="select"] span{
  color: #111827 !important;
}

div[data-baseweb="select"] div{
  color: #111827 !important;
}

div[data-baseweb="select"] input{
  color: #111827 !important;
}

/* ================= BOTÕES ================= */
.stButton > button,
div[data-testid="stFormSubmitButton"] > button{
  background: linear-gradient(180deg, #1E8449, #145A32) !important;
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
  background: linear-gradient(180deg, #1E8449 0%, #145A32 100%) !important;
  color: #ffffff !important;
  font-weight: 700;
}

.wrap-table td{
  border: 1px solid rgba(0,0,0,0.10);
  padding: 10px 12px;
  vertical-align: top;
  color: #111827 !important;
}

/* ================= BARRA DE TÍTULO ================= */
.section-title{
  background: linear-gradient(180deg, #1E8449 0%, #145A32 100%);
  color: #ffffff;
  border-radius: 14px;
  padding: 10px 14px;
  margin: 14px 0 10px 0;
  font-weight: 800;
  box-shadow: 0 8px 18px rgba(0,0,0,0.25);
}

/* ================= BRANDING ================= */
.brandbar{
  background: linear-gradient(90deg, #145A32 0%, #1E8449 55%, #27AE60 100%);
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
# UI — TÍTULOS PADRONIZADOS
# ==========================================================
def section_title(texto: str):
  """Barra azul (texto preto) para destacar seções."""
  st.markdown(f'<div class="section-title">{texto}</div>', unsafe_allow_html=True)

# ==========================================================
# BANCO
# ==========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "banco.db")

def get_conn():
  conn = sqlite3.connect(DB_PATH, check_same_thread=False)
  conn.execute("PRAGMA foreign_keys = ON;")
  return conn

def table_columns(conn, table_name: str) -> Set[str]:
  cur = conn.cursor()
  cur.execute(f"PRAGMA table_info({table_name})")
  return {row[1] for row in cur.fetchall()}

def ensure_schema():
  """Cria tabelas e adiciona colunas novas se faltarem (sem precisar apagar banco)."""
  conn = get_conn()
  cur = conn.cursor()

  # Obras
  cur.execute("""
      CREATE TABLE IF NOT EXISTS obras (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          cliente TEXT NOT NULL,
          obra TEXT NOT NULL,
          endereco TEXT
      )
  """)

  # Lançamentos Piso
  cur.execute("""
      CREATE TABLE IF NOT EXISTS lancamentos_piso (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          obra_id INTEGER NOT NULL,
          laje TEXT NOT NULL,
          tipo_laje TEXT NOT NULL DEFAULT "Piso",
          preenchimento TEXT NOT NULL DEFAULT "EPS",
          vao_livre REAL NOT NULL,
          largura REAL NOT NULL,
          trespasse REAL NOT NULL,
          comprimento_final REAL NOT NULL,
          area_com_trespasse REAL NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY (obra_id) REFERENCES obras(id)
      )
  """)

  # Mantemos colunas de armadura no banco
  cols = table_columns(conn, "lancamentos_piso")
  if "diametro_reforco" not in cols:
      cur.execute("ALTER TABLE lancamentos_piso ADD COLUMN diametro_reforco TEXT")
  if "qtd_reforco" not in cols:
      cur.execute("ALTER TABLE lancamentos_piso ADD COLUMN qtd_reforco REAL")

  # Tipo de Preenchimento (EPS / Lajota)
  if "preenchimento" not in cols:
      cur.execute('ALTER TABLE lancamentos_piso ADD COLUMN preenchimento TEXT NOT NULL DEFAULT "EPS"')


  if "tipo_laje" not in cols:
      cur.execute('ALTER TABLE lancamentos_piso ADD COLUMN tipo_laje TEXT NOT NULL DEFAULT "Piso"')


  # Índice para performance (muitos lançamentos por obra)
  cur.execute("CREATE INDEX IF NOT EXISTS idx_lancamentos_piso_obra_id ON lancamentos_piso(obra_id)")


  # ============================
  # FINANCEIRO — TABELAS / SEED
  # ============================
  cur.execute("""
      CREATE TABLE IF NOT EXISTS precos_materiais (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          material TEXT UNIQUE NOT NULL,
          unidade TEXT,
          valor_unitario REAL NOT NULL DEFAULT 0
      )
  """)

  cur.execute("""
      CREATE TABLE IF NOT EXISTS config_financeiro (
          chave TEXT PRIMARY KEY,
          valor REAL NOT NULL DEFAULT 0
      )
  """)

  # Snapshot do Financeiro (trava por obra)
  cur.execute("""
      CREATE TABLE IF NOT EXISTS financeiro_snapshot (
          obra_id INTEGER PRIMARY KEY,
          locked_at TEXT NOT NULL,
          preco_m2 REAL NOT NULL DEFAULT 0,
          metragem_m2 REAL NOT NULL DEFAULT 0,
          custo_producao REAL NOT NULL DEFAULT 0,
          preco_proposta REAL NOT NULL DEFAULT 0,
          lucro REAL NOT NULL DEFAULT 0,
          itens_json TEXT NOT NULL
      )
  """)


  # Seed de materiais e configs (INSERT OR IGNORE)
  seed_mats = [
      ("Volume de Concreto", "m³", 0.0),
      ("Barras 5.0", "UND", 0.0),
      ("Barras 6.3", "UND", 0.0),
      ("Barras 8.0", "UND", 0.0),
      ("Barras 10.0", "UND", 0.0),
      ("Barras 12.5", "UND", 0.0),
      ("Treliças", "UND", 0.0),
      ("Isopor", "UND", 0.0),
      ("Lajota", "UND", 0.0),
      ("Mão de Obra", "m²", 0.0),
      ("Frete", "UND", 0.0),
      ("Ferragem Negativa", "UND", 0.0),
  ]
  for mat, und, val in seed_mats:
      cur.execute(
          "INSERT OR IGNORE INTO precos_materiais (material, unidade, valor_unitario) VALUES (?, ?, ?)",
          (mat, und, float(val)),
      )

  seed_cfg = [
      ("preco_venda_m2", 0.0),    # R$/m² (preço de venda)
  ]
  for ch, val in seed_cfg:
      cur.execute(
          "INSERT OR IGNORE INTO config_financeiro (chave, valor) VALUES (?, ?)",
          (ch, float(val)),
      )

  conn.commit()
  conn.close()


# ==========================================================
# PDF — PRODUÇÃO
# ==========================================================
def _safe_pdf_name(texto: str) -> str:
  s = str(texto or "").strip()
  s = re.sub(r"[\\/:*?\"<>|]+", "-", s)
  s = re.sub(r"\s+", "_", s)
  s = s.strip(" ._-")
  return s or "producao"

def gerar_pdf_producao(cliente: str, obra: str, endereco: str, df_resultado: pd.DataFrame) -> bytes:
  """Gera PDF para produção com cabeçalho profissional (tons de azul), logo opcional e tabela resumida."""
  styles = getSampleStyleSheet()

  # Paleta (tons de azul)
  AZUL_ESCURO = HexColor("#0B4F8A")
  AZUL_MEDIO  = HexColor("#1E73BE")
  AZUL_CLARO  = HexColor("#EAF2FB")
  CINZA_TEXTO = HexColor("#1F2A37")

  # Estilos de texto
  title_white = ParagraphStyle(
      "title_white",
      parent=styles["Title"],
      textColor=colors.white,
      fontName="Helvetica-Bold",
      fontSize=18,
      leading=22,
      spaceAfter=0,
  )
  sub_white = ParagraphStyle(
      "sub_white",
      parent=styles["Normal"],
      textColor=colors.white,
      fontName="Helvetica",
      fontSize=10,
      leading=12,
  )
  small_grey = ParagraphStyle(
      "small_grey",
      parent=styles["Normal"],
      textColor=CINZA_TEXTO,
      fontName="Helvetica",
      fontSize=9,
      leading=11,
  )

  # Logo opcional (coloque um arquivo logo.png/jpg/jpeg na mesma pasta do .py)
  logo_path = None
  for nm in ("logo.png", "logo.jpg", "logo.jpeg"):
      p = os.path.join(BASE_DIR, nm)
      if os.path.exists(p):
          logo_path = p
          break

  buf = BytesIO()
  doc = SimpleDocTemplate(
      buf,
      pagesize=A4,
      leftMargin=24,
      rightMargin=24,
      topMargin=24,
      bottomMargin=24
  )
  story = []

  # ===== Cabeçalho (faixa azul com logo + título) =====
  if logo_path:
      try:
          logo = Image(logo_path)
          logo.drawHeight = 14 * mm
          logo.drawWidth = 35 * mm
          logo_cell = logo
      except Exception:
          logo_cell = Paragraph("<b>SUA LOGO</b>", sub_white)
  else:
      logo_cell = Paragraph("<b>SUA LOGO</b>", sub_white)

  header_right = [
      Paragraph("<b>ORDEM DE PRODUÇÃO</b>", title_white),
      Paragraph(f"<b>Cliente:</b> {cliente} &nbsp;&nbsp; <b>Obra:</b> {obra}", sub_white),
      Paragraph(f"<b>Endereço:</b> {endereco}", sub_white),
  ]

  header_tbl = Table(
      [[logo_cell, header_right]],
      colWidths=[55 * mm, doc.width - (55 * mm)],
  )
  header_tbl.setStyle(TableStyle([
      ("BACKGROUND", (0, 0), (-1, -1), AZUL_ESCURO),
      ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
      ("LEFTPADDING", (0, 0), (-1, -1), 10),
      ("RIGHTPADDING", (0, 0), (-1, -1), 10),
      ("TOPPADDING", (0, 0), (-1, -1), 10),
      ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
      ("LINEBELOW", (0, 0), (-1, -1), 0.8, AZUL_MEDIO),
  ]))
  story.append(header_tbl)
  story.append(Spacer(1, 12))

  # ===== Tabela (resumo para produção) =====
# ===== Seção: PRODUÇÃO =====
  sec_prod = Table([[Paragraph("<b>PRODUÇÃO</b>", sub_white)]], colWidths=[doc.width])
  sec_prod.setStyle(TableStyle([
      ("BACKGROUND", (0, 0), (-1, -1), AZUL_MEDIO),
      ("LEFTPADDING", (0, 0), (-1, -1), 10),
      ("RIGHTPADDING", (0, 0), (-1, -1), 10),
      ("TOPPADDING", (0, 0), (-1, -1), 6),
      ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
  ]))
  story.append(sec_prod)
  story.append(Spacer(1, 8))

  cols = [
      ("Laje", "Laje"),
      ("Comprimento Final (m)", "Comprimento Final (m)"),
      ("Bitola Armadura de Reforço", "Bitola"),
      ("Quantidade de Armadura de Reforço", "Qtd Arm. Reforço"),
      ("Quantidade de Vigotas", "Qtd Vigotas"),
  ]

  faltando = [c for c, _ in cols if c not in df_resultado.columns]
  if faltando:
      story.append(Paragraph(
          f"<b>Atenção:</b> colunas não encontradas no resultado: {', '.join(faltando)}",
          small_grey
      ))
      story.append(Spacer(1, 8))

  df = df_resultado.copy()

  # Formatação numérica
  if "Comprimento Final (m)" in df.columns:
      df["Comprimento Final (m)"] = pd.to_numeric(df["Comprimento Final (m)"], errors="coerce").fillna(0.0).map(lambda x: f"{x:.2f}")
  if "Quantidade de Vigotas" in df.columns:
      df["Quantidade de Vigotas"] = pd.to_numeric(df["Quantidade de Vigotas"], errors="coerce").fillna(0).astype(int)
  if "Quantidade de Armadura de Reforço" in df.columns:
      df["Quantidade de Armadura de Reforço"] = pd.to_numeric(df["Quantidade de Armadura de Reforço"], errors="coerce").fillna(0.0).map(lambda x: f"{x:.2f}")

  data = [[label for _, label in cols]]
  for _, row in df.iterrows():
      data.append([str(row.get(col, "")) for col, _ in cols])

  table = Table(data, repeatRows=1, hAlign="CENTER")
  table.setStyle(TableStyle([
      ("BACKGROUND", (0, 0), (-1, 0), AZUL_MEDIO),
      ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
      ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
      ("FONTSIZE", (0, 0), (-1, 0), 10),
      ("ALIGN", (0, 0), (-1, 0), "CENTER"),

      ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#AAB8C5")),
      ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
      ("FONTSIZE", (0, 1), (-1, -1), 9),
      ("TEXTCOLOR", (0, 1), (-1, -1), CINZA_TEXTO),

      ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, AZUL_CLARO]),
      ("LEFTPADDING", (0, 0), (-1, -1), 6),
      ("RIGHTPADDING", (0, 0), (-1, -1), 6),
      ("TOPPADDING", (0, 0), (-1, -1), 4),
      ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
  ]))
  story.append(table)
  story.append(Spacer(1, 10))
  # ===== Seção: MATERIAL PARA ENTREGA =====
  story.append(Spacer(1, 6))
  sec_mat = Table([[Paragraph("<b>MATERIAL PARA ENTREGA</b>", sub_white)]], colWidths=[doc.width])
  sec_mat.setStyle(TableStyle([
      ("BACKGROUND", (0, 0), (-1, -1), AZUL_MEDIO),
      ("LEFTPADDING", (0, 0), (-1, -1), 10),
      ("RIGHTPADDING", (0, 0), (-1, -1), 10),
      ("TOPPADDING", (0, 0), (-1, -1), 6),
      ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
  ]))
  story.append(sec_mat)
  story.append(Spacer(1, 8))

  # Monta quantitativo e gera tabela com EPS, Lajotas e Ferragem Negativa
  try:
      df_qtd_entrega, _df_arm_por_bitola = construir_quantitativo(df_resultado)
  except Exception:
      df_qtd_entrega = pd.DataFrame()

  if df_qtd_entrega is None or df_qtd_entrega.empty:
      story.append(Paragraph("Sem dados suficientes para montar o material para entrega.", small_grey))
      story.append(Spacer(1, 6))
  else:
      cols_entrega = [
          ("Laje", "Laje"),
          ("Preenchimento", "Preench."),
          ("Quantidade de EPS", "Qtd EPS"),
          ("Quantidade Lajotas", "Qtd Lajotas"),
          ("Quantidade de Armadura Negativa", "Ferragem Negativa"),
      ]

      df_e = df_qtd_entrega.copy()
      # Garantir colunas
      for c, _ in cols_entrega:
          if c not in df_e.columns:
              df_e[c] = ""

      # Formatar números
      for c in ["Quantidade de EPS", "Quantidade Lajotas"]:
          df_e[c] = pd.to_numeric(df_e[c], errors="coerce").fillna(0).astype(int)
      if "Quantidade de Armadura Negativa" in df_e.columns:
          df_e["Quantidade de Armadura Negativa"] = pd.to_numeric(df_e["Quantidade de Armadura Negativa"], errors="coerce").fillna(0.0).map(lambda x: f"{x:.2f}")

      data_e = [[label for _, label in cols_entrega]]
      for _, row in df_e.iterrows():
          data_e.append([str(row.get(col, "")) for col, _ in cols_entrega])

      tbl_e = Table(data_e, repeatRows=1, hAlign="CENTER")
      tbl_e.setStyle(TableStyle([
          ("BACKGROUND", (0, 0), (-1, 0), AZUL_MEDIO),
          ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
          ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
          ("FONTSIZE", (0, 0), (-1, 0), 10),
          ("ALIGN", (0, 0), (-1, 0), "CENTER"),

          ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#AAB8C5")),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("FONTSIZE", (0, 1), (-1, -1), 9),
          ("TEXTCOLOR", (0, 1), (-1, -1), CINZA_TEXTO),

          ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, AZUL_CLARO]),
          ("LEFTPADDING", (0, 0), (-1, -1), 6),
          ("RIGHTPADDING", (0, 0), (-1, -1), 6),
          ("TOPPADDING", (0, 0), (-1, -1), 4),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
      ]))
      story.append(tbl_e)
      story.append(Spacer(1, 8))

      # Totais (Material para entrega)
      tot_eps = int(pd.to_numeric(df_qtd_entrega.get("Quantidade de EPS", 0), errors="coerce").fillna(0).sum())
      tot_laj = int(pd.to_numeric(df_qtd_entrega.get("Quantidade Lajotas", 0), errors="coerce").fillna(0).sum())
      tot_neg = float(pd.to_numeric(df_qtd_entrega.get("Quantidade de Armadura Negativa", 0), errors="coerce").fillna(0).sum().round(2))

      tot_tbl = Table(
          [[
              Paragraph("<b>Totais</b>", small_grey),
              Paragraph(f"<b>EPS:</b> {tot_eps}", small_grey),
              Paragraph(f"<b>Lajotas:</b> {tot_laj}", small_grey),
              Paragraph(f"<b>Ferragem Negativa:</b> {tot_neg:.2f}", small_grey),
          ]],
          colWidths=[doc.width * 0.18, doc.width * 0.22, doc.width * 0.22, doc.width * 0.38],
      )
      tot_tbl.setStyle(TableStyle([
          ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F3F6FB")),
          ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#D1D9E6")),
          ("LEFTPADDING", (0, 0), (-1, -1), 8),
          ("RIGHTPADDING", (0, 0), (-1, -1), 8),
          ("TOPPADDING", (0, 0), (-1, -1), 6),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
      ]))
      story.append(tot_tbl)
      story.append(Spacer(1, 6))


  # Rodapé com número da página
  def _footer(canvas, doc_):
      canvas.saveState()
      canvas.setFont("Helvetica", 8)
      canvas.setFillColor(HexColor("#6B7280"))
      canvas.drawRightString(doc_.pagesize[0] - doc_.rightMargin, 12, f"Página {canvas.getPageNumber()}")
      canvas.restoreState()

  doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
  return buf.getvalue()

# ==========================================================
# REGRA ARMADURA POR VÃO
# ==========================================================
def armadura_reforco_por_vao(vao: float) -> Tuple[str, float]:
  """Regra conforme a tabela enviada (por faixas de vão)."""
  try:
      v = float(vao)
  except Exception:
      return ("", 0.0)

  if v < 2.0:
      return ("", 0.0)

  if 2.0 <= v < 2.5:
      return ("5.0", 1.0)
  if 2.5 <= v < 3.0:
      return ("5.0", 2.0)
  if 3.0 <= v < 3.5:
      return ("6.3", 2.0)
  if 3.5 <= v < 4.0:
      return ("6.3", 3.0)
  if 4.0 <= v < 4.5:
      return ("8.0", 3.0)
  if 4.5 <= v < 5.0:
      return ("8.0", 4.0)
  if 5.0 <= v < 5.5:
      return ("10.0", 3.0)
  if 5.5 <= v < 6.0:
      return ("12.5", 2.0)

  return ("12.5", 3.0)


def armadura_reforco_forro_por_vao(vao: float) -> Tuple[str, float]:
  """Regra da Laje PARA FORRO (conforme tabela enviada)."""
  try:
      v = float(vao)
  except Exception:
      return ("", 0.0)

  # Abaixo de 3m: sem armadura (tabela mostra "-")
  if v < 3.0:
      return ("", 0.0)

  if 3.0 <= v < 3.5:
      return ("5.0", 1.0)
  if 3.5 <= v < 4.0:
      return ("5.0", 2.0)
  if 4.0 <= v < 4.5:
      return ("6.3", 2.0)
  if 4.5 <= v < 5.0:
      return ("6.3", 3.0)
  if 5.0 <= v < 5.5:
      return ("6.3", 4.0)
  if 5.5 <= v < 6.0:
      return ("8.0", 3.0)

  # 6.0m ou mais
  return ("10.0", 3.0)


def armadura_reforco_por_tipo(vao: float, tipo_laje: str) -> Tuple[str, float]:
  """Escolhe regra de armadura conforme o tipo (Piso/Forro)."""
  t = (tipo_laje or "").strip().lower()
  if t.startswith("forro"):
      return armadura_reforco_forro_por_vao(vao)
  return armadura_reforco_por_vao(vao)

# ==========================================================
# CRUD OBRAS
# ==========================================================
def inserir_obra(cliente, obra, endereco):
  conn = get_conn()
  cur = conn.cursor()
  cur.execute(
      "INSERT INTO obras (cliente, obra, endereco) VALUES (?, ?, ?)",
      (cliente.strip(), obra.strip(), (endereco or "").strip())
  )
  conn.commit()
  conn.close()

def listar_obras_full():
  conn = get_conn()
  df = pd.read_sql_query(
      "SELECT id, cliente, obra, endereco FROM obras ORDER BY id DESC",
      conn
  )
  conn.close()
  return df

def listar_obras_select():
  conn = get_conn()
  df = pd.read_sql_query(
      "SELECT id, cliente, obra FROM obras ORDER BY id DESC",
      conn
  )
  conn.close()
  return df

def obter_obra_por_id(obra_id: int):
  conn = get_conn()
  cur = conn.cursor()
  cur.execute("SELECT id, cliente, obra, endereco FROM obras WHERE id=?", (obra_id,))
  row = cur.fetchone()
  conn.close()
  if not row:
      return None
  return {"id": row[0], "cliente": row[1], "obra": row[2], "endereco": row[3] or ""}

def atualizar_obra(obra_id: int, cliente: str, obra: str, endereco: Optional[str]):
  conn = get_conn()
  cur = conn.cursor()
  cur.execute(
      "UPDATE obras SET cliente=?, obra=?, endereco=? WHERE id=?",
      (cliente.strip(), obra.strip(), (endereco or "").strip(), obra_id),
  )
  conn.commit()
  conn.close()

def excluir_obra(obra_id: int):
  conn = get_conn()
  cur = conn.cursor()
  cur.execute("DELETE FROM lancamentos_piso WHERE obra_id=?", (obra_id,))
  cur.execute("DELETE FROM obras WHERE id=?", (obra_id,))
  conn.commit()
  conn.close()

# ==========================================================
# LANÇAMENTOS PISO
# ==========================================================
def salvar_lancamentos_piso(obra_id: int, df: pd.DataFrame, trespasse: float, tipo_laje: str = "Piso", preenchimento: str = "EPS", substituir: bool = True):
  """Salva no banco e já grava bitola/qtd automaticamente conforme o vão."""
  conn = get_conn()
  cur = conn.cursor()

  if substituir:
      cur.execute("DELETE FROM lancamentos_piso WHERE obra_id=?", (obra_id,))

  now = datetime.now().isoformat(timespec="seconds")

  for _, row in df.iterrows():
      laje = str(row.get("Laje", "")).strip()
      vao = float(row.get("Vão Livre (m)", 0) or 0)
      larg = float(row.get("Largura (m)", 0) or 0)

      bitola, qtd = armadura_reforco_por_tipo(vao, tipo_laje)

      comprimento_final = vao + (trespasse * 2)
      area_com_trespasse = comprimento_final * larg

      cur.execute("""
          INSERT INTO lancamentos_piso
          (obra_id, laje, vao_livre, largura, trespasse,
           comprimento_final, area_com_trespasse,
           tipo_laje, preenchimento, diametro_reforco, qtd_reforco, created_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      """, (
          obra_id, laje, vao, larg, trespasse,
          comprimento_final, area_com_trespasse,
          tipo_laje, (preenchimento or "EPS"), bitola, qtd, now
      ))

  conn.commit()
  conn.close()

def ler_lancamentos_piso(obra_id: int) -> pd.DataFrame:
  """Resultado: mostra bitola e quantidade (sem mostrar 'Salvo em') + Quantidade de Vigotas."""
  conn = get_conn()
  df = pd.read_sql_query("""
      SELECT
          laje AS "Laje",
          tipo_laje AS "Tipo",
          preenchimento AS "Preenchimento",
          vao_livre AS "Vão Livre (m)",
          largura AS "Largura (m)",
          trespasse AS "Trespasse (m)",
          comprimento_final AS "Comprimento Final (m)",
          area_com_trespasse AS "Área com Trespasse",
          diametro_reforco AS "Bitola Armadura de Reforço",
          qtd_reforco AS "Quantidade de Armadura de Reforço"
      FROM lancamentos_piso
      WHERE obra_id=?
      ORDER BY id DESC
  """, conn, params=(obra_id,))
  conn.close()

  # Quantidade de Vigotas = ceil(Largura / 0.43), sempre inteiro arredondado para cima.
  if not df.empty and "Largura (m)" in df.columns:
      larguras = pd.to_numeric(df["Largura (m)"], errors="coerce").fillna(0.0)
      df.insert(
          df.columns.get_loc("Largura (m)") + 1,
          "Quantidade de Vigotas",
          larguras.apply(lambda x: int(max(0, math.ceil(x / 0.43))) if x > 0 else 0)
      )

  return df


# ==========================================================
# QUANTITATIVO (por laje e totais)
# ==========================================================
def construir_quantitativo(df_resultado: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Monta a planilha de quantitativos a partir do Resultado.

    Fórmulas (conforme combinado):
      1) Quantidade de Treliças (UND) = (Qtd Vigotas * Comprimento Final) / 12
      2) Quantitativos de Armadura de Reforço = (Qtd Arm. Reforço * Qtd Vigotas * Comprimento Final) / 12
      3) Quantidade de EPS = ceil((Qtd Vigotas - 1) * Largura)
      4) Quantidade Lajotas = ceil(((Qtd Vigotas - 1) * Largura) / 0,3)
      5) Quantidade de Armadura Negativa = ((Largura / 0,4) * Comprimento Final) / 12
      6) Volume de Concreto = Qtd Vigotas * 0,12 * 0,03 * Comprimento Final (m)
    """
    if df_resultado is None or df_resultado.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = df_resultado.copy()

    # Colunas esperadas no Resultado
    col_laje = "Laje"
    col_comp = "Comprimento Final (m)"  # já inclui trespasse
    col_larg = "Largura (m)"
    col_bitola = "Bitola Armadura de Reforço"
    col_qtd_ref = "Quantidade de Armadura de Reforço"
    col_qtd_vig = "Quantidade de Vigotas"
    col_preench = "Preenchimento"

    for col in [col_laje, col_comp, col_larg, col_bitola, col_qtd_ref, col_qtd_vig, col_preench]:
        if col not in df.columns:
            df[col] = None

    comp = pd.to_numeric(df[col_comp], errors="coerce").fillna(0.0)
    larg = pd.to_numeric(df[col_larg], errors="coerce").fillna(0.0)
    qtd_vig = pd.to_numeric(df[col_qtd_vig], errors="coerce").fillna(0).astype(int)
    qtd_ref = pd.to_numeric(df[col_qtd_ref], errors="coerce").fillna(0.0)

    preench = df[col_preench].astype(str).fillna("EPS").str.strip().str.upper()

    # 1) Treliças (UND)
    qtd_trelicas = ((qtd_vig * comp) / 12.0).round(2)

    # 2) Armadura de Reforço (UND), considerando bitolas (totais depois agrupados)
    qtd_arm_ref = ((qtd_ref * qtd_vig * comp) / 12.0).round(2)

    # 3) EPS (arredondar pra cima) — depende do COMPRIMENTO da laje
    qtd_eps_raw = ((qtd_vig - 1).clip(lower=0) * comp).apply(lambda x: int(math.ceil(x)) if x > 0 else 0)

    # 4) Lajotas (arredondar pra cima) — depende do COMPRIMENTO da laje
    qtd_lajotas_raw = (((qtd_vig - 1).clip(lower=0) * comp) / 0.3).apply(lambda x: int(math.ceil(x)) if x > 0 else 0)

    # Regra: escolhe o tipo de preenchimento (EPS ou LAJOTA). Um zera o outro.
    is_eps = preench.eq("EPS")
    is_laj = preench.isin(["LAJOTA", "LAJOTAS"])

    qtd_eps = qtd_eps_raw.where(is_eps, 0)
    qtd_lajotas = qtd_lajotas_raw.where(is_laj, 0)

    # 5) Armadura Negativa
    qtd_arm_neg = (((larg / 0.4) * comp) / 12.0).round(2)

    # 6) Volume de concreto
    vol_conc = (qtd_vig * 0.12 * 0.03 * comp).round(4)

    df_qtd = pd.DataFrame({
        "Laje": df[col_laje].astype(str),
        "Preenchimento": preench,
        "Quantidade de Treliças": qtd_trelicas,
        "Quantitativos de Armadura de Reforço": qtd_arm_ref,
        "Quantidade de EPS": qtd_eps,
        "Quantidade Lajotas": qtd_lajotas,
        "Quantidade de Armadura Negativa": qtd_arm_neg,
        "Volume de Concreto (m³)": vol_conc,
    })

    # Totais por bitola (Armadura de Reforço) — remove bitola vazia
    bitola = df[col_bitola].astype(str).fillna("").str.strip()
    mask_bitola = bitola.ne("")
    df_arm_ref_por_bitola = (
        pd.DataFrame({
            "Bitola": bitola[mask_bitola],
            "Quantitativos de Armadura de Reforço": qtd_arm_ref[mask_bitola]
        })
        .groupby("Bitola", as_index=False)["Quantitativos de Armadura de Reforço"]
        .sum()
        .sort_values("Bitola")
        .reset_index(drop=True)
    )
    df_arm_ref_por_bitola["Quantitativos de Armadura de Reforço"] = df_arm_ref_por_bitola["Quantitativos de Armadura de Reforço"].round(2)

    return df_qtd, df_arm_ref_por_bitola


# ==========================================================
# FINANCEIRO — PREÇOS E CONFIG
# ==========================================================
def listar_precos_materiais() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT material AS Material, unidade AS Unidade, valor_unitario AS Valor FROM precos_materiais ORDER BY material",
        conn
    )
    conn.close()
    return df

def salvar_precos_materiais(df: pd.DataFrame):
    if df is None or df.empty:
        return
    conn = get_conn()
    cur = conn.cursor()
    for _, r in df.iterrows():
        mat = str(r.get("Material", "")).strip()
        if not mat:
            continue
        und = str(r.get("Unidade", "")).strip()
        try:
            val = float(pd.to_numeric(r.get("Valor", 0), errors="coerce") or 0)
        except Exception:
            val = 0.0
        cur.execute(
            """
            INSERT INTO precos_materiais (material, unidade, valor_unitario)
            VALUES (?, ?, ?)
            ON CONFLICT(material) DO UPDATE SET
                unidade=excluded.unidade,
                valor_unitario=excluded.valor_unitario
            """,
            (mat, und, val)
        )
    conn.commit()
    conn.close()

def get_cfg(chave: str, default: float = 0.0) -> float:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT valor FROM config_financeiro WHERE chave=?", (chave,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return float(default)
    try:
        return float(row[0])
    except Exception:
        return float(default)

def set_cfg(chave: str, valor: float):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO config_financeiro (chave, valor)
        VALUES (?, ?)
        ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor
        """,
        (chave, float(valor))
    )
    conn.commit()
    conn.close()

def _brl(v: float) -> str:
    try:
        x = float(v)
    except Exception:
        x = 0.0
    s = f"{x:,.2f}"
    # pt-BR: troca separadores
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

def montar_financeiro_obra(salvos: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """
    Gera a tabela do Financeiro (Material/Quantidade/Valor/Custo Total) + resumo.
    Usa:
      - Volume de Concreto (m³)
      - Armadura por bitola (Barras 5.0/6.3/8.0/10.0/12.5)
      - Treliças, Isopor(EPS), Lajota, Ferragem Negativa
      - Mão de Obra = preço por m²
      - Frete = preço unitário (1x)
    """
    if salvos is None or salvos.empty:
        return pd.DataFrame(), {}

    # Quantitativos
    df_qtd, df_arm = construir_quantitativo(salvos)

    # Área (m²) — usa a mesma do seu cálculo
    area_total = float(pd.to_numeric(salvos.get("Área com Trespasse", 0), errors="coerce").fillna(0).sum())
    area_total = round(area_total, 2)

    # Totais do quantitativo
    vol_conc = float(pd.to_numeric(df_qtd.get("Volume de Concreto (m³)", 0), errors="coerce").fillna(0).sum())
    trelicas = float(pd.to_numeric(df_qtd.get("Quantidade de Treliças", 0), errors="coerce").fillna(0).sum())
    eps = float(pd.to_numeric(df_qtd.get("Quantidade de EPS", 0), errors="coerce").fillna(0).sum())
    lajota = float(pd.to_numeric(df_qtd.get("Quantidade Lajotas", 0), errors="coerce").fillna(0).sum())
    ferr_neg = float(pd.to_numeric(df_qtd.get("Quantidade de Armadura Negativa", 0), errors="coerce").fillna(0).sum())

    # Armadura por bitola (barras de 12m)
    barras = {k: 0.0 for k in ["5.0", "6.3", "8.0", "10.0", "12.5"]}
    if df_arm is not None and not df_arm.empty:
        for _, r in df_arm.iterrows():
            b = str(r.get("Bitola", "")).strip()
            q = float(pd.to_numeric(r.get("Quantitativos de Armadura de Reforço", 0), errors="coerce") or 0)
            if b in barras:
                barras[b] += q

    # Preços
    df_precos = listar_precos_materiais()
    preco = {str(r.Material).strip(): float(pd.to_numeric(r.Valor, errors="coerce") or 0) for r in df_precos.itertuples()}
    unidade = {str(r.Material).strip(): str(r.Unidade or "") for r in df_precos.itertuples()}

    def u(mat, fallback=""):
        return unidade.get(mat, fallback)

    itens = []

    def add_item(nome: str, qtd: float, valor_unit: float, und: str):
        custo = float(qtd) * float(valor_unit)
        itens.append({
            "Material": nome,
            "Quantidade": float(qtd),
            "Unidade": und,
            "Valor": float(valor_unit),
            "Custo Total": float(custo)
        })

    add_item("Volume de Concreto", vol_conc, preco.get("Volume de Concreto", 0.0), u("Volume de Concreto", "m³"))
    add_item("Barras 5.0", barras["5.0"], preco.get("Barras 5.0", 0.0), u("Barras 5.0", "UND"))
    add_item("Barras 6.3", barras["6.3"], preco.get("Barras 6.3", 0.0), u("Barras 6.3", "UND"))
    add_item("Barras 8.0", barras["8.0"], preco.get("Barras 8.0", 0.0), u("Barras 8.0", "UND"))
    add_item("Barras 10.0", barras["10.0"], preco.get("Barras 10.0", 0.0), u("Barras 10.0", "UND"))
    add_item("Barras 12.5", barras["12.5"], preco.get("Barras 12.5", 0.0), u("Barras 12.5", "UND"))
    add_item("Treliças", trelicas, preco.get("Treliças", 0.0), u("Treliças", "UND"))
    add_item("Isopor", eps, preco.get("Isopor", 0.0), u("Isopor", "UND"))
    add_item("Lajota", lajota, preco.get("Lajota", 0.0), u("Lajota", "UND"))

    # Mão de obra (m²)
    add_item("Mão de Obra", area_total, preco.get("Mão de Obra", 0.0), u("Mão de Obra", "m²"))

    # Frete (1x)
    add_item("Frete", 1.0, preco.get("Frete", 0.0), u("Frete", "UND"))

    # Ferragem negativa (barras 12m)
    add_item("Ferragem Negativa", ferr_neg, preco.get("Ferragem Negativa", 0.0), u("Ferragem Negativa", "UND"))

    df_itens = pd.DataFrame(itens)

    custo_producao = float(pd.to_numeric(df_itens["Custo Total"], errors="coerce").fillna(0).sum().round(2))

    resumo = {
        "metragem_m2": area_total,
        "custo_producao": custo_producao,
    }

    return df_itens, resumo


# ==========================================================
# FINANCEIRO — TRAVA (snapshot por obra)
# ==========================================================
def carregar_snapshot_financeiro(obra_id: int) -> Optional[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT locked_at, preco_m2, metragem_m2, custo_producao, preco_proposta, lucro, itens_json
        FROM financeiro_snapshot WHERE obra_id=?
    """, (int(obra_id),))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    try:
        itens = json.loads(row[6] or "[]")
    except Exception:
        itens = []
    return {
        "locked_at": row[0],
        "preco_m2": float(row[1] or 0.0),
        "metragem_m2": float(row[2] or 0.0),
        "custo_producao": float(row[3] or 0.0),
        "preco_proposta": float(row[4] or 0.0),
        "lucro": float(row[5] or 0.0),
        "itens": itens,
    }

def salvar_snapshot_financeiro(obra_id: int, snapshot: dict):
    itens_json = json.dumps(snapshot.get("itens", []), ensure_ascii=False)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO financeiro_snapshot
          (obra_id, locked_at, preco_m2, metragem_m2, custo_producao, preco_proposta, lucro, itens_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(obra_id) DO UPDATE SET
          locked_at=excluded.locked_at,
          preco_m2=excluded.preco_m2,
          metragem_m2=excluded.metragem_m2,
          custo_producao=excluded.custo_producao,
          preco_proposta=excluded.preco_proposta,
          lucro=excluded.lucro,
          itens_json=excluded.itens_json
        """,
        (
            int(obra_id),
            str(snapshot.get("locked_at") or datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
            float(snapshot.get("preco_m2") or 0.0),
            float(snapshot.get("metragem_m2") or 0.0),
            float(snapshot.get("custo_producao") or 0.0),
            float(snapshot.get("preco_proposta") or 0.0),
            float(snapshot.get("lucro") or 0.0),
            itens_json,
        )
    )
    conn.commit()
    conn.close()

def excluir_snapshot_financeiro(obra_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM financeiro_snapshot WHERE obra_id=?", (int(obra_id),))
    conn.commit()
    conn.close()


# cria/migra banco
ensure_schema()


# ==========================================================
# BRANDING (Logo + cabeçalho)
# ==========================================================
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

def render_branding():
    """Mostra logo no sidebar e um banner no topo."""
    logo_path = _find_logo_path()

    # Sidebar: logo + nome
    with st.sidebar:
        if logo_path:
            st.image(logo_path, use_container_width=True)
        st.markdown("### 🏗️ Sistema Engenharia")
        st.caption("Produção • Cálculo • Financeiro")

    # Topo da página: banner colorido
    if logo_path:
        uri = _img_to_data_uri(logo_path)
        st.markdown(
            f"""
            <div class="brandbar">
              <img src="{uri}" style="height:56px; width:auto; border-radius:12px; background: rgba(255,255,255,0.12); padding:6px;" />
              <div>
                <div class="title">Sistema Engenharia</div>
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
                <div class="title">Sistema Engenharia</div>
                <div class="subtitle">Coloque um arquivo <b>logo_app.png</b> (ou logo.png) na mesma pasta do .py para aparecer aqui.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )

# chama branding em todas as páginas
render_branding()
# ==========================================================
# MENU
# ==========================================================
st.sidebar.title("Menu")
pagina = st.sidebar.radio("Navegação", ["Cadastro de Obras", "Cálculo", "Financeiro"])

# ==========================================================
# PAGINA 1 - CADASTRO DE OBRAS
# ==========================================================
if pagina == "Cadastro de Obras":
  st.title("🏗️ Cadastro de Obras")

  st.subheader("Nova obra")
  st.markdown('<div class="card">', unsafe_allow_html=True)
  with st.form("nova_obra", clear_on_submit=True):
      c1, c2, c3 = st.columns(3)
      with c1:
          cliente = st.text_input("Cliente")
      with c2:
          obra = st.text_input("Obra")
      with c3:
          endereco = st.text_input("Endereço (opcional)")

      salvar = st.form_submit_button("💾 Salvar obra")

      if salvar:
          if not (cliente or "").strip() or not (obra or "").strip():
              st.error("Preencha **Cliente** e **Obra**.")
          else:
              inserir_obra(cliente, obra, endereco)
              st.success("Obra cadastrada!")
              st.rerun()
  st.markdown('</div>', unsafe_allow_html=True)

  st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

  section_title("Obras cadastradas")
  df_obras = listar_obras_full()
  st.dataframe(df_obras, use_container_width=True, hide_index=True)

  st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

  st.subheader("Editar / Excluir obra")
  if df_obras.empty:
      st.info("Cadastre uma obra para editar/excluir.")
  else:
      colA, colB = st.columns([1, 2])
      with colA:
          ids = df_obras["id"].tolist()
          obra_id_sel = st.selectbox("Selecione o ID", options=ids)

      with colB:
          obra_atual = obter_obra_por_id(int(obra_id_sel))
          if not obra_atual:
              st.error("Obra não encontrada.")
          else:
              st.markdown('<div class="card">', unsafe_allow_html=True)

              e1, e2, e3 = st.columns(3)
              with e1:
                  novo_cliente = st.text_input("Cliente", value=obra_atual["cliente"], key="ed_cliente")
              with e2:
                  nova_obra = st.text_input("Obra", value=obra_atual["obra"], key="ed_obra")
              with e3:
                  novo_endereco = st.text_input("Endereço (opcional)", value=obra_atual["endereco"], key="ed_endereco")

              b1, b2, b3 = st.columns([1, 1, 2])

              with b1:
                  if st.button("✅ Salvar alterações", use_container_width=True):
                      if not novo_cliente.strip() or not nova_obra.strip():
                          st.error("Preencha **Cliente** e **Obra**.")
                      else:
                          atualizar_obra(int(obra_id_sel), novo_cliente, nova_obra, novo_endereco)
                          st.success("Alterações salvas!")
                          st.rerun()

              with b2:
                  confirmar = st.checkbox("Confirmar exclusão", value=False)
                  if st.button("🗑️ Excluir obra", use_container_width=True, disabled=not confirmar):
                      excluir_obra(int(obra_id_sel))
                      st.warning("Obra excluída (e lançamentos vinculados também).")
                      st.rerun()

              st.markdown('</div>', unsafe_allow_html=True)

# ==========================================================
# PAGINA 2 - CALCULO
# ==========================================================
elif pagina == "Cálculo":
  st.title("📐 Lançamentos — Piso / Forro")
  st.caption("Selecione o tipo de laje. Trespasse fixo = 0.10 m por ponta")

  obras = listar_obras_select()
  if obras.empty:
      st.warning("Cadastre uma obra primeiro.")
      st.stop()

  opcoes = {f"#{row.id} — {row.cliente} / {row.obra}": row.id for row in obras.itertuples()}
  obra_sel = st.selectbox("Escolha a obra/cliente", list(opcoes.keys()))
  obra_id = int(opcoes[obra_sel])

  tipo_laje = st.selectbox("Tipo de Laje", ["Piso", "Forro"], index=0)

  preenchimento = st.selectbox("Tipo de Preenchimento", ["EPS", "Lajota"], index=0)

  # ===== TRAVA (para garantir que o PDF saia sempre igual) =====
  ctx = (obra_id, tipo_laje, str(preenchimento or "EPS"))
  if st.session_state.calc_locked and st.session_state.lock_ctx != ctx:
      # Se mudou a obra ou o tipo, destrava automaticamente
      st.session_state.calc_locked = False
      st.session_state.lock_ctx = None
      st.session_state.lock_time = None
      st.session_state.snapshot_resultado = None
      st.session_state.snapshot_qtd = None
      st.session_state.snapshot_arm_por_bitola = None

  cL, cU, cInfo = st.columns([1, 1, 3])
  with cL:
      travar_btn = st.button("🔒 Travar cálculos", use_container_width=True, disabled=st.session_state.calc_locked)
  with cU:
      destravar_btn = st.button("🔓 Destravar", use_container_width=True, disabled=not st.session_state.calc_locked)
  with cInfo:
      if st.session_state.calc_locked:
          st.success(f"Cálculos TRAVADOS ✅ — PDF gerado a partir do snapshot ({st.session_state.lock_time}).")
      else:
          st.info("Cálculos DESBLOQUEADOS — você pode editar e salvar normalmente.")

  TRESPASSE = 0.10

  section_title("Quantas linhas para lançar")

  qtd_linhas = st.number_input(
      " ",
      min_value=1,
      max_value=200,
      value=1,
      step=1,
      key="qtd_linhas"
  )

  # TABELA DE LANÇAMENTO (SEM colunas de armadura aqui)
  base = pd.DataFrame({
      "Laje": [f"LP{str(i+1).zfill(2)}" for i in range(int(qtd_linhas))],
      "Vão Livre (m)": [0.0] * int(qtd_linhas),
      "Largura (m)": [0.0] * int(qtd_linhas),
  })

  edited_df = st.data_editor(base, num_rows="dynamic", use_container_width=True, disabled=st.session_state.calc_locked)

  col1, col2, col3 = st.columns([1.4, 1.2, 2])
  with col1:
      substituir = st.checkbox("Substituir lançamentos salvos dessa obra", value=True, disabled=st.session_state.calc_locked)
  with col2:
      salvar_btn = st.button("💾 Salvar lançamentos", use_container_width=True, disabled=st.session_state.calc_locked)

  if salvar_btn:
      df = edited_df.copy()

      if df.empty:
          st.error("Nenhuma linha para salvar.")
          st.stop()

      if df["Laje"].astype(str).str.strip().eq("").any():
          st.error("Tem linha com **Laje** vazia.")
          st.stop()

      for col in ["Vão Livre (m)", "Largura (m)"]:
          df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

      salvar_lancamentos_piso(obra_id, df, TRESPASSE, tipo_laje=tipo_laje, preenchimento=preenchimento, substituir=substituir)
      st.success("Lançamentos salvos! ✅ (armadura calculada pelo vão)")
      st.rerun()

  st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
  st.subheader("Resultado")

  salvos_db = ler_lancamentos_piso(obra_id)

  # Ações de travar/destravar (precisa vir depois de carregar do banco)
  if destravar_btn:
      st.session_state.calc_locked = False
      st.session_state.lock_ctx = None
      st.session_state.lock_time = None
      st.session_state.snapshot_resultado = None
      st.session_state.snapshot_qtd = None
      st.session_state.snapshot_arm_por_bitola = None
      st.rerun()

  if travar_btn:
      if salvos_db is None or salvos_db.empty:
          st.error("Não há cálculos para travar. Salve lançamentos primeiro.")
      else:
          df_qtd_snap, df_arm_snap = construir_quantitativo(salvos_db)
          st.session_state.snapshot_resultado = salvos_db.copy()
          st.session_state.snapshot_qtd = df_qtd_snap.copy()
          st.session_state.snapshot_arm_por_bitola = df_arm_snap.copy()
          st.session_state.calc_locked = True
          st.session_state.lock_ctx = ctx
          st.session_state.lock_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
          st.rerun()

  # Se estiver travado, usamos o snapshot; se não, usamos o banco
  salvos = st.session_state.snapshot_resultado if st.session_state.calc_locked and st.session_state.snapshot_resultado is not None else salvos_db

  if salvos.empty:
      st.info("Ainda não há lançamentos salvos para essa obra. Preencha a tabela e clique em **Salvar lançamentos**.")
  else:
      st.markdown(
          f'<div class="wrap-table">{salvos.to_html(index=False, escape=True)}</div>',
          unsafe_allow_html=True
      )

      # PDF para produção (somente campos essenciais)
      obra_info = obter_obra_por_id(int(obra_id))
      if obra_info:
          pdf_bytes = gerar_pdf_producao(
              cliente=obra_info.get("cliente", ""),
              obra=obra_info.get("obra", ""),
              endereco=obra_info.get("endereco", ""),
              df_resultado=salvos,
          )
          nome_pdf = f"OP_{_safe_pdf_name(obra_info.get('obra',''))}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
          if not st.session_state.calc_locked:
              st.warning("Trave os cálculos (🔒) antes de gerar o PDF.")

          st.download_button(
              "📄 Gerar PDF para Produção",
              data=pdf_bytes,
              file_name=nome_pdf,
              mime="application/pdf",
              use_container_width=True,
              disabled=not st.session_state.calc_locked,
          )

      
      st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
      section_title("Quantitativo por Laje e Totais")

      if st.session_state.calc_locked and st.session_state.snapshot_qtd is not None:
          df_qtd = st.session_state.snapshot_qtd
          df_arm_ref_por_bitola = st.session_state.snapshot_arm_por_bitola if st.session_state.snapshot_arm_por_bitola is not None else pd.DataFrame()
      else:
          df_qtd, df_arm_ref_por_bitola = construir_quantitativo(salvos)
      if df_qtd.empty:
          st.info("Sem dados para montar o quantitativo.")
      else:
          st.markdown(
              f'<div class="wrap-table">{df_qtd.to_html(index=False, escape=True)}</div>',
              unsafe_allow_html=True
          )

          # Totais gerais
          totais = pd.DataFrame([{
              "Quantidade de Treliças": float(pd.to_numeric(df_qtd["Quantidade de Treliças"], errors="coerce").fillna(0).sum().round(2)),
              "Armadura de Reforço (Total)": float(pd.to_numeric(df_qtd["Quantitativos de Armadura de Reforço"], errors="coerce").fillna(0).sum().round(2)),
              "Quantidade de EPS": int(pd.to_numeric(df_qtd["Quantidade de EPS"], errors="coerce").fillna(0).sum()),
              "Quantidade Lajotas": int(pd.to_numeric(df_qtd["Quantidade Lajotas"], errors="coerce").fillna(0).sum()),
              "Armadura Negativa (Total)": float(pd.to_numeric(df_qtd["Quantidade de Armadura Negativa"], errors="coerce").fillna(0).sum().round(2)),
              "Volume de Concreto (m³)": float(pd.to_numeric(df_qtd["Volume de Concreto (m³)"], errors="coerce").fillna(0).sum().round(4)),
          }])

          st.markdown("**Totais gerais**")
          st.dataframe(totais, use_container_width=True, hide_index=True)

          section_title("Armadura de Reforço (Quantitativo) — totais por bitola")
          st.dataframe(df_arm_ref_por_bitola, use_container_width=True, hide_index=True)

      total_area = pd.to_numeric(salvos["Área com Trespasse"], errors="coerce").fillna(0.0).sum()
      st.success(f"Área total (com trespasse): {total_area:.2f} m²")

# ==========================================================
# PAGINA 3 - FINANCEIRO
# ==========================================================
elif pagina == "Financeiro":
  st.title("💰 Financeiro")
  st.caption("Orçamentos (valores unitários) + Financeiro de Obra (custo e proposta).")

  aba1, aba2 = st.tabs(["🧾 Orçamentos (Materiais)", "🏗️ Financeiro de Obra"])

  with aba1:
      section_title("Tabela de valores unitários")
      st.caption("Edite os valores e clique em **Salvar**. Esses valores serão usados no Financeiro de Obra.")

      dfp = listar_precos_materiais()
      if dfp is None or dfp.empty:
          st.warning("Tabela de preços vazia. (O sistema cria automaticamente; recarregue se necessário.)")
          dfp = pd.DataFrame(columns=["Material", "Unidade", "Valor"])

      edited_precos = st.data_editor(
          dfp,
          use_container_width=True,
          hide_index=True,
          num_rows="dynamic",
          column_config={
              "Material": st.column_config.TextColumn("Material", required=True),
              "Unidade": st.column_config.TextColumn("Unidade"),
              "Valor": st.column_config.NumberColumn("Valor (R$)", min_value=0.0, step=0.01, format="%.2f"),
          }
      )

      c1 = st.columns([1])[0]
      with c1:
          if st.button("💾 Salvar preços", use_container_width=True):
              salvar_precos_materiais(edited_precos)
              st.success("Preços salvos! ✅")
              st.rerun()

  with aba2:
      st.subheader("Financeiro de Obra")
      obras = listar_obras_select()
      if obras.empty:
          st.warning("Cadastre uma obra primeiro.")
          st.stop()

      opcoes = {f"#{row.id} — {row.cliente} / {row.obra}": row.id for row in obras.itertuples()}
      obra_sel = st.selectbox("Escolha a obra/cliente", list(opcoes.keys()), key="fin_obra_sel")
      obra_id = int(opcoes[obra_sel])

      # ===== TRAVA DO FINANCEIRO (por obra) =====
      snap_db = carregar_snapshot_financeiro(obra_id)
      st.session_state.fin_locked = bool(snap_db)
      st.session_state.fin_lock_obra_id = obra_id if snap_db else None
      st.session_state.fin_lock_time = snap_db.get("locked_at") if snap_db else None
      st.session_state.fin_snapshot = snap_db

      cL, cU, cInfo = st.columns([1, 1, 3])
      with cL:
          travar_fin_btn = st.button("🔒 Travar proposta", use_container_width=True, disabled=st.session_state.fin_locked)
      with cU:
          destravar_fin_btn = st.button("🔓 Destravar", use_container_width=True, disabled=not st.session_state.fin_locked)
      with cInfo:
          if st.session_state.fin_locked:
              st.success(f"Financeiro TRAVADO ✅ — proposta fixa (snapshot em {st.session_state.fin_lock_time}).")
          else:
              st.info("Financeiro DESBLOQUEADO — altera conforme preços dos materiais.")

      if destravar_fin_btn:
          excluir_snapshot_financeiro(obra_id)
          st.session_state.fin_locked = False
          st.session_state.fin_snapshot = None
          st.session_state.fin_lock_time = None
          st.rerun()


      # Usa os lançamentos salvos (mesma base do cálculo)
      salvos_db = ler_lancamentos_piso(obra_id)
      salvos = st.session_state.snapshot_resultado if st.session_state.calc_locked and st.session_state.lock_ctx and st.session_state.lock_ctx[0] == obra_id and st.session_state.snapshot_resultado is not None else salvos_db

      if salvos is None or salvos.empty:
          st.info("Essa obra ainda não tem lançamentos salvos. Vá em **Cálculo** e salve os lançamentos.")
          st.stop()

      # Se estiver TRAVADO, usa o snapshot do banco; se não, calcula com preços atuais
      if st.session_state.fin_locked and st.session_state.fin_snapshot:
          df_fin = pd.DataFrame(st.session_state.fin_snapshot.get("itens", []))
          resumo = {
              "metragem_m2": float(st.session_state.fin_snapshot.get("metragem_m2", 0.0) or 0.0),
              "custo_producao": float(st.session_state.fin_snapshot.get("custo_producao", 0.0) or 0.0),
          }
      else:
          df_fin, resumo = montar_financeiro_obra(salvos)
      if df_fin.empty:
          st.warning("Sem dados para montar o financeiro.")
          st.stop()

      # Formata para exibir igual sua tabela
      df_show = df_fin.copy()
      df_show["Quantidade"] = pd.to_numeric(df_show["Quantidade"], errors="coerce").fillna(0.0).map(lambda x: f"{x:.2f}")
      df_show["Valor"] = pd.to_numeric(df_show["Valor"], errors="coerce").fillna(0.0).map(lambda x: _brl(x))
      df_show["Custo Total"] = pd.to_numeric(df_show["Custo Total"], errors="coerce").fillna(0.0).map(lambda x: _brl(x))
      df_show = df_show[["Material", "Quantidade", "Valor", "Custo Total"]]

      st.markdown('<div class="section-title section-title-green">💰 RESUMO FINANCEIRO</div>', unsafe_allow_html=True)
      m2 = resumo.get("metragem_m2", 0.0)
      st.success(f"Área (com trespasse): **{m2:.2f} m²**")

      st.markdown('<div class="wrap-table-fin">', unsafe_allow_html=True)
      st.markdown(df_show.to_html(index=False, escape=True), unsafe_allow_html=True)
      st.markdown('</div>', unsafe_allow_html=True)

      section_title("Totais e Proposta")

      area_total = float(resumo.get("metragem_m2", 0.0) or 0.0)
      c_prod = float(resumo.get("custo_producao", 0.0) or 0.0)

      cB, cC = st.columns([1.2, 2.2])
      with cB:
          preco_m2_padrao = float(get_cfg("preco_venda_m2", 0.0))
          if st.session_state.fin_locked and st.session_state.fin_snapshot:
              preco_m2_padrao = float(st.session_state.fin_snapshot.get("preco_m2", preco_m2_padrao) or 0.0)

          preco_m2 = st.number_input(
              "Preço do m² (R$)",
              min_value=0.0,
              step=1.0,
              value=preco_m2_padrao,
              key="fin_preco_m2",
              disabled=st.session_state.fin_locked
          )

          if st.button("Salvar preço/m²", use_container_width=True, disabled=st.session_state.fin_locked):
              set_cfg("preco_venda_m2", float(preco_m2))
              st.success("Preço/m² salvo! ✅")
              st.rerun()


      with cC:
          st.info("Dica: informe **Mão de Obra (R$/m²)** e **Frete (R$)** na tabela de preços para entrar no custo total.")

      custo_total = float(round(c_prod, 2))

      # Receita / proposta
      if st.session_state.fin_locked and st.session_state.fin_snapshot:
          receita = float(st.session_state.fin_snapshot.get("preco_proposta", 0.0) or 0.0)
          lucro = float(st.session_state.fin_snapshot.get("lucro", 0.0) or 0.0)
      else:
          # (preço do m² × área com trespasse)
          receita = float(round(area_total * float(preco_m2), 2)) if area_total > 0 else 0.0
          lucro = float(round(receita - custo_total, 2))

          # Se pediu pra travar agora, salva snapshot no banco
          if travar_fin_btn:
              snap = {
                  "locked_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                  "preco_m2": float(preco_m2),
                  "metragem_m2": float(area_total),
                  "custo_producao": float(c_prod),
                  "preco_proposta": float(receita),
                  "lucro": float(lucro),
                  "itens": df_fin.to_dict(orient="records"),
              }
              salvar_snapshot_financeiro(obra_id, snap)
              st.success("Proposta travada! ✅")
              st.rerun()

      custo_por_m2 = float(round(custo_total / area_total, 2)) if area_total > 0 else 0.0
      lucro_por_m2 = float(round(lucro / area_total, 2)) if area_total > 0 else 0.0


      totais_df = pd.DataFrame([{
          "Custo Total de Produção": _brl(c_prod),
          "Preço da Proposta": _brl(receita),
          "Custo por m²": _brl(custo_por_m2),
          "Lucro por m²": _brl(lucro_por_m2),
          "Lucro": _brl(lucro),
      }])

      st.dataframe(totais_df, use_container_width=True, hide_index=True)

      st.caption("Obs.: **Preço da Proposta** = (Preço do m² × Área com trespasse). **Lucro** = Proposta − Custo de Produção.")
