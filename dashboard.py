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

def iniciar_banco_local():
    con = conectar_local()
    cur = con.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS carteira (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_email TEXT, data_compra TEXT, programa TEXT, quantidade INTEGER, custo_total REAL, cpm_medio REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS mercado_p2p (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, grupo_nome TEXT, programa TEXT, tipo TEXT, valor REAL, observacao TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, nome TEXT, senha_hash TEXT, data_cadastro TEXT)')
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

# --- 5. MOTOR DE INTELIGÊNCIA DE MERCADO (SCANNER) ---
@st.cache_data(ttl=3600) # Atualiza a cada 1 hora
def analisar_mercado_milhas():
    feeds = [
        "https://passageirodeprimeira.com/feed/",
        "https://pontospravoar.com/feed/",
        "https://www.melhoresdestinos.com.br/feed"
    ]
    
    # Padrões de Mercado (Defaults conservadores)
    mercado = {
        "Livelo": {"desconto": 0, "cpm_compra": 70.00, "fonte": "Preço Padrão"}, # 70 = Cheio
        "Esfera": {"desconto": 0, "cpm_compra": 70.00, "fonte": "Preço Padrão"},
        "Smiles": {"bonus_transf": 0, "fonte": "Sem bônus detectado"},
        "Latam":  {"bonus_transf": 0, "fonte": "Sem bônus detectado"},
        "Azul":   {"bonus_transf": 0, "fonte": "Sem bônus detectado"}
    }
    
    noticias_relevantes = []

    for feed_url in feeds:
        try:
            d = feedparser.parse(feed_url)
            for entry in d.entries[:20]: # Analisa 20 últimas
                titulo = entry.title
                t_lower = titulo.lower()
                
                # 1. Detecta Desconto de Compra (Livelo/Esfera)
                # Ex: "Livelo oferece até 53% de desconto"
                if "compra de pontos" in t_lower or "desconto" in t_lower:
                    for prog in ["livelo", "esfera"]:
                        if prog in t_lower:
                            match_desc = re.search(r'(\d+)%\s*(?:de\s*)?(?:desconto|off)', t_lower)
                            if match_desc:
                                desc = int(match_desc.group(1))
                                # Só atualiza se for melhor que o atual
                                if desc > mercado[prog.capitalize()]["desconto"]:
                                    mercado[prog.capitalize()]["desconto"] = desc
                                    mercado[prog.capitalize()]["cpm_compra"] = 70.00 * (1 - desc/100)
                                    mercado[prog.capitalize()]["fonte"] = f"Via: {entry.title[:30]}..."
                                    noticias_relevantes.append(titulo)

                # 2. Detecta Bônus de Transferência
                # Ex: "Transfira para Smiles com até 80% de bônus"
                if "bônus" in t_lower or "bonus" in t_lower:
                    for prog in ["smiles", "latam", "azul", "tudoazul"]:
                        key_prog = "Azul" if "azul" in prog else prog.capitalize()
                        if key_prog in mercado:
                            match_bonus = re.search(r'(\d+)%\s*(?:de\s*)?(?:bônus|bonus)', t_lower)
                            if match_bonus:
                                bonus = int(match_bonus.group(1))
                                if bonus > mercado[key_prog]["bonus_transf"]:
                                    mercado[key_prog]["bonus_transf"] = bonus
                                    mercado[key_prog]["fonte"] = f"Via: {entry.title[:30]}..."
                                    noticias_relevantes.append(titulo)
        except: pass

    return mercado, noticias_relevantes

def calcular_melhor_emissao(programa_destino, milhas_necessarias, preco_dinheiro):
    # Pega dados frescos do scanner
    mercado, _ = analisar_mercado_milhas()
    
    # Define qual a melhor origem HOJE (Livelo ou Esfera)
    origem = "Livelo"
    cpm_origem = mercado["Livelo"]["cpm_compra"]
    
    if mercado["Esfera"]["cpm_compra"] < cpm_origem:
        origem = "Esfera"
        cpm_origem = mercado["Esfera"]["cpm_compra"]
    
    # Pega bônus ativo para o destino
    bonus = mercado.get(programa_destino.split()[0], {}).get("bonus_transf", 0)
    
    # CÁLCULO DO CUSTO DE PRODUÇÃO (CPM FINAL)
    # Fórmula: Custo Origem / (1 + Bonus)
    cpm_final = cpm_origem / (1 + (bonus/100))
    
    custo_total_milhas = (milhas_necessarias / 1000) * cpm_final
    
    if custo_total_milhas < preco_dinheiro:
        economia = preco_dinheiro - custo_total_milhas
        perc = (economia / preco_dinheiro) * 100
        return {
            "veredicto": "MILHAS",
            "custo_milhas": custo_total_milhas,
            "economia": economia,
            "detalhe": f"Comprando {origem} (R${cpm_origem:.2f}) + Transferindo com {bonus}% Bônus -> CPM Final {programa_destino}: R$ {cpm_final:.2f}",
            "cor": "green"
        }
    else:
        prejuizo = custo_total_milhas - preco_dinheiro
        return {
            "veredicto": "DINHEIRO",
            "custo_milhas": custo_total_milhas,
            "economia": prejuizo, # Na vdd é prejuízo evitado
            "detalhe": f"O custo de produção das milhas hoje (R$ {cpm_final:.2f}) é maior que o valor da passagem.",
            "cor": "red"
        }

# --- FUNÇÕES CRUD (P2P, CARTEIRA, USUARIOS) ---
def adicionar_p2p(g, p, t, v, o):
    sb = get_supabase()
    if sb:
        sb.table("mercado_p2p").insert({"data_hora": datetime.now().strftime("%Y-%m-%d %H:%M"), "grupo_nome": g, "programa": p, "tipo": "COMPRA", "valor": float(v), "observacao": o}).execute()
        return True, "Sucesso"
    return False, "Erro"

def ler_p2p_todos():
    sb = get_supabase()
    if sb:
        res = sb.table("mercado_p2p").select("*").order("id", desc=True).limit(50).execute()
        return pd.DataFrame(res.data)
    return pd.DataFrame()

def adicionar_carteira(email, p, q, v):
    sb = get_supabase()
    if sb:
        cpm = float(v)/(float(q)/1000) if float(q)>0 else 0
        sb.table("carteira").insert({"usuario_email": email, "data_compra": datetime.now().strftime("%Y-%m-%d"), "programa": p, "quantidade": int(q), "custo_total": float(v), "cpm_medio": cpm}).execute()
        return True, "Sucesso"
    return False, "Erro"

def remover_carteira(id_item):
    sb = get_supabase()
    if sb: sb.table("carteira").delete().eq("id", id_item).execute()

def ler_carteira_usuario(email):
    sb = get_supabase()
    if sb:
        res = sb.table("carteira").select("*").eq("usuario_email", email).execute()
        return pd.DataFrame(res.data)
    return pd.DataFrame()

def registrar_usuario(nome, email, senha, telefone):
    valida, msg = validar_senha_forte(senha)
    if not valida: return False, msg
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("usuarios").select("id").eq("email", email).execute()
            if len(res.data) > 0: return False, "Email já existe."
            sb.table("usuarios").insert({"email": email, "nome": nome, "senha_hash": hashlib.sha256(senha.encode()).hexdigest(), "telefone": telefone, "plano": "Free", "status": "Ativo"}).execute()
            return True, "Criado!"
        except Exception as e: return False, f"Erro: {e}"
    return False, "Sem conexão"

def autenticar_usuario(email, senha):
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("usuarios").select("*").eq("email", email).eq("senha_hash", hashlib.sha256(senha.encode()).hexdigest()).execute()
            if len(res.data) > 0: return {"nome": res.data[0]['nome'], "plano": res.data[0].get('plano', 'Free'), "email": email}
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

# --- INICIALIZA ---
iniciar_banco_local()

# --- CSS ---
st.markdown("""
<style>
    .block-container {padding-top: 4rem !important; padding-bottom: 2rem !important;}
    div.stButton > button {width: 100%; background-color: #0E436B; color: white; border-radius: 5px; font-weight: bold;}
    div.stButton > button:hover {background-color: #082d4a; color: white;}
    div[data-testid="stImage"] {display: flex; justify-content: center; align-items: center; width: 100%;}
    a {text-decoration: none; color: #0E436B; font-weight: bold;}
    
    .pricing-card { background: white; padding: 40px; border-radius: 15px; text-align: center; border: 1px solid #eee; box-shadow: 0 10px 30px rgba(0,0,0,0.1); position: relative; overflow: hidden; }
    .popular-badge { background: #FFC107; color: #333; padding: 5px 20px; font-weight: bold; font-size: 0.8rem; position: absolute; top: 20px; right: -30px; transform: rotate(45deg); width: 120px; }
    .lp-card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); text-align: center; height: 100%; border: 1px solid #EEF2F6; }
    .lp-icon { font-size: 2.5rem; margin-bottom: 15px; display: block; }
</style>
""", unsafe_allow_html=True)

def mostrar_paywall():
    st.error("🔒 RECURSO PRO")
    st.info("Faça o upgrade para acessar.")

if 'user' not in st.session_state: st.session_state['user'] = None

# ==============================================================================
# TELA LOGIN (LANDING PAGE)
# ==============================================================================
def tela_login():
    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.image(LOGO_URL, width=220)
        st.markdown("# O Sistema do Milheiro Profissional 🚀\n\nChega de adivinhar. Saiba exatamente o custo de produção e o momento certo de vender ou viajar.")
    with c2:
        st.markdown("<div style='background: white; padding: 25px; border-radius: 12px; box-shadow: 0 10px 30px rgba(14, 67, 107, 0.1); border: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["ENTRAR", "CRIAR"])
        with t1:
            email = st.text_input("E-mail", key="log_e")
            senha = st.text_input("Senha", type="password", key="log_p")
            if st.button("ACESSAR", type="primary", key="btn_l"):
                try:
                    if email == st.secrets["admin"]["email"] and senha == st.secrets["admin"]["senha"]:
                        st.session_state['user'] = {"nome": st.secrets["admin"]["nome"], "plano": "Admin", "email": email}; st.rerun()
                except: pass
                u = autenticar_usuario(email, senha)
                if u: st.session_state['user'] = u; st.rerun()
                else: st.error("Erro no login.")
        with t2:
            n = st.text_input("Nome", key="c_n"); e = st.text_input("Email", key="c_e"); w = st.text_input("Zap", key="c_w"); p = st.text_input("Senha", type="password", key="c_p")
            if st.button("CADASTRAR", key="btn_c"):
                if registrar_usuario(n, e, p, w): st.success("Criado! Faça login.")
                else: st.error("Erro ao criar.")
        st.markdown("</div>", unsafe_allow_html=True)

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
                <p>✅ Scanner Automático de Promoções</p><p>✅ Calculadora de Custo de Emissão</p><p>✅ Gestão de Carteira Inteligente</p>
            </div>
        </div>""", unsafe_allow_html=True)

# ==============================================================================
# SISTEMA LOGADO
# ==============================================================================
def sistema_logado():
    user = st.session_state['user']
    plano = user['plano']
    opcoes = ["Visão de Mercado (Scanner)", "✈️ Robô de Passagens", "Minha Carteira", "Mercado P2P"]
    if plano == "Admin": opcoes.append("👑 Gestão de Usuários")

    with st.sidebar:
        st.image(LOGO_URL, width=180)
        st.markdown(f"<div style='text-align: center; margin-top: 10px;'>Olá, <b>{user['nome'].split()[0]}</b></div>", unsafe_allow_html=True)
        if plano == "Admin": st.success("👑 ADMIN")
        elif plano == "Pro": st.success("⭐ PRO")
        else: st.info("🔹 FREE")
        st.divider(); menu = st.radio("Menu", opcoes); st.divider()
        if st.button("SAIR"): st.session_state['user'] = None; st.rerun()

    # --- SCANNER DE MERCADO ---
    mercado, noticias = analisar_mercado_milhas()

    if menu == "Visão de Mercado (Scanner)":
        st.header("📊 Inteligência de Mercado (Ao Vivo)")
        st.info("O sistema varre os blogs de milhas em tempo real para encontrar o Custo de Produção (CPM) atualizado.")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏭 Compra de Pontos (Hoje)")
            for prog in ["Livelo", "Esfera"]:
                dados = mercado[prog]
                st.markdown(criar_card_destaque(f"CPM {prog}", formatar_real(dados['cpm_compra']), f"Desc: {dados['desconto']}% ({dados['fonte']})", "blue"), unsafe_allow_html=True)
        
        with col2:
            st.subheader("🔄 Bônus de Transferência")
            for prog in ["Smiles", "Latam", "Azul"]:
                dados = mercado[prog]
                cor = "green" if dados['bonus_transf'] > 0 else "orange"
                st.markdown(criar_card_destaque(f"Bônus {prog}", f"{dados['bonus_transf']}%", dados['fonte'], cor), unsafe_allow_html=True)
        
        st.divider()
        st.subheader("📰 Últimas Notícias Relevantes")
        if noticias:
            for n in noticias: st.markdown(f"• {n}")
        else: st.caption("Nenhuma notícia de alta relevância detectada nas últimas horas.")

    # --- ROBÔ DE PASSAGENS (INTEGRADO AO SCANNER) ---
    elif menu == "✈️ Robô de Passagens":
        st.header("✈️ Calculadora Inteligente")
        st.info("Calcula se vale a pena emitir usando o custo de produção das milhas HOJE.")
        
        if plano == "Free": mostrar_paywall()
        else:
            with st.form("robo"):
                c1, c2 = st.columns(2)
                prog = c1.selectbox("Programa", ["Smiles", "Latam", "Azul"])
                milhas = c2.number_input("Valor em Milhas", 1000, step=1000, value=50000)
                dinheiro = st.number_input("Preço em Dinheiro (R$)", 100.0, step=50.0, value=2500.0)
                
                if st.form_submit_button("Calcular"):
                    res = calcular_melhor_emissao(prog, milhas, dinheiro)
                    
                    if res['veredicto'] == "MILHAS":
                        st.success(f"✅ EMITA COM MILHAS! Economia: {formatar_real(res['economia'])}")
                        st.markdown(f"**Por que?** {res['detalhe']}")
                        st.metric("Custo Real da Emissão", formatar_real(res['custo_milhas']))
                    else:
                        st.error(f"🛑 PAGUE EM DINHEIRO! Prejuízo evitado: {formatar_real(res['economia'])}")
                        st.markdown(f"**Por que?** {res['detalhe']}")
                        st.metric("Custo Real em Milhas seria", formatar_real(res['custo_milhas']))

    elif menu == "Minha Carteira":
        st.header("💼 Carteira")
        if plano == "Free": mostrar_paywall()
        else:
            with st.expander("➕ Adicionar Lote", expanded=True):
                with st.form("add_carteira"):
                    c1, c2, c3 = st.columns(3)
                    p = c1.selectbox("Programa", ["Latam", "Smiles", "Azul", "Livelo"])
                    q = c2.number_input("Qtd", 1000, step=1000)
                    cpm = c3.number_input("CPM Pago (R$)", 0.0, 100.0, 35.0)
                    if st.form_submit_button("Salvar"):
                        total = (q/1000)*cpm
                        if adicionar_carteira(user['email'], p, q, total): st.success("Salvo!"); time.sleep(0.5); st.rerun()
            
            dfc = ler_carteira_usuario(user['email'])
            if not dfc.empty:
                # Recalcula valor atual baseado no custo de produção atual (reposição)
                patrimonio = 0
                view_data = []
                for _, row in dfc.iterrows():
                    # Valor de mercado baseado no custo de produção atual (Scanner)
                    # Se eu tivesse que comprar essas milhas hoje, quanto custaria?
                    prog_nome = row['programa'].split()[0] if " " in row['programa'] else row['programa']
                    # Pega custo de produção da Livelo hoje com bonus
                    bonus_hoje = mercado.get(prog_nome, {}).get('bonus_transf', 0)
                    cpm_livelo = mercado['Livelo']['cpm_compra']
                    cpm_reposicao = cpm_livelo / (1 + bonus_hoje/100)
                    
                    val_atual = (row['quantidade']/1000) * cpm_reposicao
                    patrimonio += val_atual
                    
                    view_data.append({
                        "Programa": row['programa'],
                        "Qtd": f"{row['quantidade']:,.0f}",
                        "CPM Pago": formatar_real(row['cpm_medio']),
                        "Valor (Reposição)": formatar_real(val_atual)
                    })
                st.metric("Patrimônio (Custo Reposição)", formatar_real(patrimonio))
                st.dataframe(pd.DataFrame(view_data), use_container_width=True)
                rid = st.number_input("ID para remover", step=1)
                if st.button("Remover"): remover_carteira(rid); st.rerun()
            else: st.info("Vazia.")

    elif menu == "Mercado P2P":
        st.header("📢 Radar P2P")
        if plano == "Admin":
            with st.form("p2p"):
                c1, c2 = st.columns(2)
                g = c1.text_input("Grupo")
                p = c2.selectbox("Prog", ["Latam", "Smiles", "Azul"])
                val = st.number_input("Valor", 15.0)
                obs = st.text_input("Obs")
                if st.form_submit_button("Publicar"): adicionar_p2p(g, p, "COMPRA", val, obs); st.rerun()
        
        dfp = ler_p2p_todos()
        if not dfp.empty:
            dfp['valor'] = dfp['valor'].apply(formatar_real)
            st.dataframe(dfp, use_container_width=True)
        elif plano == "Free": mostrar_paywall()

    elif menu == "👑 Gestão de Usuários":
        st.header("Admin CRM")
        df = admin_listar_todos()
        if not df.empty: st.dataframe(df)

# MAIN
if st.session_state['user']: sistema_logado()
else: tela_landing_page()
