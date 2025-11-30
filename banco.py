import sqlite3
import hashlib
from datetime import datetime, timedelta

NOME_BANCO = "milhas.db"

# --- INFRAESTRUTURA ---
def conectar():
    return sqlite3.connect(NOME_BANCO)

def iniciar_banco():
    con = conectar()
    cur = con.cursor()
    
    # 1. Tabela de Clientes (SaaS)
    # Adicionamos 'plano' (Free/Pro) e 'status' (Ativo/Inativo)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            nome TEXT,
            senha_hash TEXT,
            telefone TEXT,
            plano TEXT DEFAULT 'Free', 
            status TEXT DEFAULT 'Ativo',
            data_cadastro TEXT
        )
    ''')

    # 2. Tabela de Cotações (Robô)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            email TEXT, -- Usado como 'Programa'
            prazo_dias INTEGER,
            valor_total REAL,
            cpm REAL
        )
    ''')

    # 3. Tabela de Carteira (Estoque do Cliente)
    # Adicionamos 'usuario_id' para saber de quem é a milha
    cur.execute('''
        CREATE TABLE IF NOT EXISTS carteira (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_email TEXT,
            data_compra TEXT,
            programa TEXT,
            quantidade INTEGER,
            custo_total REAL,
            cpm_medio REAL
        )
    ''')
    
    # 4. Tabela P2P e Promoções (Globais)
    cur.execute('CREATE TABLE IF NOT EXISTS promocoes (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, titulo TEXT, link TEXT, origem TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS mercado_p2p (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, grupo_nome TEXT, programa TEXT, tipo TEXT, valor REAL, observacao TEXT)')
    
    con.commit()
    con.close()

# --- SEGURANÇA E AUTH ---
def criar_hash(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def autenticar_usuario(email, senha):
    con = conectar()
    cur = con.cursor()
    senha_hash = criar_hash(senha)
    
    # Busca usuário ativo com essa senha
    cur.execute("SELECT nome, plano FROM usuarios WHERE email = ? AND senha_hash = ? AND status = 'Ativo'", (email, senha_hash))
    user = cur.fetchone()
    con.close()
    
    if user:
        return {"nome": user[0], "plano": user[1]}
    return None

def registrar_usuario(nome, email, senha, telefone):
    try:
        con = conectar()
        cur = con.cursor()
        
        # Verifica duplicidade
        if cur.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone():
            con.close()
            return False, "E-mail já cadastrado."
            
        senha_hash = criar_hash(senha)
        agora = datetime.now().strftime("%Y-%m-%d")
        
        cur.execute("""
            INSERT INTO usuarios (email, nome, senha_hash, telefone, plano, data_cadastro)
            VALUES (?, ?, ?, ?, 'Free', ?)
        """, (email, nome, senha_hash, telefone, agora))
        
        con.commit()
        con.close()
        return True, "Cadastro realizado com sucesso!"
    except Exception as e:
        return False, str(e)

# --- FUNÇÕES DE DADOS (GET/SET) ---
def ler_dados_historico():
    import pandas as pd
    con = conectar()
    try:
        df = pd.read_sql_query("SELECT * FROM historico ORDER BY data_hora ASC", con)
        # Corrige nome da coluna legado
        if 'email' in df.columns: df = df.rename(columns={'email': 'programa'})
    except:
        df = pd.DataFrame()
    con.close()
    return df

def ler_carteira_usuario(email_usuario):
    import pandas as pd
    con = conectar()
    try:
        # Só traz as milhas DESTE usuário
        df = pd.read_sql_query("SELECT * FROM carteira WHERE usuario_email = ?", con, params=(email_usuario,))
    except:
        df = pd.DataFrame()
    con.close()
    return df

def adicionar_carteira(email, programa, qtd, custo):
    con = conectar()
    cpm = custo / (qtd / 1000)
    data = datetime.now().strftime("%Y-%m-%d")
    con.execute("INSERT INTO carteira (usuario_email, data_compra, programa, quantidade, custo_total, cpm_medio) VALUES (?, ?, ?, ?, ?, ?)",
                (email, data, programa, qtd, custo, cpm))
    con.commit()
    con.close()

def remover_carteira(id_item):
    con = conectar()
    con.execute("DELETE FROM carteira WHERE id = ?", (id_item,))
    con.commit()
    con.close()

# Funções Legado para o Robô (Não remover senão o robô quebra)
def salvar_cotacao(programa, dias, valor, cpm):
    con = conectar()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con.execute('INSERT INTO historico (data_hora, email, prazo_dias, valor_total, cpm) VALUES (?, ?, ?, ?, ?)', (agora, programa, dias, valor, cpm))
    con.commit(); con.close()

def pegar_ultimo_preco(programa):
    # Função usada pelo cotador.py para saber se subiu ou desceu
    con = conectar()
    res = con.execute("SELECT cpm FROM historico WHERE email LIKE ? ORDER BY id DESC LIMIT 1", (f"%{programa}%",)).fetchone()
    con.close()
    return res[0] if res else 0.0

def salvar_promocao(titulo, link, origem):
    con = conectar()
    if not con.execute("SELECT id FROM promocoes WHERE link = ?", (link,)).fetchone():
        con.execute('INSERT INTO promocoes (data_hora, titulo, link, origem) VALUES (?, ?, ?, ?)', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), titulo, link, origem))
    con.commit(); con.close()
