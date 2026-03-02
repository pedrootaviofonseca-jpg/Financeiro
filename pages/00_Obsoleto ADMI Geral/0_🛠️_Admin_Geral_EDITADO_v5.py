import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import date

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

# Empresas padrão (mesmas do módulo Financeiro)
FIN_EMPRESAS_PADRAO = [
    "01_Escritório",
    "02_Adm de Obras",
    "03_Fábrica",
    "04_Locação de Equipamentos",
    "05_Refil",
]

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
# FINANCEIRO (VISÃO POR EMPRESA)
# =========================
def br_money(x) -> str:
    try:
        v = float(x or 0)
        s = f"{v:,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {s}"
    except Exception:
        return str(x)


@st.cache_data(show_spinner=False)
def financeiro_empresas(db_path_str: str) -> list[str]:
    """Lista empresas disponíveis no financeiro.

    Retorna a união de:
    - empresas padrão (cadastro do sistema)
    - empresas que já aparecem na tabela dados
    """
    db_path = Path(db_path_str)
    empresas_db: list[str] = []
    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            try:
                df = pd.read_sql(
                    """
                    SELECT DISTINCT COALESCE(empresa,'') AS empresa
                    FROM dados
                    WHERE COALESCE(empresa,'') <> ''
                    ORDER BY empresa
                    """,
                    conn,
                )
                empresas_db = df["empresa"].tolist() if not df.empty else []
            except Exception:
                empresas_db = []

    # une padrão + as que já existem no banco
    return sorted(set(FIN_EMPRESAS_PADRAO + empresas_db))


@st.cache_data(show_spinner=False)
def financeiro_lancamentos_por_filtro(
    db_path_str: str,
    empresa: str,
    dt_ini_iso: str,
    dt_fim_iso: str,
    tipo: str | None,
    situacao: str | None,
) -> pd.DataFrame:
    """Carrega lançamentos da tabela dados por filtros (empresa/período/tipo/situação)."""
    db_path = Path(db_path_str)
    if not db_path.exists():
        return pd.DataFrame()

    wheres = []
    params: list = []
    if empresa != "(Todas)":
        wheres.append("COALESCE(empresa,'') = ?")
        params.append(empresa)

    # período
    wheres.append("date(data_operacao) >= date(?)")
    params.append(dt_ini_iso)
    wheres.append("date(data_operacao) <= date(?)")
    params.append(dt_fim_iso)

    # tipo
    if tipo in ("entrada", "saida"):
        wheres.append("tipo = ?")
        params.append(tipo)

    # situação
    if situacao in ("Pago", "Em aberto"):
        wheres.append("situacao = ?")
        params.append(situacao)

    where_sql = " AND ".join(wheres) if wheres else "1=1"

    sql = f"""
        SELECT
            id, empresa, tipo, data_operacao, descricao,
            categoria, conta_bancaria, valor,
            forma_pagamento, parcelas, primeiro_debito, situacao
        FROM dados
        WHERE {where_sql}
        ORDER BY date(data_operacao) DESC, id DESC
    """

    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql(sql, conn, params=params)
        except Exception:
            return pd.DataFrame()

    return df


