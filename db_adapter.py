import os
import re
import socket
from typing import Any, Iterable, Optional, Sequence
from urllib.parse import urlparse, urlunparse

BACKEND_SQLITE = "sqlite"
BACKEND_POSTGRES = "postgres"


def _get_database_url() -> Optional[str]:
    """
    Lê DATABASE_URL de forma "à prova de Streamlit":
    - primeiro tenta os.environ
    - depois tenta st.secrets (funciona em qualquer página do Streamlit)
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    try:
        import streamlit as st  # type: ignore
        url = st.secrets.get("DATABASE_URL")  # type: ignore
        if url:
            os.environ["DATABASE_URL"] = str(url)
            return str(url)
    except Exception:
        pass

    return None


def backend() -> str:
    return BACKEND_POSTGRES if _get_database_url() else BACKEND_SQLITE


def connect_sqlite(db_path: str):
    import sqlite3
    return sqlite3.connect(db_path, check_same_thread=False)


def _ensure_sslmode(url: str) -> str:
    if "sslmode=" in url:
        return url
    sep = "&" if "?" in url else "?"
    return url + f"{sep}sslmode=require"


def _try_resolve_ipv4(hostname: str) -> Optional[str]:
    """
    Tenta pegar um IPv4 (A record). Se o host só tiver IPv6, retorna None.
    """
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
        if infos:
            return infos[0][4][0]
    except Exception:
        pass
    return None


def connect_postgres():
    """
    Conexão Postgres (Supabase) robusta:
    - exige sslmode=require
    - tenta forçar IPv4 quando possível (evita Cannot assign requested address)
    - timeout para não travar app
    """
    import psycopg2

    url = _get_database_url()
    if not url:
        raise RuntimeError(
            "DATABASE_URL não definido. Configure em Streamlit → App → Settings → Secrets."
        )

    url = _ensure_sslmode(url)

    parsed = urlparse(url)
    host = parsed.hostname

    # Se tiver host, tenta forçar IPv4. Se o host não tiver IPv4, deixa como está
    # e você deve trocar o DATABASE_URL para o POOLER (recomendado).
    if host:
        ipv4 = _try_resolve_ipv4(host)
        if ipv4:
            # psycopg2 aceita 'hostaddr' (força o IP) mantendo o host original no DSN
            # Para isso, conectamos via kwargs em vez de substituir a URL inteira.
            return psycopg2.connect(url, connect_timeout=10, hostaddr=ipv4)

    # fallback normal
    return psycopg2.connect(url, connect_timeout=10)


def _set_search_path(conn, schema: str):
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
# ----------------------------

_STRFTIME_RE = re.compile(r"strftime\(\s*'(%[^']+)'\s*,\s*([a-zA-Z0-9_\.]+)\s*\)")
_PRAGMA_TABLE_INFO_RE = re.compile(
    r"PRAGMA\s+table_info\s*\(\s*([a-zA-Z0-9_]+)\s*\)\s*;?\s*$", re.IGNORECASE
)


def _convert_strftime(sql: str) -> str:
    def repl(m):
        fmt = m.group(1)
        col = m.group(2)
        if fmt == "%Y-%m":
            return f"substr({col},1,7)"
        if fmt == "%Y":
            return f"substr({col},1,4)"
        if fmt in ("%m/%Y",):
            return f"(substr({col},6,2) || '/' || substr({col},1,4))"
        return f"substr({col},1,7)"
    return _STRFTIME_RE.sub(repl, sql)


def _strip_sqlite_comments(sql: str) -> str:
    lines = []
    for line in sql.splitlines():
        if "--" in line:
            line = line.split("--", 1)[0]
        lines.append(line)
    return "\n".join(lines)


def _convert_create_table(sql: str) -> str:
    s = _strip_sqlite_comments(sql)
    s = s.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    s = re.sub(r"\bREAL\b", "DOUBLE PRECISION", s, flags=re.IGNORECASE)
    return s


def _convert_sqlite_master(sql: str) -> str:
    if "sqlite_master" not in sql:
        return sql
    if re.search(r"SELECT\s+name\s+FROM\s+sqlite_master", sql, flags=re.IGNORECASE):
        return "SELECT tablename AS name FROM pg_tables WHERE schemaname = current_schema()"
    return sql


def _convert_pragma_table_info(sql: str) -> Optional[str]:
    m = _PRAGMA_TABLE_INFO_RE.match(sql.strip())
    if not m:
        return None

    table = m.group(1)

    return f"""
    SELECT
        0 AS cid,
        c.column_name AS name,
        c.data_type AS type,
        0 AS notnull,
        NULL AS dflt_value,
        0 AS pk
    FROM information_schema.columns c
    WHERE c.table_schema = current_schema()
      AND c.table_name = '{table}'
    ORDER BY c.ordinal_position
    """.strip()


def _convert_placeholders(sql: str) -> str:
    return sql.replace("?", "%s")


def convert_sql(sql: str) -> Optional[str]:
    if sql is None:
        return None

    s = sql.strip()
    if not s:
        return s

    pragma_conv = _convert_pragma_table_info(s)
    if pragma_conv:
        return pragma_conv

    if s.upper().startswith("PRAGMA"):
        return None

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
