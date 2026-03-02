import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="🛠️ Admin Geral", layout="wide")


# =========================
# CAMINHOS DOS BANCOS
# =========================
BASE_DIR = Path(__file__).resolve().parents[1]

DBS = {
    "💰 Financeiro": BASE_DIR / "banco.db",
    "🚜 Locação": BASE_DIR / "locacao.db",
    "🏗️ ADM de Obras": BASE_DIR / "banco_adm_obras.db",
    "🏭 Fábrica": BASE_DIR / "fabrica.db",
}


# =========================
# FUNÇÕES (DB)
# =========================
def _safe_tables(db_path: Path) -> list[str]:
    """Lista tabelas e garante retorno seguro."""
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;",
            conn,
        )
    return df["name"].tolist() if not df.empty else []


@st.cache_data(show_spinner=False)
def list_tables(db_path_str: str) -> list[str]:
    return _safe_tables(Path(db_path_str))


def _validate_table(db_path: Path, table: str) -> bool:
    """Só permite tabela se ela realmente existir no banco."""
    return table in _safe_tables(db_path)


@st.cache_data(show_spinner=False)
def read_table(db_path_str: str, table: str, limit: int) -> pd.DataFrame:
    db_path = Path(db_path_str)
    if not db_path.exists():
        return pd.DataFrame()

    if not _validate_table(db_path, table):
        return pd.DataFrame()

    with sqlite3.connect(db_path) as conn:
        # table vem validada contra lista real do sqlite_master
        return pd.read_sql(f"SELECT * FROM '{table}' LIMIT {int(limit)};", conn)


@st.cache_data(show_spinner=False)
def quick_count(db_path_str: str, table: str) -> int:
    db_path = Path(db_path_str)
    if not db_path.exists():
        return 0

    if not _validate_table(db_path, table):
        return 0

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(1) FROM '{table}';")
        return int(cur.fetchone()[0] or 0)


# =========================
# TELA
# =========================
st.title("🛠️ ADMIN GERAL — Visão Completa do Sistema")

top_left, top_right = st.columns([3, 1])
with top_left:
    st.caption("Acesso ADMIN • Leitura de dados dos módulos • Exportação CSV")

with top_right:
    if st.button("🔄 Atualizar / Limpar cache", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# Status bancos
cols = st.columns(len(DBS))
for i, (nome, path) in enumerate(DBS.items()):
    with cols[i]:
        if path.exists():
            st.success(f"{nome}\n\nBanco encontrado")
            st.caption(str(path))
        else:
            st.error(f"{nome}\n\nBanco não encontrado")
            st.caption(str(path))

st.divider()

# Abas
tabs = st.tabs(list(DBS.keys()) + ["📊 Consolidado"])


# =========================
# ABAS DOS MÓDULOS
# =========================
for tab_name, tab in zip(list(DBS.keys()), tabs[:-1]):
    db_path = DBS[tab_name]

    with tab:
        st.subheader(tab_name)

        if not db_path.exists():
            st.warning("Banco não encontrado.")
            continue

        tables = list_tables(str(db_path))
        if not tables:
            st.info("Nenhuma tabela encontrada.")
            continue

        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            table = st.selectbox(
                "Selecionar tabela",
                tables,
                key=f"{tab_name}_table",
            )

        with col2:
            limit = st.number_input(
                "Limite de linhas",
                min_value=100,
                max_value=50000,
                value=5000,
                step=100,
                key=f"{tab_name}_limit",
            )

        with col3:
            # pequena conveniência pra ir rápido
            st.write("")
            st.write("")
            if st.button("📥 CSV (rápido)", use_container_width=True, key=f"{tab_name}_csv_fast"):
                # força leitura com limite atual e dispara download logo abaixo
                pass

        total = quick_count(str(db_path), table)
        st.metric("Total de registros", total)

        df = read_table(str(db_path), table, int(limit))

        if df.empty:
            st.info("Sem dados para exibir (ou tabela inválida).")
            continue

        st.dataframe(df, use_container_width=True, height=500)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Baixar CSV",
            data=csv,
            file_name=f"{tab_name}_{table}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"{tab_name}_{table}_csv",
        )


# =========================
# CONSOLIDADO GERAL
# =========================
with tabs[-1]:
    st.subheader("📊 Resumo Geral do Sistema")

    resumo = []

    for nome, db_path in DBS.items():
        if not db_path.exists():
            resumo.append({"Módulo": nome, "Tabelas": 0, "Registros Totais": 0})
            continue

        tables = list_tables(str(db_path))
        total_regs = 0

        for t in tables:
            try:
                total_regs += quick_count(str(db_path), t)
            except Exception:
                pass

        resumo.append(
            {
                "Módulo": nome,
                "Tabelas": len(tables),
                "Registros Totais": total_regs,
            }
        )

    df_resumo = pd.DataFrame(resumo)

    st.dataframe(df_resumo, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Módulos", len(DBS))
    c2.metric("Total de Tabelas", int(df_resumo["Tabelas"].sum()))
    c3.metric("Total de Registros", int(df_resumo["Registros Totais"].sum()))