def render_financeiro_por_empresa(db_path: Path):
    st.subheader("💰 Financeiro — Entradas e Saídas (separado por empresa)")

    if not db_path.exists():
        st.warning("Banco do Financeiro não encontrado.")
        return

    empresas = financeiro_empresas(str(db_path))

    # Fallback: se não achar empresas distintas, ainda deixa o modo técnico funcionando
    if not empresas:
        st.info("Não encontrei empresas na tabela 'dados' (coluna empresa vazia ou tabela inexistente).")
        st.caption("Você ainda pode usar o 'Modo técnico' (tabelas) abaixo.")
        return

    cA, cB, cC, cD = st.columns([2, 1.2, 1.2, 1.4])
    with cA:
        empresa = st.selectbox("Empresa", ["(Todas)"] + empresas, key="fin_empresa_sel")

    with cB:
        dt_ini = st.date_input("Data inicial", value=date.today().replace(day=1), key="fin_dt_ini")

    with cC:
        dt_fim = st.date_input("Data final", value=date.today(), key="fin_dt_fim")

    with cD:
        tipo_ui = st.selectbox("Tipo", ["Tudo", "Entradas", "Saídas"], key="fin_tipo")
        tipo = None
        if tipo_ui == "Entradas":
            tipo = "entrada"
        elif tipo_ui == "Saídas":
            tipo = "saida"

    cE, cF = st.columns([1.4, 2.6])
    with cE:
        situacao_ui = st.selectbox("Situação", ["Todas", "Pago", "Em aberto"], key="fin_situacao")
        situacao = None if situacao_ui == "Todas" else situacao_ui

    with cF:
        st.caption("Dica: use os filtros para ver somente a empresa e o período desejado.")

    if dt_ini > dt_fim:
        st.error("A data inicial não pode ser maior que a data final.")
        return

    df = financeiro_lancamentos_por_filtro(
        str(db_path),
        empresa=empresa,
        dt_ini_iso=dt_ini.isoformat(),
        dt_fim_iso=dt_fim.isoformat(),
        tipo=tipo,
        situacao=situacao,
    )

    if df.empty:
        st.info("Sem lançamentos para os filtros selecionados.")
        return

    # Métricas
    entradas = df[df["tipo"] == "entrada"]["valor"].sum()
    saidas = df[df["tipo"] == "saida"]["valor"].sum()
    saldo = float(entradas) - float(saidas)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Registros", int(len(df)))
    m2.metric("Entradas", br_money(entradas))
    m3.metric("Saídas", br_money(saidas))
    m4.metric("Saldo (Entradas - Saídas)", br_money(saldo))

    # Tabela (bonitinha)
    df_show = df.copy()
    df_show["Tipo"] = df_show["tipo"].replace({"entrada": "Entrada", "saida": "Saída"})
    # Datas para BR
    for col in ("data_operacao", "primeiro_debito"):
        if col in df_show.columns:
            df_show[col] = pd.to_datetime(df_show[col], errors="coerce").dt.strftime("%d/%m/%Y").fillna(df_show[col].astype(str))
    if "valor" in df_show.columns:
        df_show["valor"] = df_show["valor"].apply(br_money)

    df_show = df_show.rename(columns={
        "id": "ID",
        "empresa": "Empresa",
        "Tipo": "Tipo",
        "data_operacao": "Data",
        "descricao": "Descrição",
        "categoria": "Categoria",
        "conta_bancaria": "Conta",
        "valor": "Valor",
        "forma_pagamento": "Forma",
        "parcelas": "Parcelas",
        "primeiro_debito": "1º Débito",
        "situacao": "Situação",
    })

    # remove coluna antiga "tipo" se ainda existir
    if "tipo" in df_show.columns:
        df_show = df_show.drop(columns=["tipo"])

    st.markdown("### Lançamentos (filtrados)")
    st.dataframe(df_show, use_container_width=True, height=520)

    # Export
    csv = df_show.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Baixar CSV (Empresa/Período)",
        data=csv,
        file_name=f"financeiro_{empresa.replace('(','').replace(')','').replace(' ','')}_{dt_ini.isoformat()}_{dt_fim.isoformat()}.csv",
        mime="text/csv",
        use_container_width=True,
        key="fin_csv_export",
    )


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
        # ====== FINANCEIRO: visão por empresa + modo técnico ======
        if tab_name == "💰 Financeiro":
            render_financeiro_por_empresa(db_path)

            st.divider()
            with st.expander("🔧 Modo técnico (ver tabelas cruas do banco)", expanded=False):
                st.subheader("💰 Financeiro (Tabelas)")
                if not db_path.exists():
                    st.warning("Banco não encontrado.")
                else:
                    tables = list_tables(str(db_path))
                    if not tables:
                        st.info("Nenhuma tabela encontrada.")
                    else:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            table = st.selectbox("Selecionar tabela", tables, key=f"{tab_name}_table")
                        with col2:
                            limit = st.number_input(
                                "Limite de linhas",
                                min_value=100,
                                max_value=50000,
                                value=5000,
                                step=100,
                                key=f"{tab_name}_limit",
                            )

                        total = quick_count(str(db_path), table)
                        st.metric("Total de registros", total)

                        df = read_table(str(db_path), table, int(limit))
                        if df.empty:
                            st.info("Sem dados para exibir (ou tabela inválida).")
                        else:
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
            continue

        # ====== OUTROS MÓDULOS (como estava) ======
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
