import os
import re
from typing import Any, Iterable, Optional, Sequence

# =========================================================
# ✅ GARANTE DATABASE_URL vindo do Streamlit Secrets
# - No Streamlit Cloud, Secrets nem sempre viram os.environ
# - Então a gente puxa de st.secrets e joga no os.environ
# - Fazemos isso AQUI porque todas as páginas importam db_adapter
# =========================================================
try:
    import streamlit as st  # só existe quando rodando em Streamlit
    if "DATABASE_URL" in st.secrets and not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = st.secrets["DATABASE_URL"]
except Exception:
    # rodando fora do Streamlit / sem secrets / etc.
    pass

BACKEND_SQLITE = "sqlite"
BACKEND_POSTGRES = "postgres"

def backend() -> str:
    return BACKEND_POSTGRES if os.environ.get("DATABASE_URL") else BACKEND_SQLITE

def connect_sqlite(db_path: str):
    import sqlite3
    return sqlite3.connect(db_path, check_same_thread=False)

def connect_postgres():
    import psycopg2
    # Supabase exige SSL; a URI normalmente já funciona. Se não, força sslmode=require.
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL não definido. Configure no Streamlit Secrets.")
    if "sslmode=" not in url:
        sep = "&" if "?" in url else "?"
        url = url + f"{sep}sslmode=require"
    return psycopg2.connect(url)

def _set_search_path(conn, schema: str):
    # funciona no Postgres; no SQLite não faz nada
    if backend() != BACKEND_POSTGRES:
        return
    cur = conn.cursor()
    cur.execute(f'SET search_path TO "{schema}", public')
    conn.commit()

def ensure_schema(conn, schema: str):
    if backend() != BACKEND_POSTGRES:
        return
    cur = conn.cursor()
    cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    conn.commit()
    _set_search_path(conn, schema)

def get_conn(sqlite_db_path: str, schema: Optional[str] = None):
    if backend() == BACKEND_SQLITE:
        return connect_sqlite(sqlite_db_path)
    conn = connect_postgres()
    if schema:
        ensure_schema(conn, schema)
    return conn

# ----------------------------
# Cursor adapter (SQLite SQL -> Postgres)
# - converte placeholders ? -> %s
# - ignora PRAGMA
# - converte CREATE TABLE com AUTOINCREMENT
# - converte strftime('%Y-%m', col) -> substr(col,1,7)
# - converte consultas em sqlite_master
# ----------------------------

_STRFTIME_RE = re.compile(r"strftime\(\s*'(%[^']+)'\s*,\s*([a-zA-Z0-9_\.]+)\s*\)")

def _convert_strftime(sql: str) -> str:
    def repl(m):
        fmt = m.group(1)
        col = m.group(2)
        # seus dados de data costumam ser 'YYYY-MM-DD' (TEXT). Dá pra extrair com substr.
        if fmt == "%Y-%m":
            return f"substr({col},1,7)"
        if fmt == "%Y":
            return f"substr({col},1,4)"
        if fmt in ("%m/%Y",):
            # MM/YYYY
            return f"(substr({col},6,2) || '/' || substr({col},1,4))"
        # fallback: tenta YYYY-MM
        return f"substr({col},1,7)"
    return _STRFTIME_RE.sub(repl, sql)

def _strip_sqlite_comments(sql: str) -> str:
    # remove comentários inline "-- ..."
    lines = []
    for line in sql.splitlines():
        if "--" in line:
            line = line.split("--", 1)[0]
        lines.append(line)
    return "\n".join(lines)

def _convert_create_table(sql: str) -> str:
    s = _strip_sqlite_comments(sql)
    s = s.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    # Tipos
    s = re.sub(r"\bREAL\b", "DOUBLE PRECISION", s, flags=re.IGNORECASE)
    # SQLite aceita "TEXT"; Postgres também.
    return s

def _convert_sqlite_master(sql: str) -> str:
    # casos comuns usados para listar tabelas
    if "sqlite_master" not in sql:
        return sql
    # lista tabelas
    # ex: SELECT name FROM sqlite_master WHERE type='table'
    if re.search(r"SELECT\s+name\s+FROM\s+sqlite_master", sql, flags=re.IGNORECASE):
        return "SELECT tablename AS name FROM pg_tables WHERE schemaname = current_schema()"
    return sql

def _convert_placeholders(sql: str) -> str:
    # converte ? -> %s (não perfeito para casos dentro de strings, mas atende seu app)
    return sql.replace("?", "%s")

def convert_sql(sql: str) -> Optional[str]:
    if sql is None:
        return None
    s = sql.strip()
    if s.upper().startswith("PRAGMA"):
        return None  # no-op no Postgres
    s = _convert_sqlite_master(s)
    if s.upper().startswith("CREATE TABLE"):
        s = _convert_create_table(s)
    s = _convert_strftime(s)
    s = _convert_placeholders(s)
    return s

class CursorAdapter:
    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql: str, params: Sequence[Any] = ()):
        sql2 = convert_sql(sql)
        if sql2 is None:
            return self
        self._cur.execute(sql2, params)
        return self

    def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any]]):
        sql2 = convert_sql(sql)
        if sql2 is None:
            return self
        self._cur.executemany(sql2, seq_of_params)
        return self

    def fetchall(self):
        return self._cur.fetchall()

    def fetchone(self):
        return self._cur.fetchone()

    def __getattr__(self, name):
        return getattr(self._cur, name)

def get_cursor(conn):
    cur = conn.cursor()
    if backend() == BACKEND_POSTGRES:
        return CursorAdapter(cur)
    return cur
