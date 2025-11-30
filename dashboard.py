import streamlit as st
import pandas as pd
import sqlite3

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Milhas Pro 2.0", page_icon="🚀", layout="wide")
st.title("🚀 Centro de Comando de Milhas")

# --- FUNÇÕES DE CARREGAMENTO ---
def carregar_dados():
    try:
        conexao = sqlite3.connect("milhas.db")
        # Pega tudo, ordenado por data
        df = pd.read_sql_query("SELECT * FROM historico ORDER BY data_hora ASC", conexao)
        conexao.close()
        
        if not df.empty:
            df['data_hora'] = pd.to_datetime(df['data_hora'])
            # Garante que a coluna 'email' seja tratada como 'programa' (legado do codigo antigo)
            if 'email' in df.columns:
                df = df.rename(columns={'email': 'programa'})
        return df
    except:
        return pd.DataFrame()

def carregar_promocoes():
    try:
        conexao = sqlite3.connect("milhas.db")
        df = pd.read_sql_query("SELECT * FROM promocoes ORDER BY id DESC LIMIT 15", conexao)
        conexao.close()
        return df
    except:
        return pd.DataFrame()

df = carregar_dados()
df_promos = carregar_promocoes()

# --- KPI PRINCIPAL: VISÃO DE MERCADO ---
st.subheader("📊 Pulso do Mercado (Cotação 90 dias)")

if not df.empty:
    cols = st.columns(3)
    programas = ["Latam Pass", "Smiles (Gol)", "TudoAzul"] # Nomes exatos do banco
    
    for i, prog in enumerate(programas):
        # Filtra dados só desse programa
        dados_prog = df[df['programa'].str.contains(prog.split()[0], case=False)]
        
        with cols[i]:
            if not dados_prog.empty:
                # Pega o último preço e o penúltimo para comparar
                atual = dados_prog.iloc[-1]
                valor_atual = atual['cpm']
                
                delta = 0
                if len(dados_prog) > 1:
                    anterior = dados_prog.iloc[-2]
                    valor_anterior = anterior['cpm']
                    delta = valor_atual - valor_anterior
                
                st.metric(
                    label=prog,
                    value=f"R$ {valor_atual:.2f}",
                    delta=f"{delta:.2f}", # Mostra setinha verde ou vermelha
                    delta_color="normal"
                )
                st.caption(f"Atualizado: {atual['data_hora'].strftime('%d/%m %H:%M')}")
            else:
                st.metric(label=prog, value="--", delta="Sem dados")

st.divider()

# --- ÁREA DE ESTRATÉGIA (SIMULADOR) ---
col_sim, col_graf = st.columns([1, 2])

with col_sim:
    st.header("🧮 Simulador de Lucro")
    
    # Seletor de Estratégias Prontas
    estrategia = st.selectbox(
        "Escolha uma Estratégia Comum:",
        ["Personalizada", "Livelo 50% Off", "Livelo 52% Off (Clube)", "Esfera 50% Off", "Compra Bonificada 100%"]
    )
    
    # Preenche valores automaticamente baseado na escolha
    val_compra = 70.00
    desc = 0.0
    
    if estrategia == "Livelo 50% Off":
        val_compra = 70.00
        desc = 50.0
    elif estrategia == "Livelo 52% Off (Clube)":
        val_compra = 70.00
        desc = 52.0
    elif estrategia == "Esfera 50% Off":
        val_compra = 70.00
        desc = 50.0
    
    # Inputs Manuais
    custo_base = st.number_input("Preço Base do Milheiro (R$)", value=val_compra, step=1.0)
    desconto_compra = st.number_input("Desconto na Compra (%)", value=desc, step=1.0)
    bonus_transf = st.number_input("Bônus de Transferência (%)", value=100.0, step=10.0)
    
    # Matemática
    custo_pagou = custo_base * (1 - (desconto_compra/100))
    fator_bonus = 1 + (bonus_transf / 100)
    cpm_final = custo_pagou / fator_bonus
    
    st.info(f"💰 **Seu Custo CPM: R$ {cpm_final:.2f}**")
    
    # Comparativo com Venda Hoje (Pega a melhor venda entre os 3)
    if not df.empty:
        melhor_venda = df.iloc[-1]['cpm'] # Pega o ultimo registro geral (simplificado)
        lucro = melhor_venda - cpm_final
        margem = (lucro / cpm_final) * 100
        
        if margem > 10:
            st.success(f"Lucro Potencial: {margem:.1f}% (Venda a R$ {melhor_venda:.2f})")
        elif margem > 0:
            st.warning(f"Lucro Baixo: {margem:.1f}%")
        else:
            st.error(f"Prejuízo: {margem:.1f}%")

with col_graf:
    st.subheader("📈 Tendência de Preços (Comparativo)")
    if not df.empty:
        # Gráfico colorido por programa
        st.line_chart(df, x="data_hora", y="cpm", color="programa")
    else:
        st.write("Aguardando dados...")

# --- ABA DE PROMOÇÕES E DADOS ---
st.divider()
tab1, tab2 = st.tabs(["🔥 Radar de Promoções", "💾 Dados Brutos"])

with tab1:
    if not df_promos.empty:
        for index, row in df_promos.iterrows():
            st.markdown(f"**{row['data_hora'][5:10]}** | [{row['titulo']}]({row['link']}) _via {row['origem']}_")
    else:
        st.info("Nenhuma promoção recente detectada.")

with tab2:
    st.write("Histórico completo do banco de dados:")
    st.dataframe(df.sort_values(by='data_hora', ascending=False), hide_index=True)
    
    # Botão de Download para Excel/CSV
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Baixar Dados em CSV",
        data=csv,
        file_name='historico_milhas.csv',
        mime='text/csv',
    )
