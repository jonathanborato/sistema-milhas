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
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

LOGO_URL = "https://raw.githubusercontent.com/jonathanborato/sistema-milhas/main/logo.png"

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
    # Garante que as tabelas existam
    cur.execute('CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, email TEXT, prazo_dias INTEGER, valor_total REAL, cpm REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS promocoes (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, titulo TEXT, link TEXT, origem TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS carteira (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_email TEXT, data_compra TEXT, programa TEXT, quantidade INTEGER, custo_total REAL, cpm_medio REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS mercado_p2p (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, grupo_nome TEXT, programa TEXT, tipo TEXT, valor REAL, observacao TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, nome TEXT, senha_hash TEXT, data_cadastro TEXT)')
    con.commit(); con.close()

def criar_hash(senha): return hashlib.sha256(senha.encode()).hexdigest()

def validar_senha_forte(senha):
    if len(senha) < 8: return False, "Mínimo 8 caracteres."
    if not re.search(r"[a-z]", senha): return False, "Precisa de letra minúscula."
    if not re.search(r"[A-Z]", senha): return False, "Precisa de letra maiúscula."
    if not re.search(r"[0-9]", senha): return False, "Precisa de número."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", senha): return False, "Precisa de caractere especial (@#$)."
    return True, ""

# --- 4. FUNÇÕES DE USUÁRIO (NUVEM) ---
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
        except Exception as e: return False, f"Erro Nuvem: {e}"
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

# --- FUNÇÕES ADMIN ---
def admin_listar_todos():
    sb = get_supabase()
    if sb:
        res = sb.table("usuarios").select("*").order("id", desc=True).execute()
        return pd.DataFrame(res.data)
    return pd.DataFrame()

def admin_atualizar_dados(id_user, nome, email, telefone, plano, status):
    sb = get_supabase()
    if sb:
        sb.table("usuarios").update({"nome": nome, "email": email, "telefone": telefone, "plano": plano, "status": status}).eq("id", id_user).execute()
        return True
    return False

def admin_resetar_senha(id_user, nova_senha_texto):
    sb = get_supabase()
    if sb:
        sb.table("usuarios").update({"senha_hash": criar_hash(nova_senha_texto)}).eq("id", id_user).execute()
        return True
    return False

# --- 5. FUNÇÕES DE DADOS (COM CACHE INTELIGENTE) ---

# TTL=60 significa: "Lembre dos dados por 60 seg, depois releia do arquivo"
@st.cache_data(ttl=60)
def ler_dados_historico():
    con = conectar_local()
    try:
        # Pega tudo da tabela historico
        df = pd.read_sql_query("SELECT * FROM historico ORDER BY data_hora ASC", con)
        
        # Renomeia a coluna legada 'email' para 'programa' se existir
        if 'email' in df.columns: 
            df = df.rename(columns={'email': 'programa'})
            
        # Converte a coluna de data para datetime (ESSENCIAL PARA O GRÁFICO)
        if not df.empty and 'data_hora' in df.columns:
             df['data_hora'] = pd.to_datetime(df['data_hora'], errors='coerce')
             
    except Exception as e: 
        # Se der erro, imprime no terminal do servidor mas não quebra o site
        print(f"Erro ao ler histórico: {e}")
        df = pd.DataFrame()
        
    con.close()
    return df

def ler_carteira_usuario(email):
    sb = get_supabase()
    if sb:
        res = sb.table("carteira").select("*").eq("usuario_email", email).execute()
        return pd.DataFrame(res.data)
    return pd.DataFrame()

def adicionar_carteira(email, p, q, v):
    sb = get_supabase()
    if sb:
        cpm = v/(q/1000) if q>0 else 0
        dados = {"usuario_email": email, "data_compra": datetime.now().strftime("%Y-%m-%d"), "programa": p, "quantidade": q, "custo_total": v, "cpm_medio": cpm}
        sb.table("carteira").insert(dados).execute()

def remover_carteira(id_item):
    sb = get_supabase()
    if sb: sb.table("carteira").delete().eq("id", id_item).execute()

def adicionar_p2p(g, p, t, v, o):
    sb = get_supabase()
    if sb:
        dados = {"data_hora": datetime.now().strftime("%Y-%m-%d %H:%M"), "grupo_nome": g, "programa": p, "tipo": t, "valor": v, "observacao": o}
        sb.table("mercado_p2p").insert(dados).execute()

def pegar_ultimo_p2p(programa):
    sb = get_supabase()
    if sb:
        res = sb.table("mercado_p2p").select("valor").ilike("programa", f"%{programa}%").eq("tipo", "COMPRA").order("valor", desc=True).limit(1).execute()
        if len(res.data) > 0: return float(res.data[0]['valor'])
    return 0.0

def ler_p2p_todos():
    sb = get_supabase()
    if sb:
        res = sb.table("mercado_p2p").select("*").order("id", desc=True).limit(50).execute()
        return pd.DataFrame(res.data)
    return pd.DataFrame()

# --- INICIALIZA ---
iniciar_banco()

# --- ESTILIZAÇÃO CSS ---
st.markdown("""
<style>
    .block-container {padding-top: 1rem !important; padding-bottom: 2rem !important;}
    div.stButton > button {width: 100%; background-color: #0E436B; color: white; border: none; padding: 10px; border-radius: 5px; font-weight: bold;}
    div.stButton > button:hover {background-color: #082d4a; color: white;}
    div[data-testid="stImage"] {display: flex; justify-content: center; align-items: center; width: 100%;}
    .metric-card {background: #f0f2f6; padding: 15px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);}
</style>
""", unsafe_allow_html=True)

def mostrar_paywall():
    st.error("🔒 RECURSO PRO")
    st.info("Faça o upgrade para acessar.")

# --- SESSÃO ---
if 'user' not in st.session_state: st.session_state['user'] = None

# ==============================================================================
# TELA DE LOGIN
# ==============================================================================
def tela_login():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"""<div style="display: flex; flex-direction: column; align-items: center; margin-bottom: 20px;"><img src="{LOGO_URL}" style="width: 300px; max-width: 100%;"><h3 style='text-align: center; color: #0E436B; margin-top: -25px; margin-bottom: 0;'>Acesso ao Sistema</h3></div>""", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["ENTRAR", "CRIAR CONTA"])
        with tab1:
            email = st.text_input("E-mail", key="log_email")
            senha = st.text_input("Senha", type="password", key="log_pass")
            if st.button("ACESSAR SISTEMA", type="primary", key="btn_log"):
                try:
                    if email == st.secrets["admin"]["email"] and senha == st.secrets["admin"]["senha"]:
                        st.session_state['user'] = {"nome": st.secrets["admin"]["nome"], "plano": "Admin", "email": email}
                        st.rerun()
                except: pass
                user = autenticar_usuario(email, senha)
                if user:
                    st.session_state['user'] = user
                    st.success(f"Olá, {user['nome']}!"); time.sleep(0.5); st.rerun()
                else: st.error("Acesso negado.")
        with tab2:
            st.info("Requisitos: Mínimo 8 caracteres, Maiúscula, Minúscula, Número e Especial.")
            nome = st.text_input("Nome", key="cad_nome")
            mail = st.text_input("E-mail", key="cad_mail")
            whats = st.text_input("WhatsApp", key="cad_whats")
            pw = st.text_input("Senha", type="password", key="cad_pw")
            if st.button("CADASTRAR", key="btn_cad"):
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
        st.markdown(f"""<div style="display: flex; justify-content: center; margin-bottom: 15px;"><img src="{LOGO_URL}" style="width: 200px; max-width: 100%;"></div>""", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align: center; margin-top: -10px;'>Olá, <b>{user['nome'].split()[0]}</b></div>", unsafe_allow_html=True)
        if plano == "Admin": st.success("👑 ADMIN")
        elif plano == "Pro": st.success("⭐ PRO")
        else: st.info("🔹 FREE")
        st.divider()
        menu = st.radio("Menu", opcoes)
        st.divider()
        if st.button("SAIR"): st.session_state['user'] = None; st.rerun()

    df_cotacoes = ler_dados_historico()

    # --- DASHBOARD ---
    if menu == "Dashboard (Mercado)":
        st.header("📊 Visão de Mercado")
        if not df_cotacoes.empty:
            cols = st.columns(3)
            for i, p in enumerate(["Latam", "Smiles", "Azul"]):
                d = df_cotacoes[df_cotacoes['programa'].str.contains(p, case=False, na=False)]
                val_hot = 0.0
                if not d.empty: val_hot = d.iloc[-1]['cpm']
                valor_p2p = pegar_ultimo_p2p(p)
                
                with cols[i]:
                    st.markdown(f"### {p}")
                    mc1, mc2 = st.columns(2)
                    with mc1: st.metric("🤖 Hotmilhas", f"R$ {val_hot:.2f}" if val_hot > 0 else "--")
                    with mc2:
                        delta = 0.0
                        if val_hot > 0 and valor_p2p > 0: delta = valor_p2p - val_hot
                        st.metric("👥 P2P", f"R$ {valor_p2p:.2f}" if valor_p2p > 0 else "--", delta=f"{delta:.2f}" if valor_p2p > 0 else None)
                    st.divider()
                    if not d.empty: st.line_chart(d, x="data_hora", y="cpm", height=200)
            
            # --- ÁREA DE DIAGNÓSTICO (SÓ PARA VOCÊ VER SE TEM DADOS) ---
            with st.expander("🛠️ Dados Brutos (Diagnóstico)"):
                st.write("Se a tabela abaixo estiver vazia, o robô ainda não salvou dados.")
                st.dataframe(df_cotacoes)
                
        else:
            st.warning("⚠️ O banco de dados local está vazio.")
            st.info("Motivo Provável: O Streamlit ainda não baixou a atualização do Robô do GitHub.")
            st.markdown("""
            **Solução:**
            1. Vá no painel do Streamlit Cloud.
            2. Clique nos 3 pontinhos do App.
            3. Clique em **'Reboot'**.
            """)

    # --- CARTEIRA ---
    elif menu == "Minha Carteira":
        st.header("💼 Carteira")
        if plano == "Free": mostrar_paywall()
        else:
            with st.expander("➕ Adicionar"):
                c1, c2, c3 = st.columns(3)
                p = c1.selectbox("Programa", ["Latam Pass", "Smiles", "Azul", "Livelo"])
                q = c2.number_input("Qtd", 1000, step=1000)
                v = c3.number_input("R$ Total", 0.0, step=10.0)
                if st.button("SALVAR"): adicionar_carteira(user['email'], p, q, v); st.rerun()
            dfc = ler_carteira_usuario(user['email'])
            if not dfc.empty:
                st.dataframe(dfc)
                rid = st.number_input("ID Remover", step=1)
                if st.button("REMOVER"): remover_carteira(rid); st.rerun()
            else: st.info("Vazia.")

    # --- P2P ---
    elif menu == "Mercado P2P":
        st.header("📢 Radar P2P")
        if plano == "Admin":
            with st.form("p2p"):
                st.markdown("### 👑 Inserir Oferta (Admin)")
                c1, c2 = st.columns(2)
                g = c1.text_input("Grupo")
                p = c2.selectbox("Prog", ["Latam", "Smiles", "Azul"])
                t = st.radio("Tipo", ["VENDA", "COMPRA"])
                val = st.number_input("Valor", 15.0)
                obs = st.text_input("Obs")
                if st.form_submit_button("PUBLICAR"):
                    adicionar_p2p(g, p, "COMPRA" if "COMPRA" in t else "VENDA", val, obs); st.success("Salvo!"); time.sleep(0.5); st.rerun()
        else:
            if plano == "Free": mostrar_paywall(); st.stop()
            else: st.info("ℹ️ Dados verificados pela administração.")
        dfp = ler_p2p_todos()
        if not dfp.empty: st.dataframe(dfp, use_container_width=True)

    # --- PROMOÇÕES ---
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

    # --- ADMIN CRM ---
    elif menu == "👑 Gestão de Usuários":
        st.header("Admin CRM")
        df_users = admin_listar_todos()
        if not df_users.empty:
            sel = st.selectbox("Editar", df_users['email'].tolist())
            u_dados = df_users[df_users['email'] == sel].iloc[0]
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                with st.form("edit"):
                    n = st.text_input("Nome", u_dados['nome'])
                    p = st.selectbox("Plano", ["Free", "Pro", "Admin"], index=["Free", "Pro", "Admin"].index(u_dados.get('plano', 'Free')))
                    s = st.selectbox("Status", ["Ativo", "Bloqueado"], index=0)
                    if st.form_submit_button("SALVAR"):
                        if admin_atualizar_dados(int(u_dados['id']), n, u_dados['email'], u_dados['telefone'], p, s):
                            st.success("OK"); time.sleep(1); st.rerun()
            with c2:
                npw = st.text_input("Nova Senha")
                if st.button("RESETAR SENHA") and len(npw)>3:
                    admin_resetar_senha(int(u_dados['id']), npw); st.success("Senha alterada")
            st.dataframe(df_users)

# MAIN
if st.session_state['user']: sistema_logado()
else: tela_login()
