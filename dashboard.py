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
    page_title="MilhasPro | P2P Edition",
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

# --- 3. BANCO LOCAL (APENAS PARA CACHE DE NOTÍCIAS RSS) ---
# Removemos o histórico de cotações local, pois agora tudo vem da nuvem P2P
NOME_BANCO_LOCAL = "milhas_cache.db"
def conectar_local(): return sqlite3.connect(NOME_BANCO_LOCAL)

def iniciar_banco_local():
    # Mantemos apenas tabelas auxiliares locais se necessário
    pass 

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
    }
    estilo = cores.get(cor, cores["blue"])
    return f"""
    <div style="{estilo} padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 10px;">
        <div style="font-size: 0.85rem; color: #666; font-weight: 600; text-transform: uppercase;">{titulo}</div>
        <div style="font-size: 1.6rem; font-weight: 800; color: #333; margin: 5px 0;">{valor}</div>
        <div style="font-size: 0.8rem; color: #888;">{subtitulo}</div>
    </div>
    """

# --- 5. FUNÇÕES DE DADOS (SUPABASE CENTRAL) ---

# A) LEITURA DE PREÇO P2P (O NOVO CORAÇÃO DO SISTEMA)
def pegar_preco_p2p_atual(programa):
    """Busca o preço mais recente de COMPRA registrado no P2P"""
    sb = get_supabase()
    if not sb: return 0.0
    try:
        # Pega o ultimo registro
        res = sb.table("mercado_p2p").select("valor").ilike("programa", f"%{programa}%").order("id", desc=True).limit(1).execute()
        if len(res.data) > 0: return float(res.data[0]['valor'])
    except: pass
    
    # Fallback se não tiver dados (Preço base conservador)
    defaults = {"Latam": 27.00, "Smiles": 17.50, "Azul": 21.00, "Livelo": 35.00, "Esfera": 35.00}
    return defaults.get(programa.split()[0], 0.0)

def ler_historico_p2p(programa):
    """Busca histórico de preços P2P para gráfico"""
    sb = get_supabase()
    if not sb: return pd.DataFrame()
    try:
        res = sb.table("mercado_p2p").select("data_hora, valor").ilike("programa", f"%{programa}%").order("data_hora", desc=False).execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            # Converte string de data para datetime para ordenar corretamente no gráfico
            df['data_hora'] = pd.to_datetime(df['data_hora'], format="%Y-%m-%d %H:%M", errors='coerce')
        return df
    except: return pd.DataFrame()

# B) CRUD P2P
def adicionar_p2p(g, p, v, o):
    sb = get_supabase()
    if not sb: return False, "Erro conexão"
    try:
        dados = {
            "data_hora": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "grupo_nome": g, "programa": p, "tipo": "COMPRA", # Assumimos que é oferta de compra do mercado
            "valor": float(v), "observacao": o
        }
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

# C) CARTEIRA
def adicionar_carteira(email, p, q, v):
    sb = get_supabase()
    if not sb: return False, "Erro conexão"
    try:
        cpm = float(v)/(float(q)/1000) if float(q)>0 else 0
        dados = {"usuario_email": email, "data_compra": datetime.now().strftime("%Y-%m-%d"), "programa": p, "quantidade": int(q), "custo_total": float(v), "cpm_medio": cpm}
        sb.table("carteira").insert(dados).execute()
        return True, "Sucesso"
    except Exception as e: return False, str(e)

def remover_carteira(id_item):
    sb = get_supabase()
    if sb: sb.table("carteira").delete().eq("id", id_item).execute()

def ler_carteira_usuario(email):
    sb = get_supabase()
    if not sb: return pd.DataFrame()
    try:
        res = sb.table("carteira").select("*").eq("usuario_email", email).execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

# D) NOTÍCIAS
@st.cache_data(ttl=900) 
def buscar_promocoes_live():
    feeds = [
        {"url": "https://passageirodeprimeira.com/feed/", "fonte": "Passageiro de Primeira"},
        {"url": "https://pontospravoar.com/feed/", "fonte": "Pontos pra Voar"},
        {"url": "https://www.melhoresdestinos.com.br/feed", "fonte": "Melhores Destinos"}
    ]
    keywords = ["bônus", "transferência", "compra", "livelo", "esfera", "latam", "smiles", "azul"]
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

