import db_adapter
import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import date, datetime, timedelta
import calendar

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
def financeiro_categorias(db_path_str: str, empresa: str) -> list[str]:
    """Lista categorias disponíveis na tabela dados (por empresa ou todas)."""
    db_path = Path(db_path_str)
    if not db_path.exists():
        return []

    wheres = []
    params: list = []
    if empresa != "(Todas)":
        wheres.append("COALESCE(empresa,'') = ?")
        params.append(empresa)

    where_sql = " AND ".join(wheres) if wheres else "1=1"

    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql(
                f"""
                SELECT DISTINCT COALESCE(categoria,'') AS categoria
                FROM dados
                WHERE {where_sql}
                  AND COALESCE(categoria,'') <> ''
                ORDER BY categoria
                """,
                conn,
                params=params,
            )
        except Exception:
            return []

    return df["categoria"].tolist() if not df.empty else []


@st.cache_data(show_spinner=False)
def financeiro_anos(db_path_str: str, empresa: str) -> list[int]:
    """Lista anos disponíveis pela coluna data_operacao (por empresa ou todas)."""
    db_path = Path(db_path_str)
    if not db_path.exists():
        return []
    wheres = []
    params: list = []
    if empresa != "(Todas)":
        wheres.append("COALESCE(empresa,'') = ?")
        params.append(empresa)
    where_sql = " AND ".join(wheres) if wheres else "1=1"
    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql(
                f"""
                SELECT DISTINCT CAST(strftime('%Y', date(data_operacao)) AS INTEGER) AS ano
                FROM dados
                WHERE {where_sql}
                  AND COALESCE(data_operacao,'') <> ''
                ORDER BY ano
                """,
                conn,
                params=params,
            )
        except Exception:
            return []
    anos = [int(x) for x in df["ano"].dropna().tolist()] if not df.empty else []
    return [a for a in anos if a > 1900]


