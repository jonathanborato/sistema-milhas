import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import time
from datetime import datetime

# --- 1. CONFIGURAÇÃO INICIAL (DEVE SER A PRIMEIRA LINHA) ---
st.set_page_config(
    page_title="MilhasPro System",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CONEXÃO COM SUPABASE (TENTA NUVEM, SE FALHAR USA LOCAL) ---
try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# --- 3. BACKEND (DADOS E SEGURANÇA) ---
NOME_BANCO_LOCAL = "milhas.db"

def conectar_local():
    return sqlite3.connect(NOME_BANCO_LOCAL)

def iniciar_banco():
    con = conectar_local()
    cur = con.cursor()
    # Cria tabelas essenciais para o funcionamento local/robô
    cur.execute('CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, email TEXT, prazo_dias INTEGER, valor_total REAL, cpm REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS promocoes (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, titulo TEXT, link TEXT, origem TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS carteira (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_email TEXT, data_compra TEXT, programa TEXT, quantidade INTEGER, custo_total REAL, cpm_medio REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS mercado_p2p (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, grupo_nome TEXT, programa TEXT, tipo TEXT, valor REAL, observacao TEXT)')
    # Tabela de fallback para login local caso supabase falhe
    cur.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, nome TEXT, senha_hash TEXT, data_cadastro TEXT)')
    con.commit()
    con.close()

def criar_hash(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def conectar_supabase():
    try:
        if SUPABASE_AVAILABLE:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
            return create_client(url, key)
    except:
        return None
    return None

def registrar_usuario(nome, email, senha, telefone):
    # Tenta Supabase
    sb = conectar_supabase()
    if sb:
        try:
            res = sb.table("usuarios").select("*").eq("email", email).execute()
            if len(res.data) > 0: return False, "E-mail já existe na nuvem."
            
            dados = {"email": email, "nome": nome, "senha_hash": criar_hash(senha), "telefone": telefone, "plano": "Free"}
            sb.table("usuarios").insert(dados).execute()
            return True, "Sucesso (Nuvem)!"
        except Exception as e:
            return False, f"Erro Nuvem: {str(e)}"
    
    # Fallback Local
    try:
        con = conectar_local()
        cur = con.cursor()
        cur.execute("INSERT INTO usuarios (email, nome, senha_hash) VALUES (?, ?, ?)", (email, nome, criar_hash(senha)))
        con.commit(); con.close()
        return True, "Sucesso (Local)!"
    except: return False, "Erro ao salvar local."

def autenticar_usuario(email, senha):
    senha_hash = criar_hash(senha)
    
    # 1. Tenta Supabase
    sb = conectar_supabase()
    if sb:
        try:
            res = sb.table("usuarios").select("*").eq("email", email).eq("senha_hash", senha_hash).execute()
            if len(res.data) > 0:
                user = res.data[0]
                return {"nome": user['nome'], "plano": user.get('plano', 'Free'), "email": email}
        except: pass
    
    # 2. Tenta Local
    con = conectar_local()
    cur = con.cursor()
    cur.execute("SELECT nome FROM usuarios WHERE email = ? AND senha_hash = ?", (email, senha_hash))
    res = cur.fetchone()
    con.close()
    if res: return {"nome": res[0], "plano": "Local", "email": email}
    
    return None

# Funções de Dados (Leitura)
def ler_dados_historico():
    con = conectar_local()
    try:
        df = pd.read_sql_query("SELECT * FROM historico ORDER BY data_hora ASC", con)
        if 'email' in df.columns: df = df.rename(columns={'email': 'programa'})
    except: df = pd.DataFrame()
    con.close()
    return df

def ler_carteira_usuario(email):
    con = conectar_local()
    try: df = pd.read_sql_query("SELECT * FROM carteira WHERE usuario_email = ?", con, params=(email,))
    except: df = pd.DataFrame()
    con.close()
    return df

def adicionar_carteira(email, p, q, v):
    con = conectar_local()
    cpm = v/(q/1000) if q > 0 else 0
    con.execute("INSERT INTO carteira (usuario_email, data_compra, programa, quantidade, custo_total, cpm_medio) VALUES (?, ?, ?, ?, ?, ?)", 
                (email, datetime.now().strftime("%Y-%m-%d"), p, q, v, cpm))
    con.commit(); con.close()

def remover_carteira(id_item):
    con = conectar_local()
    con.execute("DELETE FROM carteira WHERE id = ?", (id_item,)); con.commit(); con.close()

def adicionar_p2p(g, p, t, v, o):
    con = conectar_local()
    con.execute("INSERT INTO mercado_p2p (data_hora, grupo_nome, programa, tipo, valor, observacao) VALUES (?, ?, ?, ?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M"), g, p, t, v, o))
    con.commit(); con.close()

# --- INICIALIZAÇÃO ---
iniciar_banco()

# --- CSS E ESTILO ---
st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 5px;}
    .metric-card {background: #f0f2f6; padding: 15px; border-radius: 8px;}
</style>
""", unsafe_allow_html=True)

# --- GESTÃO DE SESSÃO ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

# ==============================================================================
# VIEW 1: LOGIN (COM KEYS CORRIGIDAS)
# ==============================================================================
def tela_login():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<h1 style='text-align: center;'>✈️ MilhasPro</h1>", unsafe_allow_html=True)
        
        # Admin Backdoor Check
        try:
            if st.query_params.get("admin") == "true":
                st.info("Modo Admin Detectado")
        except: pass

        tab1, tab2 = st.tabs(["ENTRAR", "CRIAR CONTA"])
        
        with tab1:
            email = st.text_input("E-mail", key="login_email")
            senha = st.text_input("Senha", type="password", key="login_pass")
            if st.button("Acessar Painel", key="btn_login", type="primary"):
                # Admin Secrets
                try:
                    if email == st.secrets["admin"]["email"] and senha == st.secrets["admin"]["senha"]:
                        st.session_state['user'] = {"nome": st.secrets["admin"]["nome"], "plano": "Admin", "email": email}
                        st.rerun()
                except: pass
                
                # Login Normal
                user = autenticar_usuario(email, senha)
                if user:
                    st.session_state['user'] = user
                    st.success("Login OK!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st
