import streamlit as st
import pandas as pd
import sqlite3
import time
import hashlib
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Milhas Pro System", page_icon="✈️", layout="wide")

# ==============================================================================
# 1. FUNÇÕES DE BANCO DE DADOS (INTERNAS)
# ==============================================================================
NOME_BANCO = "milhas.db"

def iniciar_banco():
    con = sqlite3.connect(NOME_BANCO)
    cur = con.cursor()
    # Cria todas as tabelas necessárias
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

def adicionar_oferta_p2p(grupo, programa, tipo, valor, obs):
    con = sqlite3.connect(NOME_BANCO)
    con.execute('INSERT INTO mercado_p2p (data_hora, grupo_nome, programa, tipo, valor, observacao) VALUES (?, ?, ?, ?, ?, ?)',
                (datetime.now().strftime("%Y-%m-%d %H:%M"), grupo,