@st.cache_data(show_spinner=False)
def financeiro_lancamentos_por_filtro(
    db_path_str: str,
    empresa: str,
    dt_ini_iso: str,
    dt_fim_iso: str,
    tipo: str | None,
    situacao: str | None,
    categoria: str | None,
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

    # categoria
    if categoria and categoria != "(Todas)":
        wheres.append("categoria = ?")
        params.append(categoria)

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

    cA, cB, cC, cD, cT = st.columns([2, 1.0, 1.2, 1.0, 1.4])
    with cA:
        empresa = st.selectbox("Empresa", ["(Todas)"] + empresas, key="fin_empresa_sel")

    with cB:
        # Filtro por Ano/Mês/Dia (ao invés de período livre)
        anos_disp = financeiro_anos(str(db_path), empresa)
        if not anos_disp:
            anos_disp = [date.today().year]
        ano_sel = st.selectbox("Ano", anos_disp, index=len(anos_disp)-1, key="fin_ano")

    with cC:
        meses = [
            "01 - Janeiro","02 - Fevereiro","03 - Março","04 - Abril","05 - Maio","06 - Junho",
            "07 - Julho","08 - Agosto","09 - Setembro","10 - Outubro","11 - Novembro","12 - Dezembro"
        ]
        mes_txt = st.selectbox("Mês", meses, index=date.today().month-1, key="fin_mes")
        mes_sel = int(mes_txt.split(" - ")[0])

    with cD:
        # Dia opcional: (Todos) = mês inteiro
        last_day = calendar.monthrange(int(ano_sel), int(mes_sel))[1]
        dias = ["(Todos)"] + [str(d).zfill(2) for d in range(1, last_day + 1)]
        dia_txt = st.selectbox("Dia", dias, key="fin_dia")
        dia_sel = None if dia_txt == "(Todos)" else int(dia_txt)

    with cT:
        tipo_ui = st.selectbox("Tipo", ["Tudo", "Entradas", "Saídas"], key="fin_tipo")
        tipo = None
        if tipo_ui == "Entradas":
            tipo = "entrada"
        elif tipo_ui == "Saídas":
            tipo = "saida"

    cE, cF, cG = st.columns([1.4, 1.8, 1.8])
    with cE:
        situacao_ui = st.selectbox("Situação", ["Todas", "Pago", "Em aberto"], key="fin_situacao")
        situacao = None if situacao_ui == "Todas" else situacao_ui

    with cF:
        cats = financeiro_categorias(str(db_path), empresa)
        categoria_sel = st.selectbox("Categoria", ["(Todas)"] + cats, key="fin_categoria")

    with cG:
        st.caption("Dica: use os filtros para ver somente a empresa e o período desejado.")

    # Constrói intervalo a partir do Ano/Mês/Dia
    if dia_sel is not None:
        dt_ini = date(int(ano_sel), int(mes_sel), int(dia_sel))
        dt_fim = dt_ini
    else:
        dt_ini = date(int(ano_sel), int(mes_sel), 1)
        last_day = calendar.monthrange(int(ano_sel), int(mes_sel))[1]
        dt_fim = date(int(ano_sel), int(mes_sel), int(last_day))

    df = financeiro_lancamentos_por_filtro(
        str(db_path),
        empresa=empresa,
        dt_ini_iso=dt_ini.isoformat(),
        dt_fim_iso=dt_fim.isoformat(),
        tipo=tipo,
        situacao=situacao,
        categoria=categoria_sel,
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

    # Gráfico de barras: Entradas x Saídas (mês selecionado)
    # (Sempre calcula para o mês inteiro escolhido, mesmo se você estiver vendo um dia específico)
    df_mes = financeiro_lancamentos_por_filtro(
        str(db_path),
        empresa=empresa,
        dt_ini_iso=date(int(ano_sel), int(mes_sel), 1).isoformat(),
        dt_fim_iso=date(int(ano_sel), int(mes_sel), calendar.monthrange(int(ano_sel), int(mes_sel))[1]).isoformat(),
        tipo=None,                 # precisa de ambos para comparar
        situacao=situacao,
        categoria=categoria_sel,
    )
    ent_mes = df_mes[df_mes["tipo"] == "entrada"]["valor"].sum() if not df_mes.empty else 0
    sai_mes = df_mes[df_mes["tipo"] == "saida"]["valor"].sum() if not df_mes.empty else 0

    df_bar = pd.DataFrame(
        {"Valor": [float(ent_mes), float(sai_mes)]},
        index=["Entradas", "Saídas"]
    )

    st.markdown("### 📊 Entradas x Saídas (mês selecionado)")
    st.bar_chart(df_bar)

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
# LOCAÇÃO (VISÃO ADMIN)
# =========================

def to_iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def last_day_of_month(ano: int, mes: int) -> date:
    return date(ano, mes, calendar.monthrange(ano, mes)[1])


def overlap_days(a_start: date, a_end: date, b_start: date, b_end: date) -> int:
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    if end < start:
        return 0
    return (end - start).days + 1


@st.cache_data(show_spinner=False)
def _locacoes_que_encostam_no_periodo(db_path_str: str, inicio: date, fim: date, status: str | None = None) -> pd.DataFrame:
    """Locações que sobrepõem o período (inicio..fim)."""
    db_path = Path(db_path_str)
    if not db_path.exists():
        return pd.DataFrame()
    wh = [
        "date(data_inicio) <= date(?)",
        "("
        " status='Em andamento' "
        " OR (status='Finalizado' AND data_fim_real IS NOT NULL AND date(data_fim_real) >= date(?))"
        ")",
    ]
    params = [to_iso(fim), to_iso(inicio)]
    if status and status != "(Todos)":
        wh.append("status = ?")
        params.append(status)
    where_sql = " AND ".join(wh)
    with sqlite3.connect(db_path) as conn:
        try:
            return pd.read_sql(
                f"""
                SELECT id, data_inicio, data_fim_real, status, modo_cobranca, cliente_id
                FROM locacoes
                WHERE {where_sql}
                """,
                conn,
                params=params,
            )
        except Exception:
            return pd.DataFrame()


@st.cache_data(show_spinner=False)
def _itens_com_maquinas(db_path_str: str) -> pd.DataFrame:
    db_path = Path(db_path_str)
    if not db_path.exists():
        return pd.DataFrame()
    with sqlite3.connect(db_path) as conn:
        try:
            return pd.read_sql(
                """
                SELECT li.locacao_id, li.maquina_id, li.quantidade, li.valor_diaria, li.valor_mensal,
                       m.descricao, m.categoria
                FROM locacao_itens li
                JOIN maquinas m ON m.id = li.maquina_id
                """,
                conn,
            )
        except Exception:
            return pd.DataFrame()


@st.cache_data(show_spinner=False)
def calcular_estimada_por_maquina_no_periodo(
    db_path_str: str,
    inicio: date,
    fim: date,
    status: str | None,
    cliente_id: int | None,
) -> pd.DataFrame:
    locs = _locacoes_que_encostam_no_periodo(db_path_str, inicio, fim, status)
    if cliente_id is not None and not locs.empty:
        locs = locs[locs["cliente_id"] == int(cliente_id)]
    itens = _itens_com_maquinas(db_path_str)
    if locs.empty or itens.empty:
        return pd.DataFrame(columns=["maquina_id", "descricao", "qtd_total", "valor_estimado"])

    base = itens.merge(locs, left_on="locacao_id", right_on="id", how="inner")

    def calc_valor_linha(row) -> float:
        try:
            di = datetime.strptime(str(row["data_inicio"]), "%Y-%m-%d").date()
        except Exception:
            return 0.0

        if str(row["status"]) == "Finalizado" and row.get("data_fim_real"):
            try:
                df = datetime.strptime(str(row["data_fim_real"]), "%Y-%m-%d").date()
            except Exception:
                df = fim
        else:
            df = fim

        dias = overlap_days(di, df, inicio, fim)
        if dias <= 0:
            return 0.0

        qtd = int(row.get("quantidade") or 0)
        modo = str(row.get("modo_cobranca") or "Diária").strip()

        if modo == "Mensal":
            vm = float(row.get("valor_mensal") or 0)
            return vm * qtd * (dias / 30.0)
        else:
            vd = float(row.get("valor_diaria") or 0)
            return vd * qtd * dias

    base["valor_estimado"] = base.apply(calc_valor_linha, axis=1)

    resumo = base.groupby(["maquina_id", "descricao"], as_index=False).agg(
        qtd_total=("quantidade", "sum"),
        valor_estimado=("valor_estimado", "sum"),
    )
    resumo["qtd_total"] = resumo["qtd_total"].fillna(0).astype(int)
    resumo["valor_estimado"] = resumo["valor_estimado"].fillna(0).astype(float)
    return resumo


@st.cache_data(show_spinner=False)
def max_simultaneo_no_periodo(
    db_path_str: str,
    inicio: date,
    fim: date,
    status: str | None,
    cliente_id: int | None,
) -> pd.DataFrame:
    locs = _locacoes_que_encostam_no_periodo(db_path_str, inicio, fim, status)
    if cliente_id is not None and not locs.empty:
        locs = locs[locs["cliente_id"] == int(cliente_id)]
    itens = _itens_com_maquinas(db_path_str)
    if locs.empty or itens.empty:
        return pd.DataFrame(columns=["maquina_id", "descricao", "pico_simultaneo"])

    base = itens.merge(locs, left_on="locacao_id", right_on="id", how="inner")

    events: dict[int, dict[date, int]] = {}
    desc_map: dict[int, str] = {}

    for _, r in base.iterrows():
        mid = int(r["maquina_id"])
        desc_map[mid] = str(r["descricao"])
        qtd = int(r.get("quantidade") or 0)
        if qtd <= 0:
            continue

        di = datetime.strptime(str(r["data_inicio"]), "%Y-%m-%d").date()
        if str(r["status"]) == "Finalizado" and r.get("data_fim_real"):
            df = datetime.strptime(str(r["data_fim_real"]), "%Y-%m-%d").date()
        else:
            df = fim

        start = max(di, inicio)
        end = min(df, fim)
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


@st.cache_data(show_spinner=False)
def recebido_no_periodo(db_path_str: str, inicio: date, fim: date, cliente_id: int | None) -> float:
    db_path = Path(db_path_str)
    if not db_path.exists():
        return 0.0
    with sqlite3.connect(db_path) as conn:
        wh = ["date(data_pagamento) >= date(?)", "date(data_pagamento) <= date(?)"]
        ps = [to_iso(inicio), to_iso(fim)]
        if cliente_id is not None:
            wh.append("locacao_id IN (SELECT id FROM locacoes WHERE cliente_id = ?)")
            ps.append(int(cliente_id))
        where_sql = " AND ".join(wh)
        try:
            df = pd.read_sql(f"SELECT COALESCE(SUM(valor),0) as recebido FROM recebimentos WHERE {where_sql}", conn, params=ps)
            return float(df.loc[0, "recebido"] or 0) if not df.empty else 0.0
        except Exception:
            return 0.0


@st.cache_data(show_spinner=False)
def faturado_fechado_no_periodo(db_path_str: str, inicio: date, fim: date, cliente_id: int | None) -> float:
    db_path = Path(db_path_str)
    if not db_path.exists():
        return 0.0
    with sqlite3.connect(db_path) as conn:
        wh = [
            "status='Finalizado'",
            "data_fim_real IS NOT NULL",
            "date(data_fim_real) >= date(?)",
            "date(data_fim_real) <= date(?)",
        ]
        ps = [to_iso(inicio), to_iso(fim)]
        if cliente_id is not None:
            wh.append("cliente_id = ?")
            ps.append(int(cliente_id))
        where_sql = " AND ".join(wh)
        try:
            df = pd.read_sql(f"SELECT COALESCE(SUM(total_final),0) as faturado FROM locacoes WHERE {where_sql}", conn, params=ps)
            return float(df.loc[0, "faturado"] or 0) if not df.empty else 0.0
        except Exception:
            return 0.0

@st.cache_data(show_spinner=False)
def locacao_anos(db_path_str: str) -> list[int]:
    """Anos disponíveis em locacoes.data_inicio e locacoes.data_fim_real."""
    db_path = Path(db_path_str)
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql(
                """
                SELECT DISTINCT CAST(strftime('%Y', date(data_inicio)) AS INTEGER) AS ano
                FROM locacoes
                WHERE COALESCE(data_inicio,'') <> ''
                UNION
                SELECT DISTINCT CAST(strftime('%Y', date(data_fim_real)) AS INTEGER) AS ano
                FROM locacoes
                WHERE COALESCE(data_fim_real,'') <> ''
                ORDER BY ano
                """,
                conn,
            )
        except Exception:
            return []
    anos = [int(x) for x in df["ano"].dropna().tolist()] if not df.empty else []
    return [a for a in anos if a > 1900]


@st.cache_data(show_spinner=False)
def locacao_clientes(db_path_str: str) -> list[tuple[int, str]]:
    """Lista clientes (id, nome) do banco de locação."""
    db_path = Path(db_path_str)
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql("SELECT id, nome FROM clientes ORDER BY nome", conn)
        except Exception:
            return []
    if df.empty:
        return []
    return [(int(r["id"]), str(r["nome"])) for _, r in df.iterrows()]


@st.cache_data(show_spinner=False)
def locacao_listar(
    db_path_str: str,
    dt_ini_iso: str,
    dt_fim_iso: str,
    status: str | None,
    cliente_id: int | None,
) -> pd.DataFrame:
    """Lista locações (com totais recebido/saldo) filtradas por datas/status/cliente.
    Critério de data:
    - usa data_fim_real (fechamento) quando existir
    - senão usa data_inicio (abertas)
    """
    db_path = Path(db_path_str)
    if not db_path.exists():
        return pd.DataFrame()

    wheres = [
        "date(COALESCE(data_fim_real, data_inicio)) >= date(?)",
        "date(COALESCE(data_fim_real, data_inicio)) <= date(?)",
    ]
    params: list = [dt_ini_iso, dt_fim_iso]

    if status and status != "(Todos)":
        wheres.append("status = ?")
        params.append(status)

    if cliente_id is not None:
        wheres.append("cliente_id = ?")
        params.append(int(cliente_id))

    where_sql = " AND ".join(wheres) if wheres else "1=1"

    sql = f"""
        SELECT
            l.id,
            l.cliente_id,
            c.nome AS cliente,
            l.data_inicio,
            l.data_fim_real,
            l.status,
            l.modo_cobranca,
            l.total_final,
            COALESCE(l.pago,0) AS pago,
            COALESCE(r.recebido,0) AS recebido
        FROM locacoes l
        JOIN clientes c ON c.id = l.cliente_id
        LEFT JOIN (
            SELECT locacao_id, COALESCE(SUM(valor),0) AS recebido
            FROM recebimentos
            GROUP BY locacao_id
        ) r ON r.locacao_id = l.id
        WHERE {where_sql}
        ORDER BY date(COALESCE(l.data_fim_real, l.data_inicio)) DESC, l.id DESC
    """

    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql(sql, conn, params=params)
        except Exception:
            return pd.DataFrame()

    if df.empty:
        return df

    df["total_final"] = df["total_final"].fillna(0).astype(float)
    df["recebido"] = df["recebido"].fillna(0).astype(float)
    df["saldo"] = df["total_final"] - df["recebido"]
    df["status_pagamento"] = df["pago"].apply(lambda x: "PAGA" if int(x) == 1 else "EM ABERTO")
    return df


@st.cache_data(show_spinner=False)
def locacao_resumo_mes(
    db_path_str: str,
    dt_ini_iso: str,
    dt_fim_iso: str,
    status: str | None,
    cliente_id: int | None,
) -> dict:
    """Resumo do mês: faturado (fechadas), recebido (pagamentos), abertas (contagem)."""
    df = locacao_listar(db_path_str, dt_ini_iso, dt_fim_iso, status, cliente_id)
    if df.empty:
        return {"qtd": 0, "faturado": 0.0, "recebido": 0.0, "abertas": 0}

    qtd = int(len(df))
    faturado = float(df[df["status"] == "Finalizado"]["total_final"].sum())
    # recebido aqui é por locação (somatório histórico). Para RECEBIDO NO PERÍODO, consultamos recebimentos por data:
    db_path = Path(db_path_str)
    recebido_periodo = 0.0
    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            wh = ["date(data_pagamento) >= date(?)", "date(data_pagamento) <= date(?)"]
            ps = [dt_ini_iso, dt_fim_iso]
            if cliente_id is not None:
                wh.append("locacao_id IN (SELECT id FROM locacoes WHERE cliente_id = ?)")
                ps.append(int(cliente_id))
            where_sql = " AND ".join(wh)
            try:
                rec = pd.read_sql(
                    f"SELECT COALESCE(SUM(valor),0) AS recebido FROM recebimentos WHERE {where_sql}",
                    conn,
                    params=ps,
                )
                recebido_periodo = float(rec.loc[0, "recebido"] or 0) if not rec.empty else 0.0
            except Exception:
                recebido_periodo = 0.0

    abertas = int((df["status"] == "Em andamento").sum())
    return {"qtd": qtd, "faturado": faturado, "recebido": recebido_periodo, "abertas": abertas}


def render_locacao_admin(db_path: Path):
    st.subheader("🚜 Locação — ADMIN (Dashboard / Relatórios)")

    view = st.radio("Navegação (Locação)", ["Dashboard", "Relatórios"], horizontal=True, key="loc_view")


    if not db_path.exists():
        st.warning("Banco de Locação não encontrado.")
        return

    # -------------------------
    # RELATÓRIOS (igual ao menu do módulo Locação)
    # -------------------------
    if view == "Relatórios":
        st.subheader("Relatório Mensal")

        hoje = date.today()
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            mes = st.selectbox("Mês", list(range(1, 13)), index=hoje.month - 1, key="loc_rep_mes")
        with c2:
            anos = list(range(hoje.year - 5, hoje.year + 1))
            ano = st.selectbox("Ano", anos, index=len(anos) - 1, key="loc_rep_ano")
        with c3:
            considerar_ate_hoje = st.checkbox(
                "Se for o mês atual, considerar somente até hoje (evita projeção até o fim do mês)",
                value=True,
                key="loc_rep_ate_hoje",
            )

        inicio_mes = date(int(ano), int(mes), 1)
        fim_mes = last_day_of_month(int(ano), int(mes))
        fim_analise = fim_mes
        if considerar_ate_hoje and (int(ano) == hoje.year and int(mes) == hoje.month):
            fim_analise = hoje

        st.caption(f"Período do relatório: {inicio_mes.strftime('%d/%m/%Y')} até {fim_analise.strftime('%d/%m/%Y')}")

        # filtros adicionais (cliente / status)
        c4, c5 = st.columns([2.5, 1.5])
        with c4:
            clientes = locacao_clientes(str(db_path))
            labels = ["(Todos)"] + [f"{cid} - {nome}" for cid, nome in clientes]
            pick = st.selectbox("Cliente", labels, key="loc_rep_cliente")
            cliente_id = None
            if pick != "(Todos)":
                cliente_id = int(pick.split(" - ")[0])
        with c5:
            status_sel = st.selectbox("Status", ["(Todos)", "Em andamento", "Finalizado", "Cancelado"], key="loc_rep_status")

        st.divider()

        # 1) Máquinas alugadas no mês
        st.markdown("### 1) Máquinas alugadas no mês (quantidade e valor estimado)")
        resumo = calcular_estimada_por_maquina_no_periodo(str(db_path), inicio_mes, fim_analise, status_sel, cliente_id)

        if resumo.empty:
            st.info("Nenhuma locação com itens no período selecionado.")
        else:
            previsto_mes = float(resumo["valor_estimado"].sum())
            colA, colB, colC = st.columns(3)
            colA.metric("Tipos de máquinas no mês", int(resumo.shape[0]))
            colB.metric("Qtd (somada) no mês", int(resumo["qtd_total"].sum()))
            colC.metric("Valor estimado do mês", br_money(previsto_mes))

            resumo_show = resumo.copy()
            resumo_show["valor_estimado"] = resumo_show["valor_estimado"].apply(br_money)
            resumo_show = resumo_show.rename(columns={
                "descricao": "Máquina",
                "qtd_total": "Quantidade (somada)",
                "valor_estimado": "Valor estimado (R$)",
            })
            st.dataframe(resumo_show.sort_values("Valor estimado (R$)", ascending=False), use_container_width=True)

            st.download_button(
                "⬇️ Baixar CSV - Máquinas no mês",
                data=resumo_show.to_csv(index=False).encode("utf-8"),
                file_name=f"relatorio_maquinas_mes_{ano}_{int(mes):02d}.csv",
                mime="text/csv",
                use_container_width=True,
                key="loc_rep_csv_maquinas",
            )

        st.divider()

        # 1.1) Pico do mês
        st.markdown("### 1.1) Pico do mês: máximo simultâneo por máquina")
        pico = max_simultaneo_no_periodo(str(db_path), inicio_mes, fim_analise, status_sel, cliente_id)
        if pico.empty:
            st.info("Sem dados suficientes para calcular o pico do mês.")
        else:
            pico_show = pico.rename(columns={
                "descricao": "Máquina",
                "pico_simultaneo": "Pico simultâneo (máx)",
            })
            st.dataframe(pico_show, use_container_width=True)
            st.download_button(
                "⬇️ Baixar CSV - Pico simultâneo",
                data=pico_show.to_csv(index=False).encode("utf-8"),
                file_name=f"pico_simultaneo_{ano}_{int(mes):02d}.csv",
                mime="text/csv",
                use_container_width=True,
                key="loc_rep_csv_pico",
            )

        st.divider()

        # 2) Situação atual por máquina
        st.markdown("### 2) Situação atual por máquina (alugadas agora x disponíveis)")
        with sqlite3.connect(db_path) as conn:
            alugadas_agora = pd.read_sql(
                """
                SELECT li.maquina_id, COALESCE(SUM(li.quantidade),0) as alugadas
                FROM locacao_itens li
                JOIN locacoes l ON l.id = li.locacao_id
                WHERE l.status='Em andamento'
                GROUP BY li.maquina_id
                """,
                conn,
            )
            maq = pd.read_sql(
                """
                SELECT id, descricao, categoria,
                       quantidade_total, quantidade_manutencao, quantidade_disponivel,
                       valor_diaria, valor_mensal
                FROM maquinas
                ORDER BY descricao
                """,
                conn,
            )

        if maq.empty:
            st.info("Nenhuma máquina cadastrada.")
        else:
            rel = maq.merge(alugadas_agora, how="left", left_on="id", right_on="maquina_id")
            rel["alugadas"] = rel["alugadas"].fillna(0).astype(int)
            for c in ["quantidade_total","quantidade_manutencao","quantidade_disponivel"]:
                rel[c] = rel[c].fillna(0).astype(int)

            rel_show = rel[[
                "descricao","categoria",
                "quantidade_total","quantidade_manutencao","alugadas","quantidade_disponivel",
                "valor_diaria","valor_mensal"
            ]].copy()

            rel_show = rel_show.rename(columns={
                "descricao": "Máquina",
                "categoria": "Categoria",
                "quantidade_total": "Total",
                "quantidade_manutencao": "Manutenção",
                "alugadas": "Alugadas agora",
                "quantidade_disponivel": "Disponíveis",
                "valor_diaria": "Diária",
                "valor_mensal": "Mensal",
            })
            st.dataframe(rel_show, use_container_width=True)
            st.download_button(
                "⬇️ Baixar CSV - Situação atual por máquina",
                data=rel_show.to_csv(index=False).encode("utf-8"),
                file_name=f"situacao_maquinas_{hoje.strftime('%Y_%m_%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="loc_rep_csv_situacao",
            )

        st.divider()

        # 3) Financeiro do mês (recebido x faturado fechado)
        st.markdown("### 3) Financeiro do mês (recebido x faturado fechado)")

        recebido_mes = recebido_no_periodo(str(db_path), inicio_mes, fim_analise, cliente_id)
        faturado_mes = faturado_fechado_no_periodo(str(db_path), inicio_mes, fim_analise, cliente_id)

        a_receber = max(0.0, float(faturado_mes) - float(recebido_mes))

        f1, f2, f3 = st.columns(3)
        f1.metric("Recebido no período", br_money(recebido_mes))
        f2.metric("Faturado (fechadas)", br_money(faturado_mes))
        f3.metric("A receber (aprox.)", br_money(a_receber))

        df_bar = pd.DataFrame({"Valor": [float(recebido_mes), float(faturado_mes), float(a_receber)]},
                              index=["Recebido", "Faturado", "A receber"])
        st.bar_chart(df_bar)

        return

    # filtros (Ano/Mês/Dia)
    anos = locacao_anos(str(db_path))
    if not anos:
        anos = [date.today().year]
    c1, c2, c3, c4 = st.columns([1.0, 1.2, 1.0, 2.0])

    with c1:
        ano_sel = st.selectbox("Ano", anos, index=len(anos)-1, key="loc_ano")
    with c2:
        meses = [
            "01 - Janeiro","02 - Fevereiro","03 - Março","04 - Abril","05 - Maio","06 - Junho",
            "07 - Julho","08 - Agosto","09 - Setembro","10 - Outubro","11 - Novembro","12 - Dezembro"
        ]
        mes_txt = st.selectbox("Mês", meses, index=date.today().month-1, key="loc_mes")
        mes_sel = int(mes_txt.split(" - ")[0])
    with c3:
        last_day = calendar.monthrange(int(ano_sel), int(mes_sel))[1]
        dias = ["(Todos)"] + [str(d).zfill(2) for d in range(1, last_day + 1)]
        dia_txt = st.selectbox("Dia", dias, key="loc_dia")
        dia_sel = None if dia_txt == "(Todos)" else int(dia_txt)
    with c4:
        status_sel = st.selectbox("Status", ["(Todos)", "Em andamento", "Finalizado", "Cancelado"], key="loc_status")

    c5, c6 = st.columns([2.5, 1.5])
    with c5:
        clientes = locacao_clientes(str(db_path))
        # selectbox com (Todos)
        labels = ["(Todos)"] + [f"{cid} - {nome}" for cid, nome in clientes]
        pick = st.selectbox("Cliente", labels, key="loc_cliente")
        cliente_id = None
        if pick != "(Todos)":
            cliente_id = int(pick.split(" - ")[0])
    with c6:
        st.caption("Dica: Status=Finalizado mostra o faturamento das locações fechadas no mês.")

    # intervalo calculado
    if dia_sel is not None:
        dt_ini = date(int(ano_sel), int(mes_sel), int(dia_sel))
        dt_fim = dt_ini
    else:
        dt_ini = date(int(ano_sel), int(mes_sel), 1)
        dt_fim = date(int(ano_sel), int(mes_sel), calendar.monthrange(int(ano_sel), int(mes_sel))[1])

    # dados + métricas
    resumo = locacao_resumo_mes(str(db_path), dt_ini.isoformat(), dt_fim.isoformat(), status_sel, cliente_id)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Locações", int(resumo["qtd"]))
    m2.metric("Faturado (fechadas)", br_money(resumo["faturado"]))
    m3.metric("Recebido no período", br_money(resumo["recebido"]))
    m4.metric("Abertas", int(resumo["abertas"]))

    # gráfico (sem Plotly: usa nativo do Streamlit)
    df_bar = pd.DataFrame(
        {"Valor": [float(resumo["faturado"]), float(resumo["recebido"])]},
        index=["Faturado", "Recebido"]
    )
    st.markdown("### 📊 Faturado x Recebido (período selecionado)")
    st.bar_chart(df_bar)

    # tabela
    df = locacao_listar(str(db_path), dt_ini.isoformat(), dt_fim.isoformat(), status_sel, cliente_id)
    if df.empty:
        st.info("Sem locações para os filtros selecionados.")
        return

    df_show = df.copy()
    # datas BR
    for col in ("data_inicio", "data_fim_real"):
        if col in df_show.columns:
            df_show[col] = pd.to_datetime(df_show[col], errors="coerce").dt.strftime("%d/%m/%Y").fillna(df_show[col].astype(str))

    df_show["total_final"] = df_show["total_final"].apply(br_money)
    df_show["recebido"] = df_show["recebido"].apply(br_money)
    df_show["saldo"] = df_show["saldo"].apply(br_money)

    df_show = df_show.rename(columns={
        "id": "Locação",
        "cliente": "Cliente",
        "data_inicio": "Início",
        "data_fim_real": "Fechamento",
        "status": "Status",
        "modo_cobranca": "Cobrança",
        "total_final": "Total",
        "recebido": "Recebido",
        "saldo": "Saldo",
        "status_pagamento": "Pagamento",
    })

    keep = ["Locação","Cliente","Início","Fechamento","Status","Cobrança","Total","Recebido","Saldo","Pagamento"]
    df_show = df_show[[c for c in keep if c in df_show.columns]]

    st.markdown("### Locações (filtradas)")
    st.dataframe(df_show, use_container_width=True, height=520)

    csv = df_show.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Baixar CSV (Locações)",
        data=csv,
        file_name=f"locacoes_{ano_sel}_{mes_sel:02d}_{'dia'+str(dia_sel).zfill(2) if dia_sel else 'mes'}.csv",
        mime="text/csv",
        use_container_width=True,
        key="loc_csv",
    )


# =========================
# ADM DE OBRAS (VISÃO GERAL)
# =========================



# -------------------------
# Fechamento de Período (PAGO/ABERTO)
# - no ADM de Obras o fechamento é por OBRA + PERÍODO
# - aqui no Admin Geral damos opção de fechar/reabrir o período para TODAS as obras
# -------------------------

def _adm_obras_status_por_periodo(conn: sqlite3.Connection, periodo_id: int) -> dict[int, bool]:
    """Retorna mapa {obra_id: fechado(True/False)} para um período."""
    try:
        df = pd.read_sql(
            """
            SELECT obra_id, COALESCE(fechado,0) AS fechado
            FROM obra_periodo_status
            WHERE periodo_id = ?
            """,
            conn,
            params=(int(periodo_id),),
        )
    except Exception:
        return {}

    if df.empty:
        return {}
    return {int(r.obra_id): bool(int(r.fechado)) for r in df.itertuples(index=False)}


def _adm_obras_set_periodo_fechado_para_todas(conn: sqlite3.Connection, periodo_id: int, fechado: bool):
    """Fecha (PAGO) ou reabre (ABERTO) o período para todas as obras."""
    now_iso = datetime.now().isoformat(timespec="seconds")
    obras = pd.read_sql("SELECT id AS obra_id FROM obras", conn)
    if obras.empty:
        return

    fechado_int = 1 if bool(fechado) else 0

    # garante tabela (se vier de banco muito antigo)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS obra_periodo_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            obra_id INTEGER,
            periodo_id INTEGER,
            fechado INTEGER DEFAULT 0,
            fechado_em TEXT DEFAULT NULL,
            reaberto_em TEXT DEFAULT NULL,
            UNIQUE(obra_id, periodo_id)
        )
        """
    )

    for obra_id in obras["obra_id"].astype(int).tolist():
        if fechado_int == 1:
            cur.execute(
                """
                INSERT INTO obra_periodo_status (obra_id, periodo_id, fechado, fechado_em, reaberto_em)
                VALUES (?, ?, 1, ?, NULL)
                ON CONFLICT(obra_id, periodo_id) DO UPDATE SET
                    fechado=1,
                    fechado_em=excluded.fechado_em,
                    reaberto_em=NULL
                """,
                (int(obra_id), int(periodo_id), now_iso),
            )
        else:
            cur.execute(
                """
                INSERT INTO obra_periodo_status (obra_id, periodo_id, fechado, fechado_em, reaberto_em)
                VALUES (?, ?, 0, NULL, ?)
                ON CONFLICT(obra_id, periodo_id) DO UPDATE SET
                    fechado=0,
                    fechado_em=NULL,
                    reaberto_em=excluded.reaberto_em
                """,
                (int(obra_id), int(periodo_id), now_iso),
            )

    conn.commit()

@st.cache_data(show_spinner=False)
def _adm_obras_periodos(db_path_str: str) -> pd.DataFrame:
    db_path = Path(db_path_str)
    if not db_path.exists():
        return pd.DataFrame(columns=["id", "numero", "dt_inicio", "dt_fim"])
    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql(
                "SELECT id, numero, dt_inicio, dt_fim FROM periodos ORDER BY numero DESC",
                conn,
            )
        except Exception:
            return pd.DataFrame(columns=["id", "numero", "dt_inicio", "dt_fim"])
    # normaliza
    if not df.empty:
        df["dt_inicio"] = df["dt_inicio"].astype(str)
        df["dt_fim"] = df["dt_fim"].astype(str)
    return df


@st.cache_data(show_spinner=False)
def _adm_obras_resumo_por_periodos(db_path_str: str, periodo_ids: list[int]) -> pd.DataFrame:
    """Retorna resumo por OBRA para uma lista de periodos (um ou vários)."""
    db_path = Path(db_path_str)
    if not db_path.exists() or not periodo_ids:
        return pd.DataFrame()

    # placeholders (?, ?, ?)
    ph = ",".join(["?"] * len(periodo_ids))

    with sqlite3.connect(db_path) as conn:
        try:
            obras = pd.read_sql("SELECT id AS obra_id, nome AS obra FROM obras ORDER BY nome", conn)
        except Exception:
            return pd.DataFrame()

        # Mão de obra (folha_semanal)
        mao = pd.read_sql(
            f"""
            SELECT
                periodo_id,
                obra_id,
                COALESCE(SUM(
                    COALESCE(seg,0)+COALESCE(ter,0)+COALESCE(qua,0)+COALESCE(qui,0)+COALESCE(sex,0)+COALESCE(sab,0)+COALESCE(laje_aditivo,0)
                ),0) AS valor_mao_obra
            FROM folha_semanal
            WHERE periodo_id IN ({ph})
            GROUP BY periodo_id, obra_id
            """,
            conn,
            params=periodo_ids,
        )

        # Encargos extras
        enc = pd.read_sql(
            f"""
            SELECT
                periodo_id,
                obra_id,
                COALESCE(SUM(COALESCE(valor,0)),0) AS encargos_extras
            FROM encargos_extras
            WHERE periodo_id IN ({ph})
            GROUP BY periodo_id, obra_id
            """,
            conn,
            params=periodo_ids,
        )

        # Notas (total_liquido salvo; se não existir, tenta total_liquido; se não, 0)
        # coluna total_liquido existe no seu módulo ADM de Obras (migração garante).
        notas = pd.read_sql(
            f"""
            SELECT
                periodo_id,
                obra_id,
                COALESCE(SUM(COALESCE(total_liquido,0)),0) AS valor_notas
            FROM compras_notas
            WHERE periodo_id IN ({ph})
            GROUP BY periodo_id, obra_id
            """,
            conn,
            params=periodo_ids,
        )

        # Parâmetros do relatório (semana, taxa admin, estorno)
        params_df = pd.read_sql(
            f"""
            SELECT
                periodo_id,
                obra_id,
                semana,
                COALESCE(taxa_admin_pct, 20.0) AS taxa_admin_pct,
                COALESCE(estorno_valor, 0.0) AS estorno_valor
            FROM relatorio_params
            WHERE periodo_id IN ({ph})
            """,
            conn,
            params=periodo_ids,
        )

        # Períodos (para datas e mês/ano)
        periodos = pd.read_sql(
            f"SELECT id AS periodo_id, numero AS periodo_num, dt_inicio, dt_fim FROM periodos WHERE id IN ({ph})",
            conn,
            params=periodo_ids,
        )

    if obras.empty or periodos.empty:
        return pd.DataFrame()

    # base: cruza obra x período (para aparecer mesmo se não tiver nada em uma obra)
    base = obras.assign(_k=1).merge(periodos.assign(_k=1), on="_k", how="outer").drop(columns=["_k"])

    # junta agregados
    df = base.merge(mao, on=["periodo_id", "obra_id"], how="left")
    df = df.merge(enc, on=["periodo_id", "obra_id"], how="left")
    df = df.merge(notas, on=["periodo_id", "obra_id"], how="left")
    df = df.merge(params_df, on=["periodo_id", "obra_id"], how="left")

    # defaults
    df["valor_mao_obra"] = df["valor_mao_obra"].fillna(0.0).astype(float)
    df["encargos_extras"] = df["encargos_extras"].fillna(0.0).astype(float)
    df["valor_notas"] = df["valor_notas"].fillna(0.0).astype(float)
    df["taxa_admin_pct"] = df["taxa_admin_pct"].fillna(20.0).astype(float)
    df["estorno_valor"] = df["estorno_valor"].fillna(0.0).astype(float)

    # semana pode ser nula (vira "")
    df["semana"] = df["semana"].fillna("").astype(str)

    # calcula valores
    df["valor_administrativo"] = (df["valor_mao_obra"] * (df["taxa_admin_pct"] / 100.0)).round(2)

    # Total: mão de obra + admin + encargos + notas - estorno
    df["total_quinzena"] = (
        df["valor_mao_obra"]
        + df["valor_administrativo"]
        + df["encargos_extras"]
        + df["valor_notas"]
        - df["estorno_valor"]
    ).round(2)

    # Mês/Ano baseado no início do período
    dt_ini = pd.to_datetime(df["dt_inicio"], errors="coerce")
    df["ano"] = dt_ini.dt.year.fillna(0).astype(int)
    df["mes_num"] = dt_ini.dt.month.fillna(0).astype(int)

    meses_map = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
        7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    df["mes"] = df["mes_num"].map(meses_map).fillna("")

    # Data do período BR
    def _br_date(iso):
        try:
            return datetime.fromisoformat(str(iso)).strftime("%d/%m/%Y")
        except Exception:
            try:
                return pd.to_datetime(iso, errors="coerce").strftime("%d/%m/%Y")
            except Exception:
                return ""

    df["data_periodo"] = df.apply(lambda r: f"{_br_date(r['dt_inicio'])} a {_br_date(r['dt_fim'])}", axis=1)

    # Organiza colunas no formato parecido com sua planilha
    out = df[[
        "obra_id",
        "periodo_id",
        "obra",
        "periodo_num",
        "mes",
        "ano",
        "data_periodo",
        "semana",
        "valor_mao_obra",
        "valor_administrativo",
        "encargos_extras",
        "valor_notas",
        "estorno_valor",
        "total_quinzena",
    ]].copy()

    out = out.rename(columns={
        "obra_id": "_obra_id",
        "periodo_id": "_periodo_id",
        "obra": "Obra",
        "periodo_num": "Período",
        "mes": "Mês",
        "ano": "Ano",
        "data_periodo": "Data do Período",
        "semana": "Semana",
        "valor_mao_obra": "Valor da Mão de Obra",
        "valor_administrativo": "Valor Administrativo",
        "encargos_extras": "Encargos Extras",
        "valor_notas": "Valor de Notas",
        "estorno_valor": "Estornos",
        "total_quinzena": "Total da Quinzena",
    })

    # Ordenação: período desc, obra asc
    out = out.sort_values(["Período", "Obra"], ascending=[False, True], kind="mergesort").reset_index(drop=True)

    return out


def render_adm_obras_geral(db_path: Path):
    st.subheader("🏗️ ADM de Obras — Mão de Obra (Visão Geral)")
    if not db_path.exists():
        st.warning("Banco do ADM de Obras não encontrado.")
        return

    # conexão para status/fechamento (botões)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)

    periodos_df = _adm_obras_periodos(str(db_path))
    if periodos_df.empty:
        st.info("Nenhum período cadastrado no ADM de Obras.")
        return

    # -------------------------
    # FILTROS
    # -------------------------
    c1, c2, c3 = st.columns([1.6, 1.0, 1.0])

    # lista anos/meses disponíveis pelos períodos
    dt_ini = pd.to_datetime(periodos_df["dt_inicio"], errors="coerce")
    periodos_df["ano"] = dt_ini.dt.year
    periodos_df["mes"] = dt_ini.dt.month

    anos_disp = sorted([int(a) for a in periodos_df["ano"].dropna().unique().tolist()]) or [date.today().year]

    with c1:
        modo = st.radio("Filtro", ["Por Período", "Por Mês/Ano"], horizontal=True, key="adm_obras_modo")

    with c2:
        ano_sel = st.selectbox("Ano", anos_disp, index=len(anos_disp)-1, key="adm_obras_ano")

    with c3:
        meses_lbl = [
            "01 - Janeiro","02 - Fevereiro","03 - Março","04 - Abril","05 - Maio","06 - Junho",
            "07 - Julho","08 - Agosto","09 - Setembro","10 - Outubro","11 - Novembro","12 - Dezembro"
        ]
        mes_def = date.today().month - 1
        mes_txt = st.selectbox("Mês", meses_lbl, index=mes_def, key="adm_obras_mes")
        mes_sel = int(mes_txt.split(" - ")[0])

    if modo == "Por Período":
        # filtra períodos do mês/ano escolhido para facilitar a busca
        pool = periodos_df[(periodos_df["ano"] == int(ano_sel)) & (periodos_df["mes"] == int(mes_sel))].copy()
        if pool.empty:
            pool = periodos_df.copy()

        opcoes = pool.sort_values("numero", ascending=False)["numero"].tolist()
        periodo_num = st.selectbox("Período (número)", opcoes, key="adm_obras_periodo_num")
        periodo_ids = periodos_df.loc[periodos_df["numero"] == int(periodo_num), "id"].astype(int).tolist()
        titulo = f"Período {int(periodo_num)}"
    else:
        pool = periodos_df[(periodos_df["ano"] == int(ano_sel)) & (periodos_df["mes"] == int(mes_sel))]
        periodo_ids = pool["id"].astype(int).tolist()
        titulo = f"{int(ano_sel)} / {int(mes_sel):02d} (todos os períodos do mês)"

    st.caption(f"Exibindo: **{titulo}**")

    df_out = _adm_obras_resumo_por_periodos(str(db_path), periodo_ids)

    if df_out is None or df_out.empty:
        st.info("Sem dados para os filtros selecionados.")
        return

    # -------------------------
    # DASHBOARD (comparar períodos)
    # -------------------------
    with st.expander("📊 Dashboard — Comparar períodos", expanded=(modo != "Por Período")):
        # total por período
        df_dash = df_out.copy()
        # remove linhas vazias de período
        df_dash["Período"] = pd.to_numeric(df_dash["Período"], errors="coerce")
        df_dash = df_dash.dropna(subset=["Período"]).copy()
        df_dash["Período"] = df_dash["Período"].astype(int)

        g = df_dash.groupby("Período", as_index=True).agg(
            mao_obra=("Valor da Mão de Obra", "sum"),
            admin=("Valor Administrativo", "sum"),
            encargos=("Encargos Extras", "sum"),
            notas=("Valor de Notas", "sum"),
            estornos=("Estornos", "sum"),
            total=("Total da Quinzena", "sum"),
        ).sort_index()

        cA, cB = st.columns(2)
        with cA:
            st.markdown("**Total da Quinzena por Período**")
            st.bar_chart(g[["total"]])

        with cB:
            st.markdown("**Mão de Obra por Período**")
            st.bar_chart(g[["mao_obra"]])

        st.markdown("**Resumo (R$)**")
        g_show = g.copy()
        for col in g_show.columns:
            g_show[col] = g_show[col].apply(br_money)
        st.dataframe(g_show.reset_index(), use_container_width=True)

    # -------------------------
    # TABELAS SEPARADAS POR PERÍODO
    # -------------------------
    periodos_unicos = (
        pd.to_numeric(df_out["Período"], errors="coerce")
          .dropna()
          .astype(int)
          .unique()
          .tolist()
    )
    periodos_unicos = sorted(periodos_unicos, reverse=True)

    # helper: renderiza 1 tabela do período com totais e export
    def _render_tabela_periodo(df_p: pd.DataFrame, periodo_num: int):
        if df_p.empty:
            return

        # Situação (PAGO/ABERTO) pelo fechamento do período (por obra)
        periodo_id = None
        if "_periodo_id" in df_p.columns and not df_p["_periodo_id"].isna().all():
            try:
                periodo_id = int(df_p["_periodo_id"].iloc[0])
            except Exception:
                periodo_id = None

        status_map = _adm_obras_status_por_periodo(conn, periodo_id) if periodo_id is not None else {}

        if "_obra_id" in df_p.columns:
            df_p["Situação"] = df_p["_obra_id"].apply(lambda oid: "PAGO" if status_map.get(int(oid), False) else "ABERTO")
        else:
            df_p["Situação"] = ""

        # Totais do período
        totais = {
            "Obra": "TOTAIS",
            "Período": "",
            "Mês": "",
            "Ano": "",
            "Data do Período": "",
            "Semana": "",
            "Valor da Mão de Obra": float(df_p["Valor da Mão de Obra"].sum()),
            "Valor Administrativo": float(df_p["Valor Administrativo"].sum()),
            "Encargos Extras": float(df_p["Encargos Extras"].sum()),
            "Valor de Notas": float(df_p["Valor de Notas"].sum()),
            "Estornos": float(df_p["Estornos"].sum()),
            "Total da Quinzena": float(df_p["Total da Quinzena"].sum()),
            "Situação": "",
        }

        df_show = df_p.copy()

        # não mostrar colunas internas
        for c in ["_obra_id", "_periodo_id"]:
            if c in df_show.columns:
                df_show = df_show.drop(columns=[c])

        for col in ["Valor da Mão de Obra", "Valor Administrativo", "Encargos Extras", "Valor de Notas", "Estornos", "Total da Quinzena"]:
            df_show[col] = df_show[col].apply(br_money)

        df_show = pd.concat([df_show, pd.DataFrame([{
            **totais,
            "Valor da Mão de Obra": br_money(totais["Valor da Mão de Obra"]),
            "Valor Administrativo": br_money(totais["Valor Administrativo"]),
            "Encargos Extras": br_money(totais["Encargos Extras"]),
            "Valor de Notas": br_money(totais["Valor de Notas"]),
            "Estornos": br_money(totais["Estornos"]),
            "Total da Quinzena": br_money(totais["Total da Quinzena"]),
        }])], ignore_index=True)

        # Cabeçalho do período (com datas)
        data_periodo = str(df_p["Data do Período"].iloc[0] or "")
        st.markdown(f"### Período {int(periodo_num)}  \n{data_periodo}")

        st.dataframe(df_show, use_container_width=True, height=420)

        st.download_button(
            f"⬇️ Baixar CSV — Período {int(periodo_num)}",
            data=df_p.to_csv(index=False).encode("utf-8"),
            file_name=f"adm_obras_periodo_{int(periodo_num)}_{int(ano_sel)}_{int(mes_sel):02d}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"adm_obras_csv_{int(periodo_num)}",
        )

    # Se veio mais de 1 período (modo mês/ano), separa por período (igual sua planilha)
    if len(periodos_unicos) > 1:
        for p in periodos_unicos:
            df_p = df_out[df_out["Período"].astype(int) == int(p)].copy()
            _render_tabela_periodo(df_p, int(p))
            st.divider()

        # Total do mês (opcional, ajuda muito)
        with st.expander("📌 Total geral do mês (somando todos os períodos)"):
            totais_mes = {
                "Obra": "TOTAIS",
                "Período": "",
                "Mês": "",
                "Ano": "",
                "Data do Período": "",
                "Semana": "",
                "Valor da Mão de Obra": float(df_out["Valor da Mão de Obra"].sum()),
                "Valor Administrativo": float(df_out["Valor Administrativo"].sum()),
                "Encargos Extras": float(df_out["Encargos Extras"].sum()),
                "Valor de Notas": float(df_out["Valor de Notas"].sum()),
                "Estornos": float(df_out["Estornos"].sum()),
                "Total da Quinzena": float(df_out["Total da Quinzena"].sum()),
            }
            df_mes = pd.DataFrame([totais_mes])
            for col in ["Valor da Mão de Obra", "Valor Administrativo", "Encargos Extras", "Valor de Notas", "Estornos", "Total da Quinzena"]:
                df_mes[col] = df_mes[col].apply(br_money)
            st.dataframe(df_mes, use_container_width=True)
            st.download_button(
                "⬇️ Baixar CSV — Mês (todos os períodos)",
                data=df_out.to_csv(index=False).encode("utf-8"),
                file_name=f"adm_obras_mes_{int(ano_sel)}_{int(mes_sel):02d}.csv",
                mime="text/csv",
                use_container_width=True,
                key="adm_obras_csv_mes",
            )
    else:
        # Só 1 período selecionado
        p = int(periodos_unicos[0]) if periodos_unicos else 0
        _render_tabela_periodo(df_out.copy(), p)



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

        if tab_name == "🚜 Locação":
            render_locacao_admin(db_path)

            st.divider()
            with st.expander("🔧 Modo técnico (ver tabelas cruas do banco)", expanded=False):
                st.subheader("🚜 Locação (Tabelas)")
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

                        df_raw = read_table(str(db_path), table, int(limit))
                        if df_raw.empty:
                            st.info("Sem dados para exibir (ou tabela inválida).")
                        else:
                            st.dataframe(df_raw, use_container_width=True, height=500)
                            csv = df_raw.to_csv(index=False).encode("utf-8")
                            st.download_button(
                                "⬇️ Baixar CSV",
                                data=csv,
                                file_name=f"{tab_name}_{table}.csv",
                                mime="text/csv",
                                use_container_width=True,
                                key=f"{tab_name}_{table}_csv",
                            )
            continue


        if tab_name == "🏗️ ADM de Obras":
            render_adm_obras_geral(db_path)

            st.divider()
            with st.expander("🔧 Modo técnico (ver tabelas cruas do banco)", expanded=False):
                st.subheader("🏗️ ADM de Obras (Tabelas)")
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

                        df_raw = read_table(str(db_path), table, int(limit))
                        if df_raw.empty:
                            st.info("Sem dados para exibir (ou tabela inválida).")
                        else:
                            st.dataframe(df_raw, use_container_width=True, height=500)
                            csv = df_raw.to_csv(index=False).encode("utf-8")
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
