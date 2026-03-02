def connect_postgres():
    """
    Conexão Postgres (Supabase) robusta para Streamlit Cloud:
    - garante sslmode=require
    - força IPv4 REAL (evita erro IPv6: Cannot assign requested address)
    - timeout para não travar app
    """
    import psycopg2
    import socket

    url = _get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL não definido. Configure no Streamlit Secrets.")

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
            host_ipv4 = None

    if host_ipv4:
        return psycopg2.connect(
            url,
            connect_timeout=10,
            hostaddr=host_ipv4,  # ✅ força IPv4
            host=host,
            port=port,
        )

    return psycopg2.connect(url, connect_timeout=10)
