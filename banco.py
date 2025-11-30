import sqlite3
from datetime import datetime
import os

NOME_BANCO = "milhas.db"

def iniciar_banco():
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    
    # Tabela de Preços (Venda)
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
    
    # --- NOVA TABELA: PROMOÇÕES (COMPRA) ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promocoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            titulo TEXT,
            link TEXT,
            origem TEXT
        )
    ''')
    
    conexao.commit()
    conexao.close()

def salvar_cotacao(programa, dias, valor, cpm):
    # (Mantém igual ao anterior, sem mudanças aqui)
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO historico (data_hora, email, prazo_dias, valor_total, cpm) VALUES (?, ?, ?, ?, ?)', (agora, programa, dias, valor, cpm))
    conexao.commit()
    conexao.close()

def salvar_promocao(titulo, link, origem):
    """Salva uma nova promoção encontrada"""
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Verifica se já não salvamos essa notícia hoje para não duplicar
    cursor.execute("SELECT id FROM promocoes WHERE link = ?", (link,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO promocoes (data_hora, titulo, link, origem) VALUES (?, ?, ?, ?)', (agora, titulo, link, origem))
        print(f"🔥 Nova Promoção Salva: {titulo}")
    
    conexao.commit()
    conexao.close()
