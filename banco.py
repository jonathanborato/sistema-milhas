import sqlite3
from datetime import datetime
import os

NOME_BANCO = "milhas.db"

def iniciar_banco():
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    
    # Tabela Histórico (Cotações)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            email TEXT,
            prazo_dias INTEGER,
            valor_total REAL,
            cpm REAL
        )
    ''')
    
    # Tabela Promoções
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promocoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            titulo TEXT,
            link TEXT,
            origem TEXT
        )
    ''')
    
    # --- NOVA TABELA: CARTEIRA (SEU ESTOQUE) ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS carteira (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_compra TEXT,
            programa TEXT,
            quantidade INTEGER,
            custo_total REAL,
            cpm_medio REAL
        )
    ''')
    
    conexao.commit()
    conexao.close()

# --- FUNÇÕES DE LEITURA E ESCRITA ---

def salvar_cotacao(programa, dias, valor, cpm):
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO historico (data_hora, email, prazo_dias, valor_total, cpm) VALUES (?, ?, ?, ?, ?)', (agora, programa, dias, valor, cpm))
    conexao.commit()
    conexao.close()

def salvar_promocao(titulo, link, origem):
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("SELECT id FROM promocoes WHERE link = ?", (link,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO promocoes (data_hora, titulo, link, origem) VALUES (?, ?, ?, ?)', (agora, titulo, link, origem))
    conexao.commit()
    conexao.close()

def pegar_ultimo_preco(programa):
    try:
        conexao = sqlite3.connect(NOME_BANCO)
        cursor = conexao.cursor()
        cursor.execute("SELECT cpm FROM historico WHERE email LIKE ? ORDER BY id DESC LIMIT 1", (f"%{programa}%",))
        resultado = cursor.fetchone()
        conexao.close()
        return resultado[0] if resultado else 0.0
    except:
        return 0.0

# --- FUNÇÕES DA CARTEIRA ---

def adicionar_milhas(programa, qtd, custo):
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    agora = datetime.now().strftime("%Y-%m-%d")
    cpm = custo / (qtd / 1000)
    cursor.execute('INSERT INTO carteira (data_compra, programa, quantidade, custo_total, cpm_medio) VALUES (?, ?, ?, ?, ?)', 
                   (agora, programa, qtd, custo, cpm))
    conexao.commit()
    conexao.close()

def remover_item_carteira(id_item):
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    cursor.execute('DELETE FROM carteira WHERE id = ?', (id_item,))
    conexao.commit()
    conexao.close()

def ler_carteira():
    conexao = sqlite3.connect(NOME_BANCO)
    import pandas as pd
    try:
        df = pd.read_sql_query("SELECT * FROM carteira", conexao)
    except:
        df = pd.DataFrame()
    conexao.close()
    return df
