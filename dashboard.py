import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import time
import re
import plotly.express as px
import feedparser
from datetime import datetime

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(
    page_title="MilhasPro | System",
    page_icon="✈️",
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

# --- 3. BANCO LOCAL (CACHE) ---
NOME_BANCO_LOCAL = "milhas.db"
def conectar_local(): return sqlite3.connect(NOME_BANCO_LOCAL)

def iniciar_banco_local():
    con = conectar_local()
    con.execute('CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, email TEXT, prazo_dias INTEGER, valor_total REAL, cpm REAL)')
    con.execute('CREATE TABLE IF NOT EXISTS promocoes (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, titulo TEXT, link TEXT, origem TEXT)')
    con.execute('CREATE TABLE IF NOT EXISTS carteira (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_email TEXT, data_compra TEXT, programa TEXT, quantidade INTEGER, custo_total REAL, cpm_medio REAL)')
    con.execute('CREATE TABLE IF NOT EXISTS mercado_p2p (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, grupo_nome TEXT, programa TEXT, tipo TEXT, valor REAL, observacao TEXT)')
    con.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, nome TEXT, senha_hash TEXT, data_cadastro TEXT)')
    con.commit(); con.close()

# --- 4. UTILITÁRIOS ---
def criar_hash(senha): return hashlib.sha256(senha.encode()).hexdigest()

def validar_senha_forte(senha):
    if len(senha) < 8: return False, "Mínimo 8 caracteres."
    return True, ""

def formatar_real(valor):
    if valor is None: return "R$ 0,00"
    try:
        s = f"{float(valor):,.2f}"
        s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"R$ {s}"
    except: return "R$ 0,00"

def criar_card_destaque(titulo, valor, subtitulo, cor="blue"):
    cores = {
        "blue": "border-left: 5px solid #0E436B; background-color: #F0F8FF;",
        "green": "border-left: 5px solid #28a745; background-color: #F0FFF4;",
        "red": "border-left: 5px solid #dc3545; background-color: #FFF5F5;",
        "orange": "border-left: 5px solid #ffc107; background-color: #FFFAEB;"
    }
    estilo = cores.get(cor, cores["blue"])
    
    return f"""
    <div style="{estilo} padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 10px;">
        <div style="font-size: 0.85rem; color: #666; font-weight: 600; text-transform: uppercase;">{titulo}</div>
        <div style="font-size: 1.6rem; font-weight: 800; color: #333; margin: 5px 0;">{valor}</div>
        <div style="font-size: 0.8rem; color: #888;">{subtitulo}</div>
    </div>
    """

# --- 5. FUNÇÕES DE DADOS ---
@st.cache_data(ttl=900) 
def buscar_promocoes_live():
    feeds = [
        {"url": "https://passageirodeprimeira.com/feed/", "fonte": "Passageiro de Primeira"},
        {"url": "https://pontospravoar.com/feed/", "fonte": "Pontos pra Voar"},
        {"url": "https://www.melhoresdestinos.com.br/feed", "fonte": "Melhores Destinos"}
    ]
    keywords = ["bônus", "transferência", "compra", "livelo", "esfera", "latam", "smiles", "azul", "tap", "iberia"]
    news = []
    for f in feeds:
        try:
            d = feedparser.parse(f['url'])
            for e in d.entries[:6]:
                if any(k in e.title.lower() for k in keywords):
                    data_pub = e.get('published', 'Hoje')[:16]
                    news.append({"Data": data_pub, "Título": e.title, "Fonte": f['fonte'], "Link": e.link})
        except: pass
    return pd.DataFrame(news)

def adicionar_p2p(g, p, t, v, o):
    sb = get_supabase()
    if not sb: return False, "Erro de conexão."
    try:
        dados = {"data_hora": datetime.now().strftime("%Y-%m-%d %H:%M"), "grupo_nome": g, "programa": p, "tipo": "COMPRA", "valor": float(v), "observacao": o}
        sb.table("mercado_p2p").insert(dados).execute()
        return True, "Sucesso"
    except Exception as e: return False, str(e)

def ler_p2p_todos():
    sb = get_supabase()
    if not sb: return pd.DataFrame()
    try:
        res = sb.table("mercado_p2p").select("*").order("id", desc=True).limit(50).execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

def pegar_ultimo_p2p(programa):
    sb = get_supabase()
    if not sb: return 0.0
    try:
        res = sb.table("mercado_p2p").select("valor").ilike("programa", f"%{programa}%").order("id", desc=True).limit(1).execute()
        if len(res.data) > 0: return float(res.data[0]['valor'])
    except: pass
    return 0.0

def adicionar_carteira(email, p, q, v):
    sb = get_supabase()
    if not sb: return False, "Erro conexão."
    try:
        cpm = float(v) / (float(q) / 1000) if float(q) > 0 else 0
        dados = {"usuario_email": email, "data_compra": datetime.now().strftime("%Y-%m-%d"), "programa": p, "quantidade": int(q), "custo_total": float(v), "cpm_medio": cpm}
        sb.table("carteira").insert(dados).execute()
        return True, "Sucesso"
    except Exception as e: return False, str(e)

