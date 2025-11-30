import sqlite3
from datetime import datetime

# Nome do arquivo do banco de dados
NOME_BANCO = "milhas.db"

def iniciar_banco():
    """Cria a tabela se ela não existir"""
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    
    # Criamos uma tabela com: Data, Email, Prazo (dias), Valor Total e CPM
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
    conexao.commit()
    conexao.close()

def salvar_cotacao(email, dias, valor, cpm):
    """Guarda uma linha de cotação no banco"""
    conexao = sqlite3.connect(NOME_BANCO)
    cursor = conexao.cursor()
    
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute('''
        INSERT INTO historico (data_hora, email, prazo_dias, valor_total, cpm)
        VALUES (?, ?, ?, ?, ?)
    ''', (agora, email, dias, valor, cpm))
    
    conexao.commit()
    conexao.close()
    print(f"💾 Salvo no banco: {dias} dias | R$ {cpm:.2f}/milheiro")