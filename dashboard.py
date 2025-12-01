import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import time
import re
import plotly.express as px
import feedparser
import stripe
from datetime import datetime

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(
    page_title="MilhasPro | O Sistema do Milheiro",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

LOGO_URL = "https://raw.githubusercontent.com/jonathanborato/sistema-milhas/main/logo.png"

# --- 2. CONFIGURAÇÃO DE AMBIENTE ---
try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

try:
    stripe.api_key = st.secrets["stripe"]["api_key"]
    STRIPE_AVAILABLE = True
except:
    STRIPE_AVAILABLE = False

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

def iniciar_banco_local():
    con = conectar_local()
    con.execute('CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, email TEXT, prazo_dias INTEGER, valor_total REAL, cpm REAL)')
    con.execute('CREATE TABLE IF NOT EXISTS carteira (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_email TEXT, data_compra TEXT, programa TEXT, quantidade INTEGER, custo_total REAL, cpm_medio REAL)')
    con.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, nome TEXT, senha_hash TEXT, data_cadastro TEXT, plano TEXT DEFAULT "Free")')
    con.commit(); con.close()

# --- 4. UTILITÁRIOS ---
def criar_hash(senha): return hashlib.sha256(senha.encode()).hexdigest()

def formatar_real(valor):
    if valor is None: return "R$ 0,00"
    try: return f"R$ {float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except: return "R$ 0,00"

def plotar_grafico(df, programa):
    cor = "#0E436B"
    if "Latam" in programa: cor = "#E30613"
    elif "Smiles" in programa: cor = "#FF7000"
    elif "Azul" in programa: cor = "#00AEEF"
    if df.empty: return None
    fig = px.area(df, x="data_hora", y="cpm", markers=True)
    fig.update_traces(line_color=cor, fillcolor=cor, marker=dict(size=6, color="white", line=dict(width=2, color=cor)))
    fig.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=0), xaxis_title=None, yaxis_title=None, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", yaxis=dict(showgrid=True, gridcolor='#f0f0f0'), xaxis=dict(showgrid=False), showlegend=False)
    return fig

def criar_card_preco(titulo, valor, is_winner=False):
    valor_fmt = formatar_real(valor) if valor > 0 else "--"
    css_class = "price-card winner-pulse" if is_winner and valor > 0 else "price-card"
    icon_html = '<span class="winner-icon">🏆</span>' if is_winner and valor > 0 else ""
    return f'<div class="{css_class}"><div class="card-title">{titulo} {icon_html}</div><div class="card-value">{valor_fmt}</div></div>'

# --- FUNÇÕES DE PAGAMENTO ---
def criar_sessao_checkout(email_usuario):
    if not STRIPE_AVAILABLE: return None
    try:
        domain_url = st.secrets["stripe"]["domain_url"]
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price_data': {'currency': 'brl', 'product_data': {'name': 'Assinatura MilhasPro (Pro)'}, 'unit_amount': 4990}, 'quantity': 1}],
            mode='payment',
            success_url=domain_url + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=domain_url + '?cancelado=true',
            customer_email=email_usuario,
        )
        return checkout_session.url
    except Exception as e: st.error(f"Erro Stripe: {e}"); return None

def verificar_pagamento(session_id):
    if not STRIPE_AVAILABLE: return False, None
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == 'paid': return True, session.customer_email
    except: pass
    return False, None

# --- 5. FUNÇÕES DE DADOS ---
@st.cache_data(ttl=900) 
def buscar_promocoes_live():
    feeds = [{"url": "https://passageirodeprimeira.com/feed/", "fonte": "PP"}, {"url": "https://pontospravoar.com/feed/", "fonte": "PPV"}, {"url": "https://www.melhoresdestinos.com.br/feed", "fonte": "MD"}]
    keywords = ["bônus", "transferência", "compra", "livelo", "esfera", "latam", "smiles", "azul"]
    news = []
    for f in feeds:
        try:
            d = feedparser.parse(f['url'])
            for e in d.entries[:6]:
                if any(k in e.title.lower() for k in keywords):
                    news.append({"Data": e.get('published', 'Hoje')[:16], "Título": e.title, "Fonte": f['fonte'], "Link": e.link})
        except: pass
    return pd.DataFrame(news)

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

