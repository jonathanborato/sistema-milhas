import streamlit as st
import pandas as pd
import sqlite3

st.set_page_config(page_title="Milhas Intelligence", page_icon="✈️", layout="wide")
st.title("✈️ Painel de Inteligência de Milhas")

# --- FUNÇÕES DE DADOS ---
def carregar_dados():
    try:
        conexao = sqlite3.connect("milhas.db")
        df = pd.read_sql_query("SELECT * FROM historico", conexao)
        conexao.close()
        if not df.empty:
            df['data_hora'] = pd.to_datetime(df['data_hora'])
            df = df.sort_values(by='data_hora')
        return df
    except:
        return pd.DataFrame()

def carregar_promocoes():
    try:
        conexao = sqlite3.connect("milhas.db")
        # Pega as ultimas 20 promoções
        df = pd.read_sql_query("SELECT * FROM promocoes ORDER BY id DESC LIMIT 20", conexao)
        conexao.close()
        return df
    except:
        return pd.DataFrame()

# --- CARREGA DADOS ---
df_cotacoes = carregar_dados()
df_promos = carregar_promocoes()

# --- ABAS (TABS) ---
tab1, tab2 = st.tabs(["📊 Cotações de Venda", "🔥 Promoções de Compra"])

with tab1:
    # (AQUI VAI O CÓDIGO ANTIGO DO DASHBOARD - COPIE E COLE A LOGICA DE EXIBIÇÃO AQUI)
    if not df_cotacoes.empty:
        ultima = df_cotacoes.iloc[-1]
        st.metric("Venda Latam/Smiles (Média)", f"R$ {ultima['cpm']:.2f}")
        st.line_chart(df_cotacoes, x="data_hora", y="cpm")
    else:
        st.warning("Sem dados de cotação ainda.")

with tab2:
    st.header("Radar de Oportunidades")
    st.info("Aqui estão as promoções detectadas nos blogs parceiros.")
    
    if not df_promos.empty:
        for index, row in df_promos.iterrows():
            with st.expander(f"{row['data_hora'][5:10]} - {row['titulo']}"):
                st.write(f"**Fonte:** {row['origem']}")
                st.markdown(f"👉 [Clique para ler a promoção]({row['link']})")
    else:
        st.write("Nenhuma promoção encontrada hoje.")

# Botão Atualizar
if st.button('🔄 Atualizar'):
    st.rerun()
