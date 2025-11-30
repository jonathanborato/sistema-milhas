import sqlite3
from datetime import datetime
import hashlib

NOME_BANCO = "milhas.db"

def iniciar_banco():
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    
    # Tabelas Padrão
    cursor.execute('CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, email TEXT, prazo_dias INTEGER, valor_total REAL, cpm REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS promocoes (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, titulo TEXT, link TEXT, origem TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS carteira (id INTEGER PRIMARY KEY AUTOINCREMENT, data_compra TEXT, programa TEXT, quantidade INTEGER, custo_total REAL, cpm_medio REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, nome TEXT, senha_hash TEXT, data_cadastro TEXT)')
    
    # --- NOVA TABELA: MERCADO P2P (Telegram/WhatsApp) ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mercado_p2p (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            grupo_nome TEXT,
            programa TEXT,
            tipo TEXT, -- COMPRA ou VENDA
            valor REAL,
            observacao TEXT
        )
    ''')
    
    conexao.commit()
    conexao.close()

# --- FUNÇÕES P2P ---
def adicionar_oferta_p2p(grupo, programa, tipo, valor, obs):
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    cursor.execute('''
        INSERT INTO mercado_p2p (data_hora, grupo_nome, programa, tipo, valor, observacao)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (agora, grupo, programa, tipo, valor, obs))
    
    conexao.commit()
    conexao.close()

def ler_p2p():
    conexao = sqlite3.connect(NOME_BANCO)
    import pandas as pd
    try:
        df = pd.read_sql_query("SELECT * FROM mercado_p2p ORDER BY id DESC", conexao)
    except:
        df = pd.DataFrame()
    conexao.close()
    return df

# --- DEMAIS FUNÇÕES (Login, Carteira, Cotação) ---
def criar_hash(senha): return hashlib.sha256(senha.encode()).hexdigest()

def verificar_login(email, senha):
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    senha_teste = criar_hash(senha)
    cursor.execute("SELECT nome FROM usuarios WHERE email = ? AND senha_hash = ?", (email, senha_teste))
    resultado = cursor.fetchone()
    conexao.close()
    return resultado[0] if resultado else None

def cadastrar_usuario(email, nome, senha):
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    if cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone():
        conexao.close(); return False
    cursor.execute("INSERT INTO usuarios (email, nome, senha_hash, data_cadastro) VALUES (?, ?, ?, ?)", (email, nome, criar_hash(senha), datetime.now().strftime("%Y-%m-%d")))
    conexao.commit(); conexao.close(); return True

def salvar_cotacao(programa, dias, valor, cpm):
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    cursor.execute('INSERT INTO historico (data_hora, email, prazo_dias, valor_total, cpm) VALUES (?, ?, ?, ?, ?)', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), programa, dias, valor, cpm))
    conexao.commit(); conexao.close()

def pegar_ultimo_preco(programa):
    try:
        conexao = sqlite3.connect(NOME_BANCO)
        res = conexao.execute("SELECT cpm FROM historico WHERE email LIKE ? ORDER BY id DESC LIMIT 1", (f"%{programa}%",)).fetchone()
        conexao.close(); return res[0] if res else 0.0
    except: return 0.0

def adicionar_milhas(prog, qtd, custo):
    conexao = sqlite3.connect(NOME_BANCO)
    cpm = custo/(qtd/1000)
    conexao.execute('INSERT INTO carteira (data_compra, programa, quantidade, custo_total, cpm_medio) VALUES (?, ?, ?, ?, ?)', (datetime.now().strftime("%Y-%m-%d"), prog, qtd, custo, cpm))
    conexao.commit(); conexao.close()

def remover_item_carteira(id_item):
    conexao = sqlite3.connect(NOME_BANCO)
    conexao.execute('DELETE FROM carteira WHERE id = ?', (id_item,))
    conexao.commit(); conexao.close()

def ler_carteira():
    conexao = sqlite3.connect(NOME_BANCO)
    import pandas as pd
    try: df = pd.read_sql_query("SELECT * FROM carteira", conexao); conexao.close(); return df
    except: conexao.close(); return pd.DataFrame()