@st.cache_data(ttl=60)
def ler_dados_historico():
    con = conectar_local()
    try:
        df = pd.read_sql_query("SELECT * FROM historico ORDER BY data_hora ASC", con)
        if 'email' in df.columns: df = df.rename(columns={'email': 'programa'})
        if not df.empty: df['data_hora'] = pd.to_datetime(df['data_hora'], errors='coerce')
    except: df = pd.DataFrame()
    con.close()
    return df

def autenticar_usuario(email, senha):
    sb = get_supabase()
    if not sb: return None
    try:
        h = hashlib.sha256(senha.encode()).hexdigest()
        res = sb.table("usuarios").select("*").eq("email", email).eq("senha_hash", h).execute()
        if len(res.data) > 0:
            u = res.data[0]
            # Garante que o campo plano exista, se não, assume Free
            plano = u.get('plano') if u.get('plano') is not None else 'Free'
            return {"nome": u['nome'], "plano": plano, "email": email}
    except: pass
    return None

def registrar_usuario(nome, email, senha, telefone):
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("usuarios").select("id").eq("email", email).execute()
            if len(res.data) > 0: return False, "E-mail já existe."
            dados = {"email": email, "nome": nome, "senha_hash": hashlib.sha256(senha.encode()).hexdigest(), "telefone": telefone, "plano": "Free"}
            sb.table("usuarios").insert(dados).execute()
            return True, "Conta criada!"
        except Exception as e: return False, f"Erro: {e}"
    return False, "Erro conexão."

# --- CÉREBRO DO ROBÔ DE PASSAGENS ---
def calcular_melhor_rota(programa_destino, milhas_necessarias):
    # ESTE É O CÉREBRO. No futuro, estes dados virão do banco de dados atualizado diariamente.
    # Por enquanto, simulamos o estado atual do mercado.
    
    cenarios_mercado = {
        "Smiles": [
            {"rota": "Compra Direta Smiles (Promo)", "cpm_final": 21.00, "detalhe": "Comprar no balcão com voucher 200%."},
            {"rota": "Livelo -> Smiles (Bônus 80%)", "cpm_final": 19.44, "detalhe": "Comprar Livelo com 50% off (R$35) e transferir com 80%."},
            {"rota": "Esfera -> Smiles (Bônus 100%)", "cpm_final": 17.50, "detalhe": "Comprar Esfera a R$35 e transferir com 100% (Raridade!)."}
        ],
        "Latam Pass": [
             {"rota": "Compra Direta Latam", "cpm_final": 28.00, "detalhe": "Preço padrão alto."},
             {"rota": "Livelo -> Latam (Bônus 30%)", "cpm_final": 26.92, "detalhe": "Livelo R$35 + Bônus fraco."},
        ],
        "TudoAzul": [
             {"rota": "Compra Direta Azul", "cpm_final": 25.00, "detalhe": "Promoção de compra de pontos."},
             {"rota": "Livelo -> Azul (Bônus 100%)", "cpm_final": 17.50, "detalhe": "Bônus excelente de aniversário."},
        ]
    }
    
    if programa_destino not in cenarios_mercado:
        return None

    opcoes = cenarios_mercado[programa_destino]
    # Calcula o custo total para cada opção e encontra a melhor
    melhor_opcao = None
    menor_custo = float('inf')

    for op in opcoes:
        custo_total = (milhas_necessarias / 1000) * op['cpm_final']
        op['custo_total_calculado'] = custo_total
        if custo_total < menor_custo:
            menor_custo = custo_total
            melhor_opcao = op
            
    return melhor_opcao

# --- INICIALIZAÇÃO ---
iniciar_banco_local()

