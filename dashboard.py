import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import time
import re
import plotly.express as px
from datetime import datetime
import asyncio

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(
    page_title="MilhasPro System",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

LOGO_URL = "https://raw.githubusercontent.com/jonathanborato/sistema-milhas/main/logo.png"

# --- 2. CONFIGURAÇÃO DE AMBIENTE (PREVINE ERROS DE NOME) ---
try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

def get_supabase():
    if not SUPABASE_AVAILABLE:
        return None
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except:
        return None

# --- 3. BANCO LOCAL ---
NOME_BANCO_LOCAL = "milhas.db"
def conectar_local(): return sqlite3.connect(NOME_BANCO_LOCAL)

def iniciar_banco_local():
    con = conectar_local()
    cur = con.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, email TEXT, prazo_dias INTEGER, valor_total REAL, cpm REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS promocoes (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, titulo TEXT, link TEXT, origem TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS carteira (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_email TEXT, data_compra TEXT, programa TEXT, quantidade INTEGER, custo_total REAL, cpm_medio REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS mercado_p2p (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, grupo_nome TEXT, programa TEXT, tipo TEXT, valor REAL, observacao TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, nome TEXT, senha_hash TEXT, data_cadastro TEXT)')
    con.commit()
    con.close()

# --- UTILITÁRIOS ---
def criar_hash(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def validar_senha_forte(senha):
    if len(senha) < 8:
        return False, "Mínimo 8 caracteres."
    return True, ""

def formatar_real(valor):
    if valor is None:
        return "R$ 0,00"
    try:
        s = f"{float(valor):,.2f}"
        s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"R$ {s}"
    except:
        return "R$ 0,00"

def plotar_grafico(df, programa):
    cor = "#0E436B"
    if "Latam" in programa: cor = "#E30613"
    elif "Smiles" in programa: cor = "#FF7000"
    elif "Azul" in programa: cor = "#00AEEF"
    fig = px.area(df, x="data_hora", y="cpm", markers=True)
    fig.update_traces(line_color=cor, fillcolor=cor, marker=dict(size=6, color="white", line=dict(width=2, color=cor)))
    fig.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=0), xaxis_title=None, yaxis_title=None, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", yaxis=dict(showgrid=True, gridcolor='#f0f0f0'), xaxis=dict(showgrid=False), showlegend=False)
    return fig

def criar_card_preco(titulo, valor, is_winner=False):
    valor_fmt = formatar_real(valor) if valor > 0 else "--"
    css_class = "price-card winner-pulse" if is_winner and valor > 0 else "price-card"
    icon_html = '<span class="winner-icon">🏆</span>' if is_winner and valor > 0 else ""
    return f'<div class="{css_class}"><div class="card-title">{titulo} {icon_html}</div><div class="card-value">{valor_fmt}</div></div>'

# --- 4. FUNÇÕES DE DADOS ---
def adicionar_p2p(g, p, t, v, o):
    sb = get_supabase()
    if not sb:
        return False, "Erro de conexão."
    try:
        dados = {"data_hora": datetime.now().strftime("%Y-%m-%d %H:%M"), "grupo_nome": g, "programa": p, "tipo": "COMPRA", "valor": float(v), "observacao": o}
        sb.table("mercado_p2p").insert(dados).execute()
        return True, "Sucesso"
    except Exception as e:
        return False, str(e)

def ler_p2p_todos():
    sb = get_supabase()
    if not sb:
        return pd.DataFrame()
    try:
        res = sb.table("mercado_p2p").select("*").order("id", desc=True).limit(50).execute()
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

def pegar_ultimo_p2p(programa):
    sb = get_supabase()
    if not sb:
        return 0.0
    try:
        res = sb.table("mercado_p2p").select("valor").ilike("programa", f"%{programa}%").order("id", desc=True).limit(1).execute()
        if len(res.data) > 0:
            return float(res.data[0]['valor'])
    except:
        pass
    return 0.0

def adicionar_carteira(email, p, q, v):
    sb = get_supabase()
    if not sb:
        return False, "Erro conexão."
    try:
        cpm = float(v) / (float(q) / 1000) if float(q) > 0 else 0
        dados = {"usuario_email": email, "data_compra": datetime.now().strftime("%Y-%m-%d"), "programa": p, "quantidade": int(q), "custo_total": float(v), "cpm_medio": cpm}
        sb.table("carteira").insert(dados).execute()
        return True, "Sucesso"
    except Exception as e:
        return False, str(e)

def remover_carteira(id_item):
    sb = get_supabase()
    if sb: 
        try:
            sb.table("carteira").delete().eq("id", id_item).execute()
        except:
            pass

def ler_carteira_usuario(email):
    sb = get_supabase()
    if not sb:
        return pd.DataFrame()
    try:
        res = sb.table("carteira").select("*").eq("usuario_email", email).execute()
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def ler_dados_historico():
    con = conectar_local()
    try:
        df = pd.read_sql_query("SELECT * FROM historico ORDER BY data_hora ASC", con)
        if 'email' in df.columns:
            df = df.rename(columns={'email': 'programa'})
        if not df.empty:
            df['data_hora'] = pd.to_datetime(df['data_hora'], errors='coerce')
    except:
        df = pd.DataFrame()
    con.close()
    return df

# --- FUNÇÕES DE USUÁRIO ---
def registrar_usuario(nome, email, senha, telefone):
    sb = get_supabase()
    if not sb:
        return False, "Sem conexão."
    try:
        res = sb.table("usuarios").select("id").eq("email", email).execute()
        if len(res.data) > 0:
            return False, "E-mail já cadastrado."
        
        # Dados com senha hash
        dados = {
            "email": email,
            "nome": nome,
            "senha_hash": hashlib.sha256(senha.encode()).hexdigest(),
            "telefone": telefone,
            "plano": "Free",
            "status": "Ativo"
        }
        sb.table("usuarios").insert(dados).execute()
        return True, "Conta criada!"
    except Exception as e:
        return False, f"Erro: {e}"

def autenticar_usuario(email, senha):
    sb = get_supabase()
    if not sb:
        return None
    try:
        h = hashlib.sha256(senha.encode()).hexdigest()
        res = sb.table("usuarios").select("*").eq("email", email).eq("senha_hash", h).execute()
        if len(res.data) > 0:
            u = res.data[0]
            return {"nome": u['nome'], "plano": u.get('plano', 'Free'), "email": email}
    except:
        pass
    return None

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

# --- INICIALIZA ---
iniciar_banco_local()

# --- CSS ---
st.markdown("""
<style>
    .block-container {padding-top: 4rem !important; padding-bottom: 2rem !important;}
    div.stButton > button {width: 100%; background-color: #0E436B; color: white; border-radius: 5px; font-weight: bold;}
    div.stButton > button:hover {background-color: #082d4a; color: white;}
    div[data-testid="stImage"] {display: flex; justify-content: center; align-items: center; width: 100%;}
    
    @keyframes pulse-green { 0% { box-shadow: 0 0 0 0 rgba(37, 211, 102, 0.7); } 70% { box-shadow: 0 0 0 10px rgba(37, 211, 102, 0); } 100% { box-shadow: 0 0 0 0 rgba(37, 211, 102, 0); } }
    .price-card { background: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; text-align: center; margin-bottom: 10px; }
    .winner-pulse { border: 2px solid #25d366 !important; background: #f0fff4 !important; animation: pulse-green 2s infinite; color: #0E436B; }
    .card-title { font-size: 0.85rem; color: #6c757d; margin-bottom: 5px; }
    .card-value { font-size: 1.4rem; font-weight: 800; color: #212529; }
    .winner-icon { display: inline-block; margin-left: 5px; }
</style>
""", unsafe_allow_html=True)

def mostrar_paywall():
    st.error("🔒 RECURSO PRO")
    st.info("Faça o upgrade para acessar.")

# --- SESSÃO ---
if 'user' not in st.session_state: st.session_state['user'] = None

# --- ROBÔ (PLACEHOLDER SEGURO) ---
async def executar_cotacao_agora():
    # Esta função só deve ser chamada se PLAYWRIGHT_AVAILABLE for True
    if not PLAYWRIGHT_AVAILABLE:
        return False
    
    # ... (Código do robô iria aqui, mas para evitar erros de importação na nuvem sem dependências,
    # recomendamos usar o GitHub Actions para a coleta de dados) ...
    return False

# ==============================================================================
# TELA DE LOGIN
# ==============================================================================
def tela_login():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"""<div style="display: flex; flex-direction: column; align-items: center; margin-bottom: 20px;"><img src="{LOGO_URL}" style="width: 300px; max-width: 100%;"><h3 style='text-align: center; color: #0E436B; margin-top: -30px; margin-bottom: 0;'>Acesso ao Sistema</h3></div>""", unsafe_allow_html=True)
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
                    st.success("Login OK!"); time.sleep(0.5); st.rerun()
                else: st.error("Acesso negado.")
        with tab2:
            nome = st.text_input("Nome", key="cad_nome")
            email_c = st.text_input("E-mail", key="cad_mail")
            whats = st.text_input("WhatsApp", key="cad_whats")
            pw = st.text_input("Senha", type="password", key="cad_pw")
            if st.button("CADASTRAR", key="btn_cad"):
                ok, msg = registrar_usuario(nome, email_c, pw, whats)
                if ok: st.success(msg)
                else: st.error(msg)

# ==============================================================================
# SISTEMA LOGADO
# ==============================================================================
def sistema_logado():
    user = st.session_state['user']
    plano = user['plano']
    
    sb_status = "🟢 Online" if get_supabase() else "🔴 Offline"
    opcoes = ["Dashboard (Mercado)", "Minha Carteira", "Mercado P2P", "Promoções"]
    if plano == "Admin": opcoes.append("👑 Gestão de Usuários")

    with st.sidebar:
        st.markdown(f"""<div style="display: flex; justify-content: center; margin-bottom: 15px;"><img src="{LOGO_URL}" style="width: 200px; max-width: 100%;"></div>""", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align: center; margin-top: -10px;'>Olá, <b>{user['nome'].split()[0]}</b></div>", unsafe_allow_html=True)
        st.caption(f"Nuvem: {sb_status}")
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
        col_title, col_btn = st.columns([3, 1])
        with col_title:
            st.header("📊 Visão de Mercado")
        with col_btn:
            if st.button("🔄 Atualizar"):
                st.cache_data.clear()
                st.rerun()

        if not df_cotacoes.empty:
            cols = st.columns(3)
            for i, p in enumerate(["Latam", "Smiles", "Azul"]):
                d = df_cotacoes[df_cotacoes['programa'].str.contains(p, case=False, na=False)]
                val_hot = d.iloc[-1]['cpm'] if not d.empty else 0.0
                val_p2p = pegar_ultimo_p2p(p)
                
                hot_wins = val_hot > val_p2p and val_hot > 0
                p2p_wins = val_p2p > val_hot and val_p2p > 0
                
                with cols[i]:
                    st.markdown(f"### {p}")
                    mc1, mc2 = st.columns(2)
                    with mc1: st.markdown(criar_card_preco("🤖 Hotmilhas", val_hot, hot_wins), unsafe_allow_html=True)
                    with mc2: st.markdown(criar_card_preco("👥 P2P", val_p2p, p2p_wins), unsafe_allow_html=True)
                    st.divider()
                    if not d.empty: st.plotly_chart(plotar_grafico(d, p), use_container_width=True)
        else: st.warning("Aguardando robô (GitHub Actions).")

    # --- CARTEIRA ---
    elif menu == "Minha Carteira":
        df_cotacoes = ler_dados_historico()
        st.header("💼 Carteira")
        if plano == "Free": mostrar_paywall()
        else:
            with st.expander("➕ Adicionar Lote", expanded=True):
                with st.form("add_carteira"):
                    c1, c2, c3 = st.columns(3)
                    p = c1.selectbox("Programa", ["Latam Pass", "Smiles", "Azul", "Livelo"])
                    q = c2.number_input("Qtd", 1000, step=1000)
                    v = c3.number_input("R$ Total Pago", 0.0, step=10.0)
                    if st.form_submit_button("💾 Salvar Lote"):
                        ok, msg = adicionar_carteira(user['email'], p, q, v)
                        if ok: st.success("Salvo!"); time.sleep(0.5); st.rerun()
                        else: st.error(f"Erro: {msg}")
            
            dfc = ler_carteira_usuario(user['email'])
            if not dfc.empty:
                patrimonio = 0
                custo_total = 0
                view_data = []
                for _, row in dfc.iterrows():
                    prog_nome = row['programa'].split()[0]
                    val_hot = 0.0
                    if not df_cotacoes.empty:
                        f = df_cotacoes[df_cotacoes['programa'].str.contains(prog_nome, case=False, na=False)]
                        if not f.empty: val_hot = f.iloc[-1]['cpm']
                    val_p2p = pegar_ultimo_p2p(prog_nome)
                    melhor_preco = max(val_hot, val_p2p)
                    origem = "Hotmilhas" if val_hot >= val_p2p else "P2P"
                    if melhor_preco == 0: origem = "Sem Cotação"
                    
                    qtd = float(row['quantidade'])
                    custo = float(row['custo_total'])
                    cpm_pago = float(row['cpm_medio'])
                    val_venda = (qtd / 1000) * melhor_preco
                    lucro = val_venda - custo
                    patrimonio += val_venda
                    custo_total += custo
                    
                    view_data.append({"ID": row['id'], "Programa": row['programa'], "Qtd": f"{qtd:,.0f}".replace(',', '.'), "Custo": formatar_real(custo), "CPM Pago": formatar_real(cpm_pago), "Melhor Cotação": f"{formatar_real(melhor_preco)} ({origem})", "Lucro (Hoje)": formatar_real(lucro), "val_lucro_raw": lucro})
                
                k1, k2, k3 = st.columns(3)
                k1.metric("Total Investido", formatar_real(custo_total))
                k2.metric("Patrimônio Atual", formatar_real(patrimonio))
                delta_perc = ((patrimonio/custo_total)-1)*100 if custo_total > 0 else 0
                k3.metric("Lucro Projetado", formatar_real(patrimonio - custo_total), delta=f"{delta_perc:.1f}%")
                
                st.divider()
                st.dataframe(pd.DataFrame(view_data).style.applymap(lambda x: 'color: green' if x > 0 else 'color: red', subset=['val_lucro_raw']).drop(columns=['val_lucro_raw']), use_container_width=True)
                
                rid = st.number_input("ID para remover", step=1)
                if st.button("🗑️ Remover Lote"): remover_carteira(rid); st.rerun()
            else: st.info("Carteira vazia.")

    # --- P2P ---
    elif menu == "Mercado P2P":
        st.header("📢 Radar P2P")
        if plano == "Admin":
            with st.form("p2p"):
                st.markdown("### 👑 Inserir Oferta (Admin)")
                c1, c2 = st.columns(2)
                g = c1.text_input("Grupo")
                p = c2.selectbox("Prog", ["Latam", "Smiles", "Azul"])
                val = st.number_input("Valor", 15.0)
                obs = st.text_input("Obs")
                if st.form_submit_button("PUBLICAR"):
                    ok, msg = adicionar_p2p(g, p, "COMPRA", val, obs)
                    if ok: st.success("Salvo!"); time.sleep(0.5); st.rerun()
                    else: st.error(f"Erro: {msg}")
        else:
            if plano == "Free": mostrar_paywall(); st.stop()
            else: st.info("ℹ️ Dados verificados pela administração.")
        dfp = ler_p2p_todos()
        if not dfp.empty:
            dfp['valor'] = dfp['valor'].apply(formatar_real)
            st.dataframe(dfp, use_container_width=True)

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
            st.dataframe(df_users)

# MAIN
if st.session_state['user']: sistema_logado()
else: tela_login()
