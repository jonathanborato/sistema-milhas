import streamlit as st
import pandas as pd
import sqlite3
import time
import hashlib
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Milhas Pro System", page_icon="✈️", layout="wide")

# ==============================================================================
# 1. FUNÇÕES DE BANCO DE DADOS (BLINDADAS)
# ==============================================================================
NOME_BANCO = "milhas.db"

def iniciar_banco():
    con = sqlite3.connect(NOME_BANCO)
    cur = con.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, email TEXT, prazo_dias INTEGER, valor_total REAL, cpm REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS promocoes (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, titulo TEXT, link TEXT, origem TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS carteira (id INTEGER PRIMARY KEY AUTOINCREMENT, data_compra TEXT, programa TEXT, quantidade INTEGER, custo_total REAL, cpm_medio REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, nome TEXT, senha_hash TEXT, data_cadastro TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS mercado_p2p (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, grupo_nome TEXT, programa TEXT, tipo TEXT, valor REAL, observacao TEXT)')
    con.commit()
    con.close()

def criar_hash(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def verificar_login(email, senha):
    try:
        con = sqlite3.connect(NOME_BANCO)
        cur = con.cursor()
        senha_teste = criar_hash(senha)
        cur.execute("SELECT nome FROM usuarios WHERE email = ? AND senha_hash = ?", (email, senha_teste))
        res = cur.fetchone()
        con.close()
        return res[0] if res else None
    except: return None

def cadastrar_usuario(email, nome, senha):
    try:
        con = sqlite3.connect(NOME_BANCO)
        cur = con.cursor()
        if cur.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone():
            con.close(); return False
        cur.execute("INSERT INTO usuarios (email, nome, senha_hash, data_cadastro) VALUES (?, ?, ?, ?)", 
                    (email, nome, criar_hash(senha), datetime.now().strftime("%Y-%m-%d")))
        con.commit(); con.close(); return True
    except: return False

def ler_carteira():
    try:
        con = sqlite3.connect(NOME_BANCO)
        df = pd.read_sql_query("SELECT * FROM carteira", con)
        con.close()
        return df
    except: return pd.DataFrame()

def adicionar_milhas(prog, qtd, custo):
    con = sqlite3.connect(NOME_BANCO)
    cpm = custo/(qtd/1000)
    con.execute('INSERT INTO carteira (data_compra, programa, quantidade, custo_total, cpm_medio) VALUES (?, ?, ?, ?, ?)', 
                (datetime.now().strftime("%Y-%m-%d"), prog, qtd, custo, cpm))
    con.commit(); con.close()

def remover_item_carteira(id_item):
    con = sqlite3.connect(NOME_BANCO)
    con.execute('DELETE FROM carteira WHERE id = ?', (id_item,))
    con.commit(); con.close()

# AQUI ESTAVA O ERRO - REESCREVI PARA FICAR SEGURO
def adicionar_oferta_p2p(grupo, programa, tipo, valor, obs):
    con = sqlite3.connect(NOME_BANCO)
    
    # Separamos as variaveis para evitar erro de sintaxe
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    sql = 'INSERT INTO mercado_p2p (data_hora, grupo_nome, programa, tipo, valor, observacao) VALUES (?, ?, ?, ?, ?, ?)'
    dados = (agora, grupo, programa, tipo, valor, obs)
    
    con.execute(sql, dados)
    con.commit()
    con.close()

# Inicializa o banco ao abrir o site
iniciar_banco()

# ==============================================================================
# 2. SISTEMA DE LOGIN
# ==============================================================================
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
    st.session_state['usuario_nome'] = ""

def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://cdn-icons-png.flaticon.com/512/723/723955.png", width=80)
        st.title("Milhas Pro System")
        
        tab1, tab2 = st.tabs(["Entrar", "Criar Conta"])
        
        with tab1:
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            if st.button("Entrar", type="primary"):
                try:
                    if email == st.secrets["admin"]["email"] and senha == st.secrets["admin"]["senha"]:
                        st.session_state['logado'] = True; st.session_state['usuario_nome'] = st.secrets["admin"]["nome"]
                        st.rerun()
                except: pass
                
                user = verificar_login(email, senha)
                if user:
                    st.session_state['logado'] = True; st.session_state['usuario_nome'] = user
                    st.rerun()
                else: st.error("Dados inválidos.")
        
        with tab2:
            st.warning("Cadastros no plano gratuito podem ser resetados.")
            nnome = st.text_input("Nome")
            nemail = st.text_input("E-mail Novo")
            nsenha = st.text_input("Nova Senha", type="password")
            if st.button("Cadastrar"):
                if cadastrar_usuario(nemail, nnome, nsenha): st.success("Sucesso! Faça login.")
                else: st.error("Erro ao cadastrar.")

# ==============================================================================
# 3. SISTEMA PRINCIPAL (DASHBOARD)
# ==============================================================================
def sistema_principal():
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/723/723955.png", width=80)
        st.write(f"Olá, **{st.session_state['usuario_nome']}**")
        if st.button("Sair"): st.session_state['logado'] = False; st.rerun()
        st.divider()
        menu = st.radio("Menu", ["Minha Carteira", "Mercado (Hotmilhas)", "Mercado P2P", "Promoções"])

    st.title("🏦 Gestão de Milhas")

    try:
        con = sqlite3.connect(NOME_BANCO)
        df_cotacoes = pd.read_sql_query("SELECT * FROM historico ORDER BY data_hora ASC", con)
        con.close()
        if not df_cotacoes.empty:
            df_cotacoes['data_hora'] = pd.to_datetime(df_cotacoes['data_hora'])
            if 'email' in df_cotacoes.columns: df_cotacoes = df_cotacoes.rename(columns={'email': 'programa'})
    except: df_cotacoes = pd.DataFrame()

    if menu == "Minha Carteira":
        st.subheader("💼 Seu Estoque")
        with st.expander("➕ Adicionar"):
            c1, c2, c3 = st.columns(3)
            p = c1.selectbox("Programa", ["Latam Pass", "Smiles", "TudoAzul", "Livelo"])
            q = c2.number_input("Qtd", 1000, step=1000)
            v = c3.number_input("Custo R$", 0.0, step=10.0)
            if st.button("Salvar"): adicionar_milhas(p, q, v); st.rerun()
        
        dfc = ler_carteira()
        if not dfc.empty:
            st.dataframe(dfc)
            rid = st.number_input("ID para remover", step=1)
            if st.button("Remover"): remover_item_carteira(rid); st.rerun()
        else: st.info("Carteira Vazia")

    elif menu == "Mercado (Hotmilhas)":
        st.subheader("📊 Cotações Automáticas")
        if not df_cotacoes.empty:
            st.line_chart(df_cotacoes, x="data_hora", y="cpm", color="programa")
        else: st.warning("Sem dados do robô ainda.")

    elif menu == "Mercado P2P":
        st.subheader("📢 Radar Manual")
        with st.form("p2p"):
            c1, c2 = st.columns(2)
            g = c1.text_input("Grupo")
            pr = c2.selectbox("Prog", ["Latam", "Smiles", "Azul"])
            t = st.radio("Tipo", ["VENDA", "COMPRA"])
            val = st.number_input("Valor", 15.0)
            obs = st.text_input("Obs")
            if st.form_submit_button("Salvar"): adicionar_oferta_p2p(g, pr, t, val, obs); st.rerun()
        
        try:
            con = sqlite3.connect(NOME_BANCO)
            st.dataframe(pd.read_sql_query("SELECT * FROM mercado_p2p ORDER BY id DESC", con))
            con.close()
        except: pass

    elif menu == "Promoções":
        st.subheader("🔥 Radar")
        try:
            con = sqlite3.connect(NOME_BANCO)
            dfp = pd.read_sql_query("SELECT * FROM promocoes ORDER BY id DESC LIMIT 15", con)
            con.close()
            for _, r in dfp.iterrows(): st.markdown(f"[{r['titulo']}]({r['link']})")
        except: st.write("Nada.")

if st.session_state['logado']: sistema_principal()
else: tela_login()