def remover_carteira(id_item):
    sb = get_supabase()
    if sb: 
        try: sb.table("carteira").delete().eq("id", id_item).execute()
        except: pass

def ler_carteira_usuario(email):
    sb = get_supabase()
    if not sb: return pd.DataFrame()
    try:
        res = sb.table("carteira").select("*").eq("usuario_email", email).execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

def registrar_usuario(nome, email, senha, telefone):
    valida, msg = validar_senha_forte(senha)
    if not valida: return False, msg
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("usuarios").select("id").eq("email", email).execute()
            if len(res.data) > 0: return False, "E-mail já existe."
            dados = {"email": email, "nome": nome, "senha_hash": hashlib.sha256(senha.encode()).hexdigest(), "telefone": telefone, "plano": "Free", "status": "Ativo"}
            sb.table("usuarios").insert(dados).execute()
            return True, "Conta criada!"
        except Exception as e: return False, f"Erro: {e}"
    return False, "Erro conexão."

def autenticar_usuario(email, senha):
    sb = get_supabase()
    if not sb: return None
    try:
        h = hashlib.sha256(senha.encode()).hexdigest()
        res = sb.table("usuarios").select("*").eq("email", email).eq("senha_hash", h).execute()
        if len(res.data) > 0:
            u = res.data[0]
            return {"nome": u['nome'], "plano": u.get('plano', 'Free'), "email": email}
    except: pass
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

# --- INICIALIZAÇÃO ---
iniciar_banco_local()

