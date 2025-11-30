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
    # MUDANÇA 1: Ícone da aba do navegador
    page_icon="🚀",
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

# --- VALIDADOR DE SENHA FORTE ---
def validar_senha_forte(senha):
    if len(senha) < 8: return False, "Mínimo 8 caracteres."
    if not re.search(r"[a-z]", senha): return False, "Precisa de letra minúscula."
    if not re.search(r"[A-Z]", senha): return False, "Precisa de letra maiúscula."
    if not re.search(r"[0-9]", senha): return False, "Precisa de número."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", senha): return False, "Precisa de caractere especial (@, #, $, etc)."
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
if 'erro_login' not in st.session_state: st.session_state['erro_login'] = False

# ==============================================================================
# TELA DE LOGIN / CADASTRO
# ==============================================================================
def tela_login():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        # MUDANÇA 2: Imagem da tela de login (Foguete)
        try: st.image("https://cdn-icons-png.flaticon.com/512/1356/1356479.png", width=100)
        except: pass
        st.markdown("<h1 style='text-align: center;'>MilhasPro System</h1>", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["ENTRAR", "CRIAR CONTA"])
        
        with tab1:
            email = st.text_input("E-mail", key="log_email")
            senha = st.text_input("Senha", type="password", key="log_pass")
            
            if st.button("Acessar", type="primary", key="btn_log"):
                st.session_state['erro_login'] = False
                try:
                    if email == st.secrets["admin"]["email"] and senha == st.secrets["admin"]["senha"]:
                        st.session_state['user'] = {"nome": st.secrets["admin"]["nome"], "plano": "Admin", "email": email}
                        st.rerun()
                except: pass
                
                user = autenticar_usuario(email, senha)
                if user:
                    st.session_state['user'] = user
                    st.success(f"Olá, {user['nome']}!"); time.sleep(0.5); st.rerun()
                else:
                    st.error("E-mail ou senha incorretos.")
                    st.session_state['erro_login'] = True
            
            if st.session_state['erro_login']:
                st.markdown("---")
                with st.expander("Esqueci minha senha 🆘"):
                    st.text_input("Confirme seu e-mail", value=email)
                    if st.button("Solicitar Reset"):
                        st.info("📨 Solicitação registrada! Entre em contato com o suporte.")
        
        with tab2:
            st.info("Sua senha deve conter: Maiúscula, Minúscula, Número e Especial (@#$%).")
            nome = st.text_input("Nome", key="cad_nome")
            mail = st.text_input("E-mail", key="cad_mail")
            whats = st.text_input("WhatsApp", key="cad_whats")
            pw = st.text_input("Senha", type="password", key="cad_pw")
            
            if st.button("Cadastrar", key="btn_cad"):
                ok, msg = registrar_usuario(nome, mail, pw, whats)
                if ok: st.success(msg)
                else: st.error(msg)

# ==============================================================================
# SISTEMA LOGADO
# ==============================================================================
def sistema_logado():
    user = st.session_state['user']
    plano = user['plano']
    
    opcoes = ["Dashboard (Mercado)", "Minha Carteira", "Mercado P2P", "Promoções"]
    if plano == "Admin": opcoes.append("👑 Gestão de Usuários")

    with st.sidebar:
        # MUDANÇA 3: Imagem da barra lateral (Foguete)
        try: st.image("https://cdn-icons-png.flaticon.com/512/1356/1356479.png", width=80)
        except: pass
        st.write(f"Olá, **{user['nome']}**")
        if plano == "Admin": st.success("👑 ADMIN")
        elif plano == "Pro": st.success("⭐ PRO")
        else: st.info("🔹 FREE")
        
        st.divider()
        menu = st.radio("Menu", opcoes)
        st.divider()
        if st.button("Sair"): st.session_state['user'] = None; st.session_state['erro_login'] = False; st.rerun()

    df_cotacoes = ler_dados_historico()

    if menu == "Dashboard (Mercado)":
        st.header("📊 Cotações de Hoje")
        if not df_cotacoes.empty:
            cols = st.columns(3)
            for i, p in enumerate(["Latam", "Smiles", "Azul"]):
                d = df_cotacoes[df_cotacoes['programa'].str.contains(p, case=False, na=False)]
                with cols[i]:
                    if not d.empty:
                        st.metric(p, f"R$ {d.iloc[-1]['cpm']:.2f}")
                        st.line_chart(d, x="data_hora", y="cpm")
                    else: st.metric(p, "--")
        else: st.warning("Aguardando robô.")

    elif menu == "Minha Carteira":
        st.header("💼 Carteira")
        if plano == "Free": mostrar_paywall()
        else:
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
        st.header("📢 Radar P2P")
        if plano == "Free": mostrar_paywall()
        else:
            with st.form("p2p"):
                c1, c2 = st.columns(2)
                g = c1.text_input("Grupo")
                p = c2.selectbox("Prog", ["Latam", "Smiles"])
                t = st.radio("Tipo", ["VENDA", "COMPRA"])
                val = st.number_input("Valor", 15.0)
                obs = st.text_input("Obs")
                if st.form_submit_button("Salvar"): adicionar_p2p(g, p, t, val, obs); st.success("Salvo!"); time.sleep(0.5); st.rerun()
            try:
                con = conectar_local()
                dfp = pd.read_sql_query("SELECT * FROM mercado_p2p ORDER BY id DESC", con)
                con.close()
                if not dfp.empty: st.dataframe(dfp)
            except: pass

    elif menu == "Promoções":
        st.header("🔥 Radar")
        if plano == "Free": mostrar_paywall()
        else:
            try:
                con = conectar_local()
                dfp = pd.read_sql_query("SELECT * FROM promocoes ORDER BY id DESC LIMIT 15", con)
                con.close()
                for _, r in dfp.iterrows(): st.markdown(f"[{r['titulo']}]({r['link']})")
            except: st.write("Nada ainda.")

    elif menu == "👑 Gestão de Usuários":
        st.header("Gestão de Clientes")
        df_users = admin_listar_todos()
        if not df_users.empty:
            lista_emails = df_users['email'].tolist()
            user_selecionado = st.selectbox("Editar Cliente", lista_emails)
            dados_user = df_users[df_users['email'] == user_selecionado].iloc[0]
            st.divider()
            col_edit1, col_edit2 = st.columns(2)
            with col_edit1:
                with st.form("form_edit"):
                    n_nm = st.text_input("Nome", value=dados_user['nome'])
                    n_em = st.text_input("E-mail", value=dados_user['email'])
                    n_tl = st.text_input("Tel", value=str(dados_user['telefone']) if dados_user['telefone'] else "")
                    n_pl = st.selectbox("Plano", ["Free", "Pro", "Admin"], index=["Free", "Pro", "Admin"].index(dados_user.get('plano', 'Free')))
                    n_st = st.selectbox("Status", ["Ativo", "Bloqueado"], index=0)
                    if st.form_submit_button("💾 Salvar"):
                        if admin_atualizar_dados(int(dados_user['id']), n_nm, n_em, n_tl, n_pl, n_st):
                            st.success("Atualizado!"); time.sleep(1); st.rerun()
            with col_edit2:
                st.warning("Segurança")
                n_pw = st.text_input("Resetar Senha", placeholder="Nova senha...")
                if st.button("🔄 Confirmar Reset"):
                    if len(n_pw)>3:
                        if admin_resetar_senha(int(dados_user['id']), n_pw): st.success("Senha alterada!")
                    else: st.error("Senha curta.")
            st.divider()
            st.dataframe(df_users)

# MAIN
if st.session_state['user']: sistema_logado()
else: tela_login()
