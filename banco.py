import sqlite3
from datetime import datetime
import hashlib
import streamlit as st
from supabase import create_client, Client

# --- CONFIGURAÇÃO HÍBRIDA ---
NOME_BANCO_LOCAL = "milhas.db"

# --- CONEXÃO COM A NUVEM (SUPABASE) ---
def conectar_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except:
        return None

# --- CONEXÃO LOCAL (SQLITE - Para o Robô e Cache) ---
def conectar_local():
    return sqlite3.connect(NOME_BANCO_LOCAL)

def iniciar_banco():
    # Cria apenas as tabelas locais (Histórico, Carteira, P2P)
    con = conectar_local()
    cur = con.cursor()
    
    cur.execute('CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, email TEXT, prazo_dias INTEGER, valor_total REAL, cpm REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS promocoes (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, titulo TEXT, link TEXT, origem TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS carteira (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_email TEXT, data_compra TEXT, programa TEXT, quantidade INTEGER, custo_total REAL, cpm_medio REAL)')
    cur.execute('CREATE TABLE IF NOT EXISTS mercado_p2p (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, grupo_nome TEXT, programa TEXT, tipo TEXT, valor REAL, observacao TEXT)')
    
    con.commit()
    con.close()

# --- SEGURANÇA (HASH) ---
def criar_hash(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# --- FUNÇÕES DE USUÁRIO (AGORA NA NUVEM ☁️) ---

def registrar_usuario(nome, email, senha, telefone):
    supabase = conectar_supabase()
    if not supabase:
        return False, "Erro de conexão com o banco na nuvem. Verifique os Secrets."

    # Verifica se já existe
    try:
        res = supabase.table("usuarios").select("*").eq("email", email).execute()
        if len(res.data) > 0:
            return False, "E-mail já cadastrado."
            
        senha_hash = criar_hash(senha)
        
        dados = {
            "email": email, 
            "nome": nome, 
            "senha_hash": senha_hash, 
            "telefone": telefone,
            "plano": "Free"
        }
        
        supabase.table("usuarios").insert(dados).execute()
        return True, "Conta criada com sucesso na nuvem!"
        
    except Exception as e:
        return False, f"Erro ao criar conta: {str(e)}"

def autenticar_usuario(email, senha):
    supabase = conectar_supabase()
    if not supabase:
        return None
        
    senha_hash = criar_hash(senha)
    
    try:
        # Busca usuário na nuvem
        response = supabase.table("usuarios").select("nome, plano, status").eq("email", email).eq("senha_hash", senha_hash).execute()
        
        if len(response.data) > 0:
            user = response.data[0]
            if user['status'] == 'Ativo':
                return {"nome": user['nome'], "plano": user['plano']}
            else:
                return None # Usuário banido/inativo
        return None
    except:
        return None

# --- DEMAIS FUNÇÕES (MANTÉM LOCAL) ---

def ler_dados_historico():
    import pandas as pd
    con = conectar_local()
    try:
        df = pd.read_sql_query("SELECT * FROM historico ORDER BY data_hora ASC", con)
        if 'email' in df.columns: df = df.rename(columns={'email': 'programa'})
    except: df = pd.DataFrame()
    con.close()
    return df

def ler_carteira_usuario(email_usuario):
    import pandas as pd
    con = conectar_local()
    try:
        df = pd.read_sql_query("SELECT * FROM carteira WHERE usuario_email = ?", con, params=(email_usuario,))
    except: df = pd.DataFrame()
    con.close()
    return df

def adicionar_carteira(email, programa, qtd, custo):
    con = conectar_local()
    cpm = custo / (qtd / 1000)
    data = datetime.now().strftime("%Y-%m-%d")
    con.execute("INSERT INTO carteira (usuario_email, data_compra, programa, quantidade, custo_total, cpm_medio) VALUES (?, ?, ?, ?, ?, ?)", (email, data, programa, qtd, custo, cpm))
    con.commit(); con.close()

def remover_carteira(id_item):
    con = conectar_local()
    con.execute("DELETE FROM carteira WHERE id = ?", (id_item,))
    con.commit(); con.close()

# Funções do Robô
def salvar_cotacao(programa, dias, valor, cpm):
    con = conectar_local()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con.execute('INSERT INTO historico (data_hora, email, prazo_dias, valor_total, cpm) VALUES (?, ?, ?, ?, ?)', (agora, programa, dias, valor, cpm))
    con.commit(); con.close()

def pegar_ultimo_preco(programa):
    con = conectar_local()
    res = con.execute("SELECT cpm FROM historico WHERE email LIKE ? ORDER BY id DESC LIMIT 1", (f"%{programa}%",)).fetchone()
    con.close()
    return res[0] if res else 0.0

def salvar_promocao(titulo, link, origem):
    con = conectar_local()
    if not con.execute("SELECT id FROM promocoes WHERE link = ?", (link,)).fetchone():
        con.execute('INSERT INTO promocoes (data_hora, titulo, link, origem) VALUES (?, ?, ?, ?)', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), titulo, link, origem))
    con.commit(); con.close()

def adicionar_oferta_p2p(grupo, programa, tipo, valor, obs):
    con = conectar_local()
    con.execute('INSERT INTO mercado_p2p (data_hora, grupo_nome, programa, tipo, valor, observacao) VALUES (?, ?, ?, ?, ?, ?)',
                (datetime.now().strftime("%Y-%m-%d %H:%M"), grupo, programa, tipo, valor, obs))
    con.commit(); con.close()

def ler_p2p():
    con = conectar_local()
    import pandas as pd
    try: df = pd.read_sql_query("SELECT * FROM mercado_p2p ORDER BY id DESC", con)
    except: df = pd.DataFrame()
    con.close()
    return df
