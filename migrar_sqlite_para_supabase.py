"""Migra seus bancos SQLite para o Supabase Postgres (schemas separados).

Como usar (no seu PC):
1) Instale dependências:
   pip install psycopg2-binary pandas
2) Defina a variável DATABASE_URL (ou edite abaixo)
   - No Windows PowerShell:
     $env:DATABASE_URL="postgresql://postgres:SENHA@db.xxx.supabase.co:5432/postgres?sslmode=require"
3) Rode:
   python migrar_sqlite_para_supabase.py

Ele vai criar schemas e copiar todas as tabelas/linhas.
"""

import os, sqlite3, re
import psycopg2

SQLITE_DBS = {
    "financeiro": "banco.db",
    "locacao": "locacao.db",
    "adm_obras": "banco_adm_obras.db",
    "fabrica": "fabrica.db",
    "fabrica_lajes": "fabrica_lajes.db",
    "banco_novo": "banco_novo.db",
}

def ensure_schema(pg_conn, schema: str):
    cur = pg_conn.cursor()
    cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    pg_conn.commit()

def set_search_path(pg_conn, schema: str):
    cur = pg_conn.cursor()
    cur.execute(f'SET search_path TO "{schema}", public')
    pg_conn.commit()

def strip_comments(sql: str) -> str:
    out=[]
    for line in sql.splitlines():
        if "--" in line:
            line=line.split("--",1)[0]
        out.append(line)
    return "\n".join(out)

def sqlite_create_to_postgres(sql: str) -> str:
    s = strip_comments(sql)
    s = s.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    s = re.sub(r"\bREAL\b", "DOUBLE PRECISION", s, flags=re.IGNORECASE)
    return s

def migrate_one(sqlite_path: str, pg_conn, schema: str):
    if not os.path.exists(sqlite_path):
        print(f"[pular] não achei {sqlite_path}")
        return
    ensure_schema(pg_conn, schema)
    set_search_path(pg_conn, schema)

    sq = sqlite3.connect(sqlite_path)
    sq.row_factory = sqlite3.Row
    cur = sq.cursor()
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = cur.fetchall()

    pg_cur = pg_conn.cursor()

    for t in tables:
        name = t["name"]
        create_sql = t["sql"]
        if not create_sql:
            continue
        pg_create = sqlite_create_to_postgres(create_sql)
        pg_cur.execute(pg_create)
    pg_conn.commit()

    for t in tables:
        name = t["name"]
        cur.execute(f'SELECT * FROM "{name}"')
        rows = cur.fetchall()
        if not rows:
            continue
        cols = rows[0].keys()
        col_list = ", ".join([f'"{c}"' for c in cols])
        placeholders = ", ".join(["%s"] * len(cols))
        insert_sql = f'INSERT INTO "{name}" ({col_list}) VALUES ({placeholders})'
        data = [tuple(r[c] for c in cols) for r in rows]
        pg_cur.executemany(insert_sql, data)
        pg_conn.commit()
        print(f"[ok] {schema}.{name}: {len(rows)} linhas")

    sq.close()

def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Defina DATABASE_URL antes de rodar (mesma string do Streamlit Secrets).")
    if "sslmode=" not in url:
        sep = "&" if "?" in url else "?"
        url = url + f"{sep}sslmode=require"
    pg = psycopg2.connect(url)
    base_dir = os.path.dirname(os.path.abspath(__file__))

    for schema, dbfile in SQLITE_DBS.items():
        migrate_one(os.path.join(base_dir, dbfile), pg, schema)

    pg.close()
    print("\nFinalizado! Agora seu app online vai ver os mesmos dados do PC/tablet.")

if __name__ == "__main__":
    main()
