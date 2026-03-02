import os
import socket
from typing import Optional
from urllib.parse import urlparse

BACKEND_SQLITE = "sqlite"
BACKEND_POSTGRES = "postgres"


def _get_database_url() -> Optional[str]:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL")
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


def connect_postgres():
    import psycopg2

    url = _get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL não definido.")

    if "sslmode=" not in url:
        sep = "&" if "?" in url else "?"
        url = url + f"{sep}sslmode=require"

    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or 5432

    host_ipv4 = None
    if host:
        try:
            infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
            host_ipv4 = infos[0][4][0]
        except Exception:
            pass

    if host_ipv4:
        return psycopg2.connect(
            url,
            connect_timeout=10,
            hostaddr=host_ipv4,
            host=host,
            port=port,
        )

    return psycopg2.connect(url, connect_timeout=10)


def get_conn(sqlite_db_path: str):
    if backend() == BACKEND_SQLITE:
        return connect_sqlite(sqlite_db_path)
    return connect_postgres()


def get_cursor(conn):
    return conn.cursor()