# E) USUÁRIOS
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
    if sb: return pd.DataFrame(sb.table("usuarios").select("*").order("id", desc=True).execute().data)
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
    
    /* Cards */
    .lp-card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); text-align: center; height: 100%; border: 1px solid #EEF2F6; }
    .pricing-card { background: white; padding: 40px; border-radius: 15px; text-align: center; border: 1px solid #eee; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
    .popular-badge { background: #FFC107; color: #333; padding: 5px 20px; font-weight: bold; font-size: 0.8rem; position: absolute; top: 20px; right: -30px; transform: rotate(45deg); width: 120px; }
</style>
""", unsafe_allow_html=True)

def mostrar_paywall():
    st.error("🔒 RECURSO PRO")
    st.info("Faça o upgrade para acessar.")

if 'user' not in st.session_state: st.session_state['user'] = None

# ==============================================================================
# TELA LOGIN
# ==============================================================================
def tela_login():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"""<div style="display: flex; flex-direction: column; align-items: center; margin-bottom: 20px;"><img src="{LOGO_URL}" style="width: 300px; max-width: 100%;"><h3 style='text-align: center; color: #0E436B; margin-top: -30px; margin-bottom: 0;'>Acesso ao Sistema</h3></div>""", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["ENTRAR", "CRIAR CONTA"])
        with tab1:
            email = st.text_input("E-mail", key="log_e")
            senha = st.text_input("Senha", type="password", key="log_p")
            if st.button("ENTRAR", type="primary", key="btn_l"):
                try:
                    if email == st.secrets["admin"]["email"] and senha == st.secrets["admin"]["senha"]:
                        st.session_state['user'] = {"nome": st.secrets["admin"]["nome"], "plano": "Admin", "email": email}; st.rerun()
                except: pass
                u = autenticar_usuario(email, senha)
                if u: st.session_state['user'] = u; st.rerun()
                else: st.error("Erro no login.")
        with tab2:
            n = st.text_input("Nome", key="c_n"); e = st.text_input("Email", key="c_e"); w = st.text_input("Zap", key="c_w"); p = st.text_input("Senha", type="password", key="c_p")
            if st.button("CADASTRAR", key="btn_c"):
                ok, msg = registrar_usuario(n, e, p, w)
                if ok: st.success("Criado!"); st.balloons()
                else: st.error(msg)
    
    # Landing Page Elements
    st.markdown("---")
    c_p1, c_p2, c_p3 = st.columns([1, 2, 1])
    with c_p2:
        st.markdown("""
        <div class="pricing-card">
            <div class="popular-badge">POPULAR</div>
            <h3 style="color: #0E436B;">ASSINATURA PRO</h3>
            <h1 style="font-size: 3.5rem; margin: 0; color: #222;">R$ 49,90<span style="font-size: 1rem; color: #888;">/mês</span></h1>
            <hr style="margin: 20px 0;">
            <div style="text-align: left; color: #555;">
                <p>✅ Cotações P2P em Tempo Real</p><p>✅ Gestão de Carteira</p><p>✅ Calculadora de Emissão</p>
            </div>
        </div>""", unsafe_allow_html=True)

# ==============================================================================
# SISTEMA LOGADO
# ==============================================================================
def sistema_logado():
    user = st.session_state['user']
    plano = user['plano']
    
    opcoes = ["Mercado P2P (Cotações)", "Produção & Cálculo", "Minha Carteira", "Promoções"]
    if plano == "Admin": opcoes.append("👑 Gestão de Usuários")

    with st.sidebar:
        st.image(LOGO_URL, width=180)
        st.markdown(f"<div style='text-align: center; margin-top: 10px;'>Olá, <b>{user['nome'].split()[0]}</b></div>", unsafe_allow_html=True)
        if plano == "Admin": st.success("👑 ADMIN")
        elif plano == "Pro": st.success("⭐ PRO")
        else: st.info("🔹 FREE")
        st.divider(); menu = st.radio("Menu", opcoes); st.divider()
        if st.button("SAIR"): st.session_state['user'] = None; st.rerun()

    # --- 1. VISÃO DE MERCADO (BASEADA 100% NO P2P) ---
    if menu == "Mercado P2P (Cotações)":
        st.header("📊 Cotações de Balcão (P2P)")
        st.caption("Preços praticados nos principais grupos de Telegram (Venda Particular).")
        
        # Área do Admin postar
        if plano == "Admin":
            with st.expander("👑 Publicar Nova Cotação"):
                with st.form("p2p_add"):
                    c1, c2 = st.columns(2)
                    g = c1.text_input("Fonte (Ex: Balcão Milhas)")
                    p = c2.selectbox("Programa", ["Latam", "Smiles", "Azul", "Livelo", "Esfera", "TAP", "Iberia"])
                    v = st.number_input("Valor do Milheiro (R$)", 10.0, 100.0, step=0.1)
                    o = st.text_input("Obs (Ex: Pagamento PIX)")
                    if st.form_submit_button("Publicar"):
                        if adicionar_p2p(g, p, v, o): st.success("Publicado!"); time.sleep(0.5); st.rerun()
                        else: st.error("Erro")

        # Dashboard de Preços
        st.markdown("### 📈 Cotações Atuais")
        cols = st.columns(3)
        programas = ["Latam", "Smiles", "Azul"]
        
        for i, p in enumerate(programas):
            preco_atual = pegar_preco_p2p_atual(p)
            
            # Gráfico
            df_hist = ler_historico_p2p(p)
            
            with cols[i]:
                st.markdown(criar_card_destaque(f"{p}", formatar_real(preco_atual), "Última oferta P2P", "blue"), unsafe_allow_html=True)
                if not df_hist.empty:
                    # Gráfico de linha com o histórico P2P
                    fig = px.line(df_hist, x="data_hora", y="valor", markers=True)
                    fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0), xaxis_title=None, yaxis_title=None)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Sem histórico recente.")

        st.divider()
        st.markdown("### 📋 Feed de Ofertas")
        dfp = ler_p2p_todos()
        if not dfp.empty:
            dfp['valor'] = dfp['valor'].apply(formatar_real)
            st.dataframe(dfp[['data_hora', 'programa', 'valor', 'grupo_nome', 'observacao']], use_container_width=True)
        elif plano == "Free": mostrar_paywall()

    # --- 2. CALCULADORA (CUSTO x P2P) ---
    elif menu == "Produção & Cálculo":
        st.header("🏭 Fábrica de Milhas")
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("1. Custo de Produção")
            prog_origem = st.selectbox("Origem", ["Livelo", "Esfera"])
            desc = st.slider("Desconto Compra (%)", 0, 60, 50)
            custo_base = 70.0 * (1 - desc/100)
            st.metric(f"Custo {prog_origem}", formatar_real(custo_base))
            
        with c2:
            st.subheader("2. Transferência")
            prog_dest = st.selectbox("Destino", ["Latam", "Smiles", "Azul"])
            bonus = st.number_input("Bônus (%)", 0, 120, 100, step=10)
            cpm_final = custo_base / (1 + bonus/100)
            st.markdown(criar_card_destaque("CPM FINAL (SEU CUSTO)", formatar_real(cpm_final), f"{prog_dest} com {bonus}% bônus", "green"), unsafe_allow_html=True)

        st.divider()
        
        st.subheader("3. Lucro vs P2P")
        val_p2p = pegar_preco_p2p_atual(prog_dest)
        
        if val_p2p > 0:
            lucro = val_p2p - cpm_final
            margem = (lucro/cpm_final)*100
            cor = "green" if lucro > 0 else "red"
            
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                st.markdown(criar_card_destaque("PREÇO VENDA (P2P)", formatar_real(val_p2p), "Baseado no mercado atual", "blue"), unsafe_allow_html=True)
            with col_res2:
                st.markdown(criar_card_destaque("LUCRO ESTIMADO", formatar_real(lucro), f"Margem: {margem:.1f}%", cor), unsafe_allow_html=True)
        else:
            st.warning("Não há cotação P2P cadastrada para este programa hoje.")

    # --- 3. CARTEIRA (VALUATION P2P) ---
    elif menu == "Minha Carteira":
        st.header("💼 Carteira")
        if plano == "Free": mostrar_paywall()
        else:
            with st.expander("➕ Adicionar Lote", expanded=True):
                with st.form("add"):
                    c1, c2, c3 = st.columns(3)
                    p = c1.selectbox("Prog", ["Latam", "Smiles", "Azul", "Livelo", "Esfera"])
                    q = c2.number_input("Qtd", 1000, step=1000)
                    cpm = c3.number_input("CPM Pago (R$)", 0.0, 70.0, 35.0)
                    if st.form_submit_button("Salvar"):
                        total = (q/1000)*cpm
                        if adicionar_carteira(user['email'], p, q, total): st.success("OK!"); time.sleep(0.5); st.rerun()
            
            dfc = ler_carteira_usuario(user['email'])
            if not dfc.empty:
                patrimonio = 0; custo_total = 0; view_data = []
                for _, row in dfc.iterrows():
                    prog = row['programa']
                    # Valuation baseada no P2P ou Custo (se for Livelo/Esfera)
                    if prog in ["Livelo", "Esfera"]:
                        # Pontos de banco valem o custo ou preço de venda P2P deles
                        val_mercado = pegar_preco_p2p_atual(prog)
                        if val_mercado == 0: val_mercado = 35.0 # Fallback conservador
                    else:
                        val_mercado = pegar_preco_p2p_atual(prog)
                    
                    qtd = float(row['quantidade'])
                    custo = float(row['custo_total'])
                    
                    val_venda = (qtd/1000) * val_mercado
                    lucro = val_venda - custo
                    patrimonio += val_venda
                    custo_total += custo
                    
                    view_data.append({
                        "ID": row['id'], "Prog": prog, "Qtd": f"{qtd:,.0f}".replace(',','.'),
                        "Custo": formatar_real(custo),
                        "Cotação P2P": formatar_real(val_mercado),
                        "Lucro Est.": formatar_real(lucro),
                        "val_raw": lucro
                    })
                
                k1, k2, k3 = st.columns(3)
                k1.metric("Total Investido", formatar_real(custo_total))
                k2.metric("Patrimônio (P2P)", formatar_real(patrimonio))
                k3.metric("Resultado", formatar_real(patrimonio - custo_total))
                st.divider()
                
                def color_lucro(val):
                    if isinstance(val, str) and "-" in val: return 'color: #d9534f; font-weight: bold;'
                    return 'color: #28a745; font-weight: bold;'
                
                st.dataframe(pd.DataFrame(view_data).drop(columns=['val_raw']).style.applymap(color_lucro, subset=['Lucro Est.']), use_container_width=True)
                
                rid = st.number_input("ID Excluir", step=1)
                if st.button("Remover"): remover_carteira(rid); st.rerun()
            else: st.info("Carteira vazia.")

    # --- 4. PROMOÇÕES ---
    elif menu == "Promoções":
        st.header("🔥 Radar de Promoções")
        if plano == "Free": mostrar_paywall()
        else:
            with st.spinner("Buscando promoções..."):
                df_news = buscar_promocoes_live()
                if not df_news.empty:
                    for _, row in df_news.iterrows():
                        st.markdown(f"##### 🔗 [{row['Título']}]({row['Link']})")
                        st.caption(f"📅 {row['Data']} | 📰 {row['Fonte']}")
                        st.divider()
                else: st.info("Nada encontrado.")

    # --- ADMIN ---
    elif menu == "👑 Gestão de Usuários":
        st.header("Admin CRM")
        df = admin_listar_todos()
        if not df.empty:
            sel = st.selectbox("Editar", df['email'].tolist())
            u = df[df['email'] == sel].iloc[0]
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                with st.form("edt"):
                    n = st.text_input("Nome", u['nome'])
                    p = st.selectbox("Plano", ["Free", "Pro", "Admin"], index=["Free","Pro","Admin"].index(u.get('plano','Free')))
                    s = st.selectbox("Status", ["Ativo", "Bloqueado"])
                    if st.form_submit_button("Salvar"): 
                        if admin_atualizar_dados(int(u['id']), n, u['email'], u['telefone'], p, s): st.success("OK"); time.sleep(1); st.rerun()
            st.dataframe(df)

if st.session_state['user']: sistema_logado()
else: tela_landing_page()