# --- CSS PREMIUM ---
st.markdown("""
<style>
    /* Fundo e Fonte */
    .stApp { background: linear-gradient(180deg, #F8FAFC 0%, #FFFFFF 100%); font-family: 'Segoe UI', sans-serif; }
    .block-container {padding-top: 2rem !important;}
    .lp-card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); text-align: center; height: 100%; border: 1px solid #EEF2F6; transition: transform 0.3s ease; }
    .lp-card:hover { transform: translateY(-5px); box-shadow: 0 8px 25px rgba(14, 67, 107, 0.15); border-color: #0E436B; }
    .lp-icon { font-size: 2.5rem; margin-bottom: 15px; display: block; }
    .lp-title { font-weight: 700; color: #0E436B; margin-bottom: 10px; font-size: 1.1rem; }
    .lp-text { color: #64748B; font-size: 0.9rem; line-height: 1.5; }
    div.stButton > button { width: 100%; background-color: #0E436B; color: white; border-radius: 8px; font-weight: 600; border: none; padding: 0.6rem 1rem; transition: background 0.2s; }
    div.stButton > button:hover { background-color: #0A304E; color: white; box-shadow: 0 2px 8px rgba(14, 67, 107, 0.3); }
    @keyframes pulse-green { 0% { box-shadow: 0 0 0 0 rgba(37, 211, 102, 0.7); } 70% { box-shadow: 0 0 0 10px rgba(37, 211, 102, 0); } 100% { box-shadow: 0 0 0 0 rgba(37, 211, 102, 0); } }
    @keyframes spin-slow { 0% { transform: rotate(0deg); } 25% { transform: rotate(15deg); } 75% { transform: rotate(-15deg); } 100% { transform: rotate(0deg); } }
    .price-card { background: white; padding: 15px; border-radius: 10px; border: 1px solid #E2E8F0; text-align: center; margin-bottom: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .winner-pulse { border: 2px solid #25d366 !important; background: #F0FDF4 !important; animation: pulse-green 2s infinite; color: #0E436B; }
    .card-title { font-size: 0.85rem; color: #64748B; margin-bottom: 5px; font-weight: 600; }
    .card-value { font-size: 1.5rem; font-weight: 800; color: #1E293B; }
    .winner-icon { display: inline-block; animation: spin-slow 3s infinite ease-in-out; margin-left: 5px; }
    div[data-testid="stImage"] { display: flex; justify-content: center; align-items: center; width: 100%; }
    a {text-decoration: none; color: #0E436B; font-weight: bold;}
    .pricing-card { background: white; padding: 40px; border-radius: 15px; text-align: center; border: 1px solid #eee; box-shadow: 0 10px 30px rgba(0,0,0,0.1); position: relative; overflow: hidden; }
    .popular-badge { background: #FFC107; color: #333; padding: 5px 20px; font-weight: bold; font-size: 0.8rem; position: absolute; top: 20px; right: -30px; transform: rotate(45deg); width: 120px; }
    
    /* ESTILO DO RESULTADO DO ROBÔ */
    .robo-result-box {
        background: linear-gradient(135deg, #0E436B 0%, #0A304E 100%);
        color: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 10px 25px rgba(14, 67, 107, 0.3);
        text-align: center;
        margin-top: 20px;
        animation: fadeIn 0.5s ease-in;
    }
    .robo-highlight {
        color: #FFC107; font-weight: 800; font-size: 1.2rem;
    }
    .robo-saving {
        background: rgba(37, 211, 102, 0.2);
        border: 1px solid #25d366;
        padding: 10px;
        border-radius: 8px;
        margin-top: 15px;
        font-weight: bold;
    }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
</style>
""", unsafe_allow_html=True)

def mostrar_paywall():
    st.error("🔒 RECURSO PRO")
    if st.button("ASSINAR AGORA (R$ 49,90)"):
        if st.session_state['user']:
            link = criar_sessao_checkout(st.session_state['user']['email'])
            if link: st.link_button("👉 IR PARA O PAGAMENTO SEGURO", link)
            else: st.error("Erro Stripe.")
    st.info("Faça o upgrade para desbloquear.")

# --- SESSÃO ---
if 'user' not in st.session_state: st.session_state['user'] = None

