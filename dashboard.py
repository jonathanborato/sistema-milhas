import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import time
from datetime import datetime

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(
    page_title="MilhasPro System",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CONFIGURAÇÃO SUPABASE (NUVEM) ---
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
    except:
        return None

# --- 3. BANCO DE DADOS LOCAL (CACHE/ROBÔ) ---
NOME_BANCO_LOCAL = "milhas.db"

def conectar_local():
    return sqlite3.connect(NOME_BANCO_LOCAL)

def iniciar_banco():
    con = conectar_local()
    cur = con.cursor()
    # Tabelas Locais
    cur.execute('CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, email TEXT, prazo_dias INTEGER, valor_total REAL, cpm REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS promocoes (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, titulo TEXT, link TEXT, origem TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS carteira (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_email TEXT, data_compra TEXT, programa TEXT, quantidade INTEGER, custo_total REAL, cpm_medio REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS mercado_p2p (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, grupo_nome TEXT, programa TEXT, tipo TEXT, valor REAL, observacao TEXT)')
    # Tabela Fallback
    cur.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, nome TEXT, senha_hash TEXT, data_cadastro TEXT)')
    con.commit()
    con.close()

def criar_hash(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# --- 4. FUNÇÕES DE USUÁRIO (NUVEM FIRST) ---
def registrar_usuario(nome, email, senha, telefone):
    # 1. Tenta Supabase
    sb = get_supabase()
    if sb:
        try:
            # Verifica se já existe
            res = sb.table("usuarios").select("*").eq("email", email).execute()
            if len(res.data) > 0: return False, "E-mail já cadastrado (Nuvem)."
            
            dados = {
                "email": email, "nome": nome, "senha_hash": criar_hash(senha), 
                "telefone": telefone, "plano": "Free", "status": "Ativo"
            }
            sb.table("usuarios").insert(dados).execute()
            return True, "Conta criada com sucesso na Nuvem!"
        except Exception as e:
            return False, f"Erro Nuvem: {e}"
            
    # 2. Fallback Local (Se Supabase falhar)
    try:
        con = conectar_local()
        con.execute("INSERT INTO usuarios (email, nome, senha_hash) VALUES (?, ?, ?)", (email, nome, criar_hash(senha)))
        con.commit(); con.close()
        return True, "Conta criada Localmente (Aviso: Temporária)"
    except: return False, "Erro ao criar conta."

def autenticar_usuario(email, senha):
    senha_hash = criar_hash(senha)
    
    # 1. Tenta Supabase
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("usuarios").select("*").eq("email", email).eq("senha_hash", senha_hash).execute()
            if len(res.data) > 0:
                user = res.data[0]
                return {"nome": user['nome'], "plano": user.get('plano', 'Free'), "email": email}
        except: pass
        
    # 2. Tenta Local
    con = conectar_local()
    res = con.execute("SELECT nome FROM usuarios WHERE email = ? AND senha_hash = ?", (email, senha_hash)).fetchone()
    con.close()
    if res: return {"nome": res[0], "plano": "Local", "email": email}
    
    return None

# --- 5. FUNÇÕES DE DADOS DO SISTEMA ---
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
    # Sintaxe segura
    sql = "INSERT INTO mercado_p2p (data_hora, grupo_nome, programa, tipo, valor, observacao) VALUES (?, ?, ?, ?, ?, ?)"
    dados = (datetime.now().strftime("%Y-%m-%d %H:%M"), g, p, t, v, o)
    con.execute(sql, dados)
    con.commit(); con.close()

# --- INICIALIZAÇÃO ---
iniciar_banco()

# --- CSS ---
st.markdown("""<style>.stButton>button {width: 100%;}</style>""", unsafe_allow_html=True)

# --- SESSÃO ---
if 'user' not in st.session_state: st.session_state['user'] = None

# ==============================================================================
# TELA DE LOGIN
# ==============================================================================
def tela_login():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<h1 style='text-align: center;'>✈️ MilhasPro</h1>", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["ENTRAR", "CRIAR CONTA"])
        
        with tab1:
            email = st.text_input("E-mail", key="log_email")
            senha = st.text_input("Senha", type="password", key="log_pass")
            if st.button("Acessar", type="primary", key="btn_log"):
                # Admin Secrets
                try:
                    if email == st.secrets["admin"]["email"] and senha == st.secrets["admin"]["senha"]:
                        st.session_state['user'] = {"nome": st.secrets["admin"]["nome"], "plano": "Admin", "email": email}
                        st.rerun()
                except: pass
                
                user = autenticar_usuario(email, senha)
                if user:
                    st.session_state['user'] = user
                    st.success(f"Bem-vindo, {user['nome']}!")
                    time.sleep(0.5)
                    st.rerun()
                else: st.error("Dados inválidos.")
        
        with tab2:
            st.info("Seus dados agora são salvos na Nuvem Segura (Supabase).")
            nome = st.text_input("Nome", key="cad_nome")
            c_email = st.text_input("E-mail", key="cad_email")
            whats = st.text_input("WhatsApp", key="cad_whats")
            c_pass = st.text_input("Senha", type="password", key="cad_pass")
            
            if st.button("Cadastrar Gratuitamente", key="btn_cad"):
                if len(c_pass) < 4: st.warning("Senha muito curta")
                else:
                    ok, msg = registrar_usuario(nome, c_email, c_pass, whats)
                    if ok: st.success(msg)
                    else: st.error(msg)

# ==============================================================================
# SISTEMA LOGADO
# ==============================================================================
def sistema_logado():
    user = st.session_state['user']
    
    with st.sidebar:
        st.title("✈️ Painel")
        st.write(f"Olá, **{user['nome']}**")
        
        if user['plano'] == "Admin": st.success("👑 ADMIN")
        elif user['plano'] == "Pro": st.success("⭐ PRO")
        else: st.info("🔹 FREE")
        
        st.divider()
        menu = st.radio("Navegação", ["Dashboard", "Carteira", "Mercado P2P", "Promoções"])
        st.divider()
        if st.button("Sair"): st.session_state['user'] = None; st.rerun()

    df_cotacoes = ler_dados_historico()

    if menu == "Dashboard":
        st.header("📊 Mercado (Hotmilhas)")
        if not df_cotacoes.empty:
            cols = st.columns(3)
            for i, p in enumerate(["Latam", "Smiles", "Azul"]):
                d = df_cotacoes[df_cotacoes['programa'].str.contains(p, case=False, na=False)]
                with cols[i]:
                    if not d.empty:
                        val = d.iloc[-1]['cpm']
                        st.metric(p, f"R$ {val:.2f}")
                        st.line_chart(d, x="data_hora", y="cpm")
                    else: st.metric(p, "--")
        else: st.warning("Aguardando robô.")

    elif menu == "Carteira":
        st.header("💼 Carteira")
        with st.expander("➕ Adicionar"):
            c1, c2, c3 = st.columns(3)
            p = c1.selectbox("Programa", ["Latam Pass", "Smiles", "Azul", "Livelo"])
            q = c2.number_input("Qtd", 1000, step=1000)
            v = c3.number_input("R$ Total", 0.0, step=10.0)
            if st.button("Salvar"): adicionar_carteira(user['email'], p, q, v); st.rerun()
        
        dfc = ler_carteira_usuario(user['email'])
        if not dfc.empty:
            st.dataframe(dfc)
            rid = st.number_input("ID Remover", step=1)
            if st.button("Remover"): remover_carteira(rid); st.rerun()
        else: st.info("Vazia.")

    elif menu == "Mercado P2P":
        st.header("📢 Radar Manual")
        with st.form("p2p"):
            c1, c2 = st.columns(2)
            g = c1.text_input("Grupo")
            p = c2.selectbox("Prog", ["Latam", "Smiles"])
            t = st.radio("Tipo", ["VENDA", "COMPRA"])
            val = st.number_input("Valor", 15.0)
            obs = st.text_input("Obs")
            if st.form_submit_button("Salvar"):
                adicionar_p2p(g, p, t, val, obs)
                st.success("Salvo!"); time.sleep(0.5); st.rerun()
        
        try:
            con = conectar_local()
            dfp = pd.read_sql_query("SELECT * FROM mercado_p2p ORDER BY id DESC", con)
            con.close()
            if not dfp.empty: st.dataframe(dfp)
        except: pass

    elif menu == "Promoções":
        st.header("🔥 Radar")
        try:
            con = conectar_local()
            dfp = pd.read_sql_query("SELECT * FROM promocoes ORDER BY id DESC LIMIT 15", con)
            con.close()
            for _, r in dfp.iterrows(): st.markdown(f"[{r['titulo']}]({r['link']})")
        except: st.write("Nada.")

# MAIN
if st.session_state['user']: sistema_logado()
else: tela_login()