# --- CSS ---
st.markdown("""
<style>
    .block-container {padding-top: 4rem !important; padding-bottom: 2rem !important;}
    div.stButton > button {width: 100%; background-color: #0E436B; color: white; border-radius: 5px; font-weight: bold;}
    div.stButton > button:hover {background-color: #082d4a; color: white;}
    div[data-testid="stImage"] {display: flex; justify-content: center; align-items: center; width: 100%;}
    a {text-decoration: none; color: #0E436B; font-weight: bold;}
    
    /* Pricing Card */
    .pricing-card { background: white; padding: 40px; border-radius: 15px; text-align: center; border: 1px solid #eee; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
    .popular-badge { background: #FFC107; color: #333; padding: 5px 20px; font-weight: bold; font-size: 0.8rem; display: inline-block; border-radius: 20px; margin-bottom: 10px; }
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
    # Menu reorganizado para focar na produção
    opcoes = ["Produção & Cálculo (Livelo/Esfera)", "Minha Carteira", "Mercado P2P (Venda)", "Promoções"]
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

    # --- CALCULADORA DE PRODUÇÃO ---
    if menu == "Produção & Cálculo (Livelo/Esfera)":
        st.header("🏭 Fábrica de Milhas")
        st.markdown("Calcule o custo real do seu milheiro baseado nos programas de fidelidade e compare com o preço de venda P2P.")
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("1. Compra de Pontos")
            programa = st.selectbox("Programa de Origem", ["Livelo", "Esfera", "IUPP"])
            preco_balcao = 70.00 # Preço padrão
            
            desconto = st.slider(f"Desconto {programa} (%)", 0, 60, 50, help="Quanto de desconto você consegue hoje?")
            custo_pts = preco_balcao * (1 - (desconto/100))
            
            st.metric(f"Custo {programa} (CPM)", f"R$ {custo_pts:.2f}")

        with c2:
            st.subheader("2. Transferência")
            destino = st.selectbox("Programa Aéreo", ["Latam Pass", "Smiles", "TudoAzul", "TAP", "Iberia"])
            bonus = st.number_input("Bônus de Transferência (%)", 0, 120, 100, step=10)
            
            fator = 1 + (bonus/100)
            cpm_final = custo_pts / fator
            
            # Lógica especial para Iberia/TAP que tem paridade diferente (ex: 2:1) se necessário
            # Mantendo 1:1 padrão para simplificar
            
            st.markdown(f"""
            <div style="background: #e3f2fd; padding: 15px; border-radius: 10px; text-align: center; border: 2px solid #0E436B;">
                <small>CUSTO FINAL GERADO</small><br>
                <strong style="font-size: 2rem; color: #0E436B;">{formatar_real(cpm_final)}</strong><br>
                <small>no programa {destino}</small>
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        
        # COMPARAÇÃO COM P2P
        st.subheader("3. Análise de Lucro (Sniper)")
        val_p2p = pegar_ultimo_p2p(destino.split()[0]) # Pega Latam de "Latam Pass"
        
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.markdown(criar_card_preco(f"Preço de Venda P2P ({destino})", val_p2p), unsafe_allow_html=True)
        
        with col_res2:
            if val_p2p > 0:
                lucro = val_p2p - cpm_final
                margem = (lucro / cpm_final) * 100
                cor_card = "green" if lucro > 0 else "red"
                st.markdown(criar_card_destaque("LUCRO / PREJUÍZO POR MILHEIRO", formatar_real(lucro), f"Margem: {margem:.1f}%", cor_card), unsafe_allow_html=True)
            else:
                st.info("Sem dados de venda P2P para comparação. Cadastre uma oferta no menu P2P.")

    # --- CARTEIRA ---
    elif menu == "Minha Carteira":
        st.header("💼 Carteira")
        if plano == "Free": mostrar_paywall()
        else:
            with st.expander("➕ Adicionar Lote", expanded=True):
                with st.form("add_carteira"):
                    c1, c2, c3 = st.columns(3)
                    p = c1.selectbox("Programa", ["Latam Pass", "Smiles", "Azul", "Livelo"])
                    q = c2.number_input("Qtd", 1000, step=1000)
                    cpm = c3.number_input("CPM Pago (R$)", 0.0, 70.0, 35.0, step=0.50) # AGORA PEDE O CPM
                    if st.form_submit_button("💾 Salvar Lote"):
                        total = (q/1000) * cpm
                        ok, msg = adicionar_carteira(user['email'], p, q, total)
                        if ok: st.success("Salvo!"); time.sleep(0.5); st.rerun()
                        else: st.error(f"Erro: {msg}")
            
            dfc = ler_carteira_usuario(user['email'])
            if not dfc.empty:
                patrimonio = 0; custo_total = 0; view_data = []
                for _, row in dfc.iterrows():
                    prog_nome = row['programa'].split()[0]
                    val_p2p = pegar_ultimo_p2p(prog_nome)
                    
                    qtd = float(row['quantidade'])
                    custo = float(row['custo_total'])
                    cpm_pago = float(row['cpm_medio'])
                    
                    # Valuation baseado SOMENTE no P2P (Mercado Real)
                    val_venda = (qtd / 1000) * val_p2p
                    lucro = val_venda - custo
                    
                    patrimonio += val_venda
                    custo_total += custo
                    
                    view_data.append({
                        "ID": row['id'], 
                        "Programa": row['programa'], 
                        "Qtd": f"{qtd:,.0f}".replace(',', '.'), 
                        "CPM Pago": formatar_real(cpm_pago), 
                        "Cotação P2P": formatar_real(val_p2p),
                        "Lucro (Hoje)": formatar_real(lucro)
                    })
                
                k1, k2, k3 = st.columns(3)
                k1.metric("Custo Total", formatar_real(custo_total))
                k2.metric("Valor de Venda (P2P)", formatar_real(patrimonio))
                delta_perc = ((patrimonio/custo_total)-1)*100 if custo_total > 0 else 0
                k3.metric("Resultado", formatar_real(patrimonio - custo_total), delta=f"{delta_perc:.1f}%")
                
                st.divider()
                def color_lucro(val):
                    if isinstance(val, str) and "-" in val: return 'color: #d9534f; font-weight: bold;'
                    return 'color: #28a745; font-weight: bold;'
                st.dataframe(pd.DataFrame(view_data).style.applymap(color_lucro, subset=['Lucro (Hoje)']), use_container_width=True)
                
                rid = st.number_input("ID para remover", step=1)
                if st.button("🗑️ Remover Lote"): remover_carteira(rid); st.rerun()
            else: st.info("Carteira vazia.")

    # --- P2P (COMPRA) ---
    elif menu == "Mercado P2P (Venda)":
        st.header("📢 Radar P2P (Oportunidades de Venda)")
        st.caption("Valores que estão pagando nos grupos de balcão.")
        
        if plano == "Admin":
            with st.form("p2p"):
                st.markdown("### 👑 Cadastrar Oportunidade")
                c1, c2 = st.columns(2)
                g = c1.text_input("Grupo/Comprador")
                p = c2.selectbox("Programa", ["Latam", "Smiles", "Azul", "Livelo", "Esfera"])
                val = st.number_input("Valor (R$)", 15.0)
                obs = st.text_input("Obs (Ex: Pagamento na hora, drop)")
                if st.form_submit_button("PUBLICAR"):
                    ok, msg = adicionar_p2p(g, p, "COMPRA", val, obs)
                    if ok: st.success("Salvo!"); time.sleep(0.5); st.rerun()
                    else: st.error(f"Erro: {msg}")
        else:
            if plano == "Free": mostrar_paywall(); st.stop()
        
        dfp = ler_p2p_todos()
        if not dfp.empty:
            dfp['valor'] = dfp['valor'].apply(formatar_real)
            st.dataframe(dfp[['data_hora', 'programa', 'valor', 'grupo_nome', 'observacao']], use_container_width=True)

    # --- PROMOÇÕES ---
    elif menu == "Promoções":
        st.header("🔥 Radar")
        if plano == "Free": mostrar_paywall()
        else:
            with st.spinner("Buscando promoções..."):
                df_news = buscar_promocoes_live()
                if not df_news.empty:
                    for _, row in df_news.iterrows():
                        with st.container():
                            st.markdown(f"##### 🔗 [{row['Título']}]({row['Link']})")
                            st.caption(f"📅 {row['Data']} | 📰 {row['Fonte']}")
                            st.divider()
                else: st.info("Nenhuma promoção encontrada.")

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
