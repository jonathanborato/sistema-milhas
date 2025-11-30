import streamlit as st
import pandas as pd
import banco # Importa nosso backend
import time

# --- CONFIGURAÇÃO VISUAL ---
st.set_page_config(
    page_title="MilhasPro | Intelligence",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializa tabelas locais (cache)
banco.iniciar_banco()

# --- CSS ---
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #ff4b4b;}
    div.stButton > button:first-child {width: 100%;}
</style>
""", unsafe_allow_html=True)

# --- SESSÃO ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

# ==============================================================================
# VIEW 1: LANDING PAGE & LOGIN
# ==============================================================================
def tela_login():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    
    with c2:
        st.markdown("<div style='text-align: center; margin-top: 50px;'><h1>✈️ MilhasPro</h1><p>Gestão Profissional de Ativos Aéreos</p></div>", unsafe_allow_html=True)
        
        tab_entrar, tab_criar = st.tabs(["🔒 Acessar Painel", "✨ Criar Nova Conta"])
        
        with tab_entrar:
            # ADICIONEI key="..." PARA EVITAR O ERRO DE DUPLICIDADE
            email = st.text_input("E-mail", key="login_email")
            senha = st.text_input("Senha", type="password", key="login_pass")
            
            if st.button("ENTRAR", type="primary", key="btn_entrar"):
                # 1. Admin (Backdoor via Secrets)
                try:
                    if email == st.secrets["admin"]["email"] and senha == st.secrets["admin"]["senha"]:
                        st.session_state['user'] = {"nome": st.secrets["admin"]["nome"], "email": email, "plano": "Admin"}
                        st.rerun()
                except: pass
                
                # 2. Login Supabase (Nuvem)
                usuario = banco.autenticar_usuario(email, senha)
                if usuario:
                    st.session_state['user'] = {"nome": usuario['nome'], "email": email, "plano": usuario['plano']}
                    st.toast("Sucesso!", icon="✅")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Dados incorretos ou erro de conexão.")
        
        with tab_criar:
            st.info("☁️ Seus dados serão salvos na nuvem segura.")
            # ADICIONEI key="..." AQUI TAMBÉM
            nome = st.text_input("Nome Completo", key="cad_nome")
            cad_email = st.text_input("E-mail para cadastro", key="cad_email")
            cad_tel = st.text_input("WhatsApp", key="cad_tel")
            cad_senha = st.text_input("Crie uma Senha", type="password", key="cad_pass")
            
            if st.button("CRIAR CONTA", key="btn_criar"):
                if len(cad_senha) < 4:
                    st.warning("Senha curta.")
                else:
                    # Chama o banco.py para registrar no Supabase
                    ok, msg = banco.registrar_usuario(nome, cad_email, cad_senha, cad_tel)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

# ==============================================================================
# VIEW 2: SISTEMA LOGADO
# ==============================================================================
def sistema_logado():
    user = st.session_state['user']
    
    with st.sidebar:
        try: st.image("https://cdn-icons-png.flaticon.com/512/723/723955.png", width=80)
        except: pass
        
        st.write(f"Olá, **{user['nome']}**")
        
        if user['plano'] == "Admin": st.success("👑 ADMIN")
        elif user['plano'] == "Pro": st.success("⭐ PRO")
        else: st.info("🔹 FREE")
            
        st.divider()
        menu = st.radio("Menu", ["Dashboard Geral", "Minha Carteira", "Mercado P2P", "Promoções"])
        st.divider()
        if st.button("Sair"):
            st.session_state['user'] = None
            st.rerun()

    # ---
