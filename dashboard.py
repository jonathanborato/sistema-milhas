import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import time
import re
from datetime import datetime

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(
    page_title="MilhasPro System",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CONFIGURAÇÃO SUPABASE ---
try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

def get_supabase():
    if not SUPABASE_AVAILABLE: return None
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except: return None

# --- 3. BANCO LOCAL ---
NOME_BANCO_LOCAL = "milhas.db"

def conectar_local(): return sqlite3.connect(NOME_BANCO_LOCAL)

def iniciar_banco():
    con = conectar_local()
    cur = con.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, email TEXT, prazo_dias INTEGER, valor_total REAL, cpm REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS promocoes (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, titulo TEXT, link TEXT, origem TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS carteira (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_email TEXT, data_compra TEXT, programa TEXT, quantidade INTEGER, custo_total REAL, cpm_medio REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS mercado_p2p (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, grupo_nome TEXT, programa TEXT, tipo TEXT, valor REAL, observacao TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, nome TEXT, senha_hash TEXT, data_cadastro TEXT)')
    con.commit(); con.close()

def criar_hash(senha): return hashlib.sha256(senha.encode()).hexdigest()

# --- VALIDADOR DE SENHA ---
def validar_senha_forte(senha):
    if len(senha) < 8: return False, "A senha deve ter no mínimo 8 caracteres."
    if not re.search(r"[a-z]", senha): return False, "A senha precisa ter letras minúsculas."
    if not re.search(r"[A-Z]", senha): return False, "A senha precisa ter letras maiúsculas."
    if not re.search(r"[0-9]", senha): return False, "A senha precisa ter números."
    return True, ""

# --- 4. FUNÇÕES DE USUÁRIO & ADMIN ---
def registrar_usuario(nome, email, senha, telefone):
    valida, msg = validar_senha_forte(senha)
    if not valida: return False, msg

    sb = get_supabase()
    if sb:
        try:
            res = sb.table("usuarios").select("*").eq("email", email).execute()
            if len(res.data) > 0: return False, "E-mail já existe."
            dados = {"email": email, "nome": nome, "senha_hash": criar_hash(senha), "telefone": telefone, "plano": "Free", "status": "Ativo"}
            sb.table("usuarios").insert(dados).execute()
            return True, "Conta criada! Faça login."
        except Exception as e: return False, f"Erro: {e}"
    
    try:
        con = conectar_local()
        con.execute("INSERT INTO usuarios (email, nome, senha_hash) VALUES (?, ?, ?)", (email, nome, criar_hash(senha)))
        con.commit(); con.close()
        return True, "Criado Localmente"
    except: return False, "Erro local."

def autenticar_usuario(email, senha):
    h = criar_hash(senha)
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("usuarios").select("*").eq("email", email).eq("senha_hash", h).execute()
            if len(res.data) > 0:
                u = res.data[0]
                return {"nome": u['nome'], "plano": u.get('plano', 'Free'), "email": email}
        except: pass
    
    con = conectar_local()
    res = con.execute("SELECT nome FROM usuarios WHERE email = ? AND senha_hash = ?", (email, h)).fetchone()
    con.close()
    if res: return {"nome": res[0], "plano": "Local", "email": email}
    return None

def admin_listar_todos():
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("usuarios").select("*").order("id", desc=True).execute()
            return pd.DataFrame(res.data)
        except: pass
    return pd.DataFrame()

def admin_atualizar_dados(id_user, nome, email, telefone, plano, status):
    sb = get_supabase()
    if sb:
        try:
            dados = {"nome": nome, "email": email, "telefone": telefone, "plano": plano, "status": status}
            sb.table("usuarios").update(dados).eq("id", id_user).execute()
            return True
        except: return False
    return False

def admin_resetar_senha(id_user, nova_senha_texto):
    sb = get_supabase()
    if sb:
        try:
            novo_hash = criar_hash(nova_senha_texto)
            sb.table("usuarios").update({"senha_hash": novo_hash}).eq("id", id_user).execute()
            return True
        except: return False
    return False

# --- 5. FUNÇÕES DE DADOS ---
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
    cpm = v/(q/1000) if q>0 else 0
    con.execute("INSERT INTO carteira (usuario_email, data_compra, programa, quantidade, custo_total, cpm_medio) VALUES (?, ?, ?, ?, ?, ?)", (email, datetime.now().strftime("%Y-%m-%d"), p, q, v, cpm))
    con.commit(); con.close()

def remover_carteira(id_item):
    con = conectar_local()
    con.execute("DELETE FROM carteira WHERE id = ?", (id_item,)); con.commit(); con.close()

def adicionar_p2p(g, p, t, v, o):
    con = conectar_local()
    sql = "INSERT INTO mercado_p2p (data_hora, grupo_nome, programa, tipo, valor, observacao) VALUES (?, ?, ?, ?, ?, ?)"
    con.execute(sql, (datetime.now().strftime("%Y-%m-%d %H:%M"), g, p, t, v, o))
    con.commit(); con.close()

# --- INICIALIZA ---
iniciar_banco()

st.markdown("""<style>.stButton>button {width: 100%;} .metric-card {background: #f0f2f6; padding: 15px; border-radius: 8px;}</style>""", unsafe_allow_html=True)

def mostrar_paywall():
    st.error("🔒 RECURSO PRO")
    st.info("Faça o upgrade para acessar esta ferramenta.")

# --- SESSÃO ---
if 'user' not in st.session_state: st.session_state['user'] = None

# ==============================================================================
# TELA DE LOGIN / CADASTRO
