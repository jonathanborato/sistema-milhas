import sqlite3
from datetime import datetime
import hashlib # Para criptografar a senha

NOME_BANCO = "milhas.db"

def iniciar_banco():
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    
    # Tabelas existentes
    cursor.execute('CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, email TEXT, prazo_dias INTEGER, valor_total REAL, cpm REAL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS promocoes (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, titulo TEXT, link TEXT, origem TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS carteira (id INTEGER PRIMARY KEY AUTOINCREMENT, data_compra TEXT, programa TEXT, quantidade INTEGER, custo_total REAL, cpm_medio REAL)')
    
    # --- NOVA TABELA: USUÁRIOS ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            nome TEXT,
            senha_hash TEXT,
            data_cadastro TEXT
        )
    ''')
    
    conexao.commit()
    conexao.close()

# --- FUNÇÕES DE SEGURANÇA ---
def criar_hash(senha):
    """Transforma '123456' em um código secreto ilegível"""
    return hashlib.sha256(senha.encode()).hexdigest()

def cadastrar_usuario(email, nome, senha):
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    
    # Verifica se já existe
    cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
    if cursor.fetchone():
        conexao.close()
        return False # Usuário já existe
    
    senha_secreta = criar_hash(senha)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("INSERT INTO usuarios (email, nome, senha_hash, data_cadastro) VALUES (?, ?, ?, ?)", 
                   (email, nome, senha_secreta, agora))
    conexao.commit()
    conexao.close()
    return True

def verificar_login(email, senha):
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    
    senha_teste = criar_hash(senha)
    
    cursor.execute("SELECT nome FROM usuarios WHERE email = ? AND senha_hash = ?", (email, senha_teste))
    resultado = cursor.fetchone()
    conexao.close()
    
    if resultado:
        return resultado[0] # Retorna o nome do usuário
    return None # Login falhou

# --- FUNÇÕES ANTIGAS (MANTIDAS) ---
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
    except: return 0.0

def adicionar_milhas(programa, qtd, custo):
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    agora = datetime.now().strftime("%Y-%m-%d")
    cpm = custo / (qtd / 1000)
    cursor.execute('INSERT INTO carteira (data_compra, programa, quantidade, custo_total, cpm_medio) VALUES (?, ?, ?, ?, ?)', (agora, programa, qtd, custo, cpm))
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
    try: df = pd.read_sql_query("SELECT * FROM carteira", conexao)
    except: df = pd.DataFrame()
    conexao.close()
    return df