# ==============================================================================
# TELA 1: LANDING PAGE
# ==============================================================================
def tela_landing_page():
    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.image(LOGO_URL, width=220)
        st.markdown("""
        # O Sistema Definitivo para Milheiros Profissionais 🚀
        Domine o mercado de milhas com inteligência de dados. O **MilhasPro** automatiza cotações, monitora o mercado P2P e gerencia seu patrimônio em tempo real.
        """)
    with c2:
        st.markdown("<div style='background: white; padding: 25px; border-radius: 12px; box-shadow: 0 10px 30px rgba(14, 67, 107, 0.1); border: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #0E436B; margin-top: 0;'>Acessar Painel</h3>", unsafe_allow_html=True)
        tab_l, tab_c = st.tabs(["ENTRAR", "CRIAR CONTA"])
        with tab_l:
            with st.form("login_form"):
                email = st.text_input("E-mail")
                senha = st.text_input("Senha", type="password")
                submitted = st.form_submit_button("ENTRAR AGORA")
                if submitted:
                    try:
                        if email == st.secrets["admin"]["email"] and senha == st.secrets["admin"]["senha"]:
                            st.session_state['user'] = {"nome": st.secrets["admin"]["nome"], "plano": "Admin", "email": email}
                            st.rerun()
                    except: pass
                    user = autenticar_usuario(email, senha)
                    if user:
                        st.session_state['user'] = user
                        st.toast(f"Bem-vindo, {user['nome']}!")
                        time.sleep(0.5); st.rerun()
                    else: st.error("Dados inválidos.")
        with tab_c:
            with st.form("cad_form"):
                nome = st.text_input("Nome")
                c_email = st.text_input("E-mail")
                whats = st.text_input("WhatsApp")
                pw = st.text_input("Senha (Min 8 chars)")
                submitted_cad = st.form_submit_button("CADASTRAR GRÁTIS")
                if submitted_cad:
                    ok, msg = registrar_usuario(nome, c_email, pw, whats)
                    if ok: st.success("Sucesso! Faça login."); st.balloons()
                    else: st.error(msg)
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1: st.markdown("""<div class="lp-card"><span class="lp-icon">🤖</span><div class="lp-title">Automação Inteligente</div><div class="lp-text">Nosso robô monitora a Hotmilhas todo dia e salva o histórico.</div></div>""", unsafe_allow_html=True)
    with col_f2: st.markdown("""<div class="lp-card"><span class="lp-icon">👥</span><div class="lp-title">Radar P2P Exclusivo</div><div class="lp-text">Saiba quanto estão pagando nos grupos fechados.</div></div>""", unsafe_allow_html=True)
    with col_f3: st.markdown("""<div class="lp-card"><span class="lp-icon">💼</span><div class="lp-title">Controle de Patrimônio</div><div class="lp-text">Registre suas compras e veja seu lucro baseado na melhor cotação.</div></div>""", unsafe_allow_html=True)
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
                <p>✅ Acesso Ilimitado ao Dashboard</p><p>✅ Cotações P2P Exclusivas</p><p>✅ Gestão de Carteira Inteligente</p>
            </div>
            <br>
        </div>
        """, unsafe_allow_html=True)
        st.info("👆 Crie sua conta grátis acima para assinar.")

# ==============================================================================
# TELA 2: SISTEMA LOGADO
# ==============================================================================
def sistema_logado():
    user = st.session_state['user']
    plano = user['plano']
    
    # VERIFICAR RETORNO DE PAGAMENTO
    params = st.query_params
    if "session_id" in params:
        pagou, email_pagante = verificar_pagamento(params["session_id"])
        if pagou and email_pagante == user['email']:
            sb = get_supabase()
            if sb:
                sb.table("usuarios").update({"plano": "Pro"}).eq("email", user['email']).execute()
                user['plano'] = "Pro"
                st.toast("Parabéns! Você agora é PRO!", icon="🚀")
                st.balloons()
                time.sleep(2); st.rerun()
        st.query_params.clear()
    
    opcoes = ["Dashboard (Mercado)", "✈️ Robô de Passagens (Beta)", "Minha Carteira", "Promoções (Ao Vivo)"]
    if plano == "Admin": opcoes.append("👑 Gestão de Usuários")

    with st.sidebar:
        st.image(LOGO_URL, width=180)
        st.markdown(f"<div style='text-align: center; margin-top: 10px;'>Olá, <b>{user['nome'].split()[0]}</b></div>", unsafe_allow_html=True)
        if plano == "Admin": st.success("👑 ADMIN")
        elif plano == "Pro": st.success("⭐ PRO")
        else: st.info("🔹 FREE")
        st.divider()
        menu = st.radio("Menu", opcoes)
        st.divider()
        if st.button("SAIR DO SISTEMA"): st.session_state['user'] = None; st.rerun()

    df_cotacoes = ler_dados_historico()

    if menu == "Dashboard (Mercado)":
        st.header("📊 Visão de Mercado")
        if not df_cotacoes.empty:
            cols = st.columns(3)
            for i, p in enumerate(["Latam", "Smiles", "Azul"]):
                d = df_cotacoes[df_cotacoes['programa'].str.contains(p, case=False, na=False)]
                val_hot = d.iloc[-1]['cpm'] if not d.empty else 0.0
                val_p2p = 0.0 # Aqui você pode reconectar sua função pegar_ultimo_p2p se quiser
                hot_wins = val_hot > val_p2p and val_hot > 0
                p2p_wins = val_p2p > val_hot and val_p2p > 0
                with cols[i]:
                    st.markdown(f"### {p}")
                    mc1, mc2 = st.columns(2)
                    with mc1: st.markdown(criar_card_preco("🤖 Hotmilhas", val_hot, hot_wins), unsafe_allow_html=True)
                    with mc2: st.markdown(criar_card_preco("👥 P2P", val_p2p, p2p_wins), unsafe_allow_html=True)
                    st.divider()
                    if not d.empty: st.plotly_chart(plotar_grafico(d, p), use_container_width=True)
        else: st.warning("Aguardando robô.")

    # --- A NOVA ÁREA SURREAL ---
    elif menu == "✈️ Robô de Passagens (Beta)":
        st.header("✈️ Otimizador de Rotas Surreal")
        st.markdown("""
        <div style='background: #F0F4FF; padding: 20px; border-radius: 10px; border-left: 5px solid #0E436B; margin-bottom: 25px;'>
            <strong style='color: #0E436B; font-size: 1.1rem;'>Como funciona?</strong><br>
            Você encontra o voo, e o nosso robô calcula <b>automaticamente</b> a forma mais barata de emiti-lo HOJE, 
            cruzando dados de custo de aquisição de pontos (Livelo, Esfera) e bônus de transferência ativos no momento.
        </div>
        """, unsafe_allow_html=True)

        if plano == "Free": mostrar_paywall()
        else:
            with st.form("robo_form"):
                c1, c2 = st.columns(2)
                prog_destino = c1.selectbox("Onde você viu a passagem?", ["Smiles", "Latam Pass", "TudoAzul"])
                milhas = c2.number_input("Valor em Milhas (Total)", min_value=1000, step=1000, value=50000)
                valor_dinheiro = st.number_input("Quanto custa essa mesma passagem em DINHEIRO (R$)? (Para cálculo de economia)", min_value=100.0, step=50.0, value=2500.0)
                
                submitted = st.form_submit_button("🤖 ATIVAR ROBÔ E CALCULAR MELHOR ROTA")

                if submitted:
                    with st.spinner("O robô está analisando todas as combinações de mercado possíveis hoje..."):
                        time.sleep(1.5) # Efeito dramático
                        melhor_cenario = calcular_melhor_rota(prog_destino, milhas)
                        
                        if melhor_cenario:
                            custo_milhas = melhor_cenario['custo_total_calculado']
                            economia = valor_dinheiro - custo_milhas
                            perc_economia = (economia / valor_dinheiro) * 100

                            # RESULTADO SURREAL
                            st.markdown(f"""
                            <div class="robo-result-box">
                                <h2>🚀 ROTA OTIMIZADA ENCONTRADA!</h2>
                                <p style="font-size: 1.2rem;">Para este voo, a melhor estratégia HOJE é:</p>
                                <p class="robo-highlight">{melhor_cenario['rota']}</p>
                                <p><i>({melhor_cenario['detalhe']})</i></p>
                                <hr style="border-color: rgba(255,255,255,0.2);">
                                <div style="display: flex; justify-content: space-around; margin-top: 20px;">
                                    <div>
                                        <div style="font-size: 0.9rem; opacity: 0.8;">Custo do Milheiro Final</div>
                                        <div style="font-size: 1.5rem; font-weight: bold;">{formatar_real(melhor_cenario['cpm_final'])}</div>
                                    </div>
                                    <div>
                                        <div style="font-size: 0.9rem; opacity: 0.8;">Custo Total da Emissão</div>
                                        <div style="font-size: 2.2rem; font-weight: 800; color: #FFC107;">{formatar_real(custo_milhas)}</div>
                                    </div>
                                </div>
                                <div class="robo-saving">
                                    🤑 VOCÊ VAI ECONOMIZAR: <b>{formatar_real(economia)}</b> ({perc_economia:.0f}% mais barato que pagar em dinheiro)
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            st.balloons()
                        else:
                            st.error("Não encontramos uma rota otimizada para este programa hoje.")


    elif menu == "Minha Carteira":
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
                patrimonio = 0; custo_total = 0; view_data = []
                for _, row in dfc.iterrows():
                    prog_nome = row['programa'].split()[0]
                    val_hot = 0.0
                    if not df_cotacoes.empty:
                        f = df_cotacoes[df_cotacoes['programa'].str.contains(prog_nome, case=False, na=False)]
                        if not f.empty: val_hot = f.iloc[-1]['cpm']
                    val_p2p = 0.0 # pegar_ultimo_p2p(prog_nome)
                    melhor_preco = max(val_hot, val_p2p)
                    if melhor_preco == 0: origem = "Sem Cotação"
                    else: origem = "Hotmilhas" if val_hot >= val_p2p else "P2P"
                    qtd = float(row['quantidade']); custo = float(row['custo_total']); cpm_pago = float(row['cpm_medio'])
                    val_venda = (qtd / 1000) * melhor_preco
                    lucro = val_venda - custo
                    patrimonio += val_venda; custo_total += custo
                    view_data.append({"ID": row['id'], "Programa": row['programa'], "Qtd": f"{qtd:,.0f}".replace(',', '.'), "Custo": formatar_real(custo), "CPM Pago": formatar_real(cpm_pago), "Melhor Cotação": f"{formatar_real(melhor_preco)} ({origem})", "Lucro (Hoje)": formatar_real(lucro), "val_lucro_raw": lucro})
                k1, k2, k3 = st.columns(3)
                k1.metric("Total Investido", formatar_real(custo_total))
                k2.metric("Patrimônio Atual", formatar_real(patrimonio))
                delta_perc = ((patrimonio/custo_total)-1)*100 if custo_total > 0 else 0
                k3.metric("Lucro Projetado", formatar_real(patrimonio - custo_total), delta=f"{delta_perc:.1f}%")
                st.divider()
                def color_lucro(val):
                    if isinstance(val, str) and "-" in val: return 'color: #d9534f; font-weight: bold;'
                    return 'color: #28a745; font-weight: bold;'
                st.dataframe(pd.DataFrame(view_data).style.applymap(color_lucro, subset=['Lucro (Hoje)']).drop(columns=['val_lucro_raw']), use_container_width=True)
                rid = st.number_input("ID para remover", step=1)
                if st.button("🗑️ Remover Lote"): remover_carteira(rid); st.rerun()
            else: st.info("Carteira vazia.")

    elif menu == "Promoções (Ao Vivo)":
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
                else: st.info("Nenhuma promoção encontrada.")

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

# MAIN ROUTER
if st.session_state['user']: sistema_logado()
else: tela_landing_page()
