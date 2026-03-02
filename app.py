import streamlit as st
import os

# 🔐 Conecta Secrets (Streamlit Cloud) ao sistema
if "DATABASE_URL" in st.secrets and not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = st.secrets["DATABASE_URL"]

st.set_page_config(page_title="Sistema Unificado", layout="wide")
st.title("Sistema Unificado")

st.write("Escolha o módulo que você quer abrir:")

c1, c2, c3 = st.columns(3)

with c1:
    if st.button("🏢 Escritório", use_container_width=True):
        st.switch_page("pages/1_🏢_Escritorio.py")

with c2:
    if st.button("🚜 Locação", use_container_width=True):
        st.switch_page("pages/2_🚜_Locacao.py")

with c3:
    if st.button("🏗️ ADM de Obras", use_container_width=True):
        st.switch_page("pages/3_🏗️_ADM_de_Obras.py")

st.divider()
st.caption("Login está preservado no código, mas desativado por enquanto via config.py (LOGIN_ATIVO=False).")
