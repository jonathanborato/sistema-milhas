import streamlit as st
import pandas as pd
import banco # Importa nosso backend limpo que conecta no Supabase
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
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            
            if st.button("ENTRAR", type="primary"):
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
            st.info("☁️ Seus dados serão salvos na nuvem segura (Supabase).")
            nome = st.text_input("Nome Completo")
            cad_email = st.text_input("E-mail para cadastro")
            cad_tel = st.text_input("WhatsApp")
            cad_senha = st.text_input("Senha", type="password")
            
            if st.button("CRIAR CONTA"):
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
        # Tenta colocar imagem, se falhar nao quebra
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

    # --- CARREGAMENTO ---
    df_cotacoes = banco.ler_dados_historico()
    
    # --- DASHBOARD ---
    if menu == "Dashboard Geral":
        st.title("📊 Visão de Mercado")
        if not df_cotacoes.empty:
            st.line_chart(df_cotacoes, x="data_hora", y="cpm", color="programa")
        else: st.warning("Sem dados.")

    # --- CARTEIRA ---
    elif menu == "Minha Carteira":
        st.title("💼 Carteira")
        with st.expander("➕ Adicionar"):
            c1, c2, c3 = st.columns(3)
            p = c1.selectbox("Programa", ["Latam Pass", "Smiles", "Azul", "Livelo"])
            q = c2.number_input("Qtd", 1000, step=1000)
            v = c3.number_input("R$ Total", 0.0, step=10.0)
            if st.button("Salvar"):
                banco.adicionar_carteira(user['email'], p, q, v)
                st.rerun()
        
        dfc = banco.ler_carteira_usuario(user['email'])
        if not dfc.empty:
            st.dataframe(dfc)
            rid = st.number_input("ID Remover", step=1)
            if st.button("Remover"):
                banco.remover_carteira(rid)
                st.rerun()
        else: st.info("Vazia.")

    # --- P2P ---
    elif menu == "Mercado P2P":
        st.title("📢 P2P Manual")
        with st.form("p2p"):
            c1, c2 = st.columns(2)
            g = c1.text_input("Grupo")
            p = c2.selectbox("Prog", ["Latam", "Smiles"])
            t = st.radio("Tipo", ["VENDA", "COMPRA"])
            val = st.number_input("Valor", 15.0)
            obs = st.text_input("Obs")
            if st.form_submit_button("Salvar"):
                banco.adicionar_oferta_p2p(g, p, t, val, obs)
                st.rerun()
        dfp2p = banco.ler_p2p()
        if not dfp2p.empty: st.dataframe(dfp2p)

    # --- PROMOS ---
    elif menu == "Promoções":
        st.title("🔥 Radar")
        try:
            con = sqlite3.connect("milhas.db")
            dfp = pd.read_sql_query("SELECT * FROM promocoes ORDER BY id DESC LIMIT 15", con)
            con.close()
            for _, r in dfp.iterrows(): st.markdown(f"[{r['titulo']}]({r['link']})")
        except: pass

# MAIN
if st.session_state['user']: sistema_logado()
else: tela_login()
