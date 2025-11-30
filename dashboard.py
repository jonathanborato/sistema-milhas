import streamlit as st
import pandas as pd
import sqlite3
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Milhas Intelligence",
    page_icon="✈️",
    layout="wide"
)

# Título Principal
st.title("✈️ Painel de Inteligência de Milhas")
st.markdown("---")

# --- CONEXÃO COM O BANCO DE DADOS ---
def carregar_dados():
    try:
        conexao = sqlite3.connect("milhas.db")
        
        query_check = "SELECT name FROM sqlite_master WHERE type='table' AND name='historico';"
        tabela_existe = pd.read_sql_query(query_check, conexao)
        
        if tabela_existe.empty:
            conexao.close()
            return pd.DataFrame()
            
        df = pd.read_sql_query("SELECT * FROM historico", conexao)
        conexao.close()
        
        if not df.empty:
            df['data_hora'] = pd.to_datetime(df['data_hora'])
            df = df.sort_values(by='data_hora')
        return df
    except Exception as e:
        st.error(f"Erro ao ler banco: {e}")
        return pd.DataFrame()

# Carrega os dados na memória
df = carregar_dados()

if df.empty:
    st.warning("⚠️ Ainda não há dados de cotação.")
    st.info("👉 Dica: Rode o arquivo 'cotador.py' no terminal para buscar os primeiros preços.")
    if st.button("Já rodei, recarregar página"):
        st.rerun()
    st.stop()

# --- BARRA LATERAL (CALCULADORA DE LUCRO) ---
with st.sidebar:
    st.header("🧮 Calculadora de Oportunidade")
    st.write("Simule uma compra de pontos:")
    
    custo_livelo = st.number_input("Preço Compra (Livelo/Esfera)", value=35.00, step=0.50)
    bonus_transf = st.number_input("Bônus Transferência (%)", value=100, step=10)
    
    fator_bonus = 1 + (bonus_transf / 100)
    cpm_custo = custo_livelo / fator_bonus
    
    st.divider()
    st.metric(label="💰 Seu Custo Final (CPM)", value=f"R$ {cpm_custo:.2f}")
    
    if cpm_custo < 17.00:
        st.success("Custo excelente!")
    elif cpm_custo > 22.00:
        st.error("Custo muito alto!")

# --- CORPO PRINCIPAL DO DASHBOARD ---

ultima_cotacao = df.iloc[-1]
preco_venda_atual = ultima_cotacao['cpm']
data_atualizacao = ultima_cotacao['data_hora'].strftime("%d/%m às %H:%M")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Preço de Venda (Hoje)", f"R$ {preco_venda_atual:.2f}")
    st.caption(f"Última atualização: {data_atualizacao}")

with col2:
    lucro_milheiro = preco_venda_atual - cpm_custo
    margem = (lucro_milheiro / cpm_custo) * 100
    
    st.metric(
        "Lucro Estimado / Milheiro", 
        f"R$ {lucro_milheiro:.2f}", 
        delta=f"{margem:.1f}%"
    )

with col3:
    if margem > 15:
        st.success("✅ COMPRAR AGORA! (Lucro Alto)")
    elif margem > 0:
        st.warning("⚠️ Lucro Baixo (Aguardar)")
    else:
        st.error("❌ PREJUÍZO (Não faça nada)")

st.divider()

# --- GRÁFICOS ---
col_graf1, col_graf2 = st.columns([2, 1])

with col_graf1:
    st.subheader("📈 Tendência do Preço")
    st.line_chart(df, x="data_hora", y="cpm")

with col_graf2:
    st.subheader("📋 Histórico Recente")
    st.dataframe(
        df.tail(10)[['data_hora', 'prazo_dias', 'cpm']].sort_values(by='data_hora', ascending=False), 
        hide_index=True
    )

if st.button('🔄 Atualizar Dados'):
    st.rerun()