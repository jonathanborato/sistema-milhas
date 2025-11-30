import streamlit as st
import pandas as pd
import sqlite3
import banco # Importamos o banco atualizado

# Configuração da página
st.set_page_config(page_title="Milhas Pro 3.0 - Asset Management", page_icon="🏦", layout="wide")
st.title("🏦 Gestão de Patrimônio em Milhas")

# Garante que o banco está criado
banco.iniciar_banco()

# --- FUNÇÕES AUXILIARES ---
def carregar_cotacoes():
    try:
        conexao = sqlite3.connect("milhas.db")
        df = pd.read_sql_query("SELECT * FROM historico ORDER BY data_hora ASC", conexao)
        conexao.close()
        if not df.empty:
            df['data_hora'] = pd.to_datetime(df['data_hora'])
            if 'email' in df.columns: df = df.rename(columns={'email': 'programa'})
        return df
    except: return pd.DataFrame()

def pegar_preco_atual(programa, df_historico):
    """Pega o preço mais recente de um programa especifico"""
    if df_historico.empty: return 0.0
    
    # Filtra pelo nome (ex: Latam)
    filtro = df_historico[df_historico['programa'].str.contains(programa.split()[0], case=False, na=False)]
    if not filtro.empty:
        return filtro.iloc[-1]['cpm']
    return 0.0

# --- CARREGAMENTO ---
df_cotacoes = carregar_cotacoes()
df_carteira = banco.ler_carteira()

# --- MENU LATERAL DE NAVEGAÇÃO ---
menu = st.sidebar.radio("Navegação", ["Minha Carteira (Patrimônio)", "Análise de Mercado", "Promoções"])

# ==============================================================================
# ABA 1: MINHA CARTEIRA (O NOVO PODER)
# ==============================================================================
if menu == "Minha Carteira (Patrimônio)":
    st.header("💼 Seu Estoque de Milhas")
    
    # 1. Formulário para Adicionar Compras
    with st.expander("➕ Registrar Nova Compra de Milhas", expanded=False):
        c1, c2, c3 = st.columns(3)
        prog_input = c1.selectbox("Programa", ["Latam Pass", "Smiles", "TudoAzul", "Livelo", "Esfera"])
        qtd_input = c2.number_input("Quantidade de Milhas", min_value=1000, step=1000)
        custo_input = c3.number_input("Quanto você pagou? (R$ Total)", min_value=0.0, step=10.0)
        
        if st.button("💾 Salvar na Carteira"):
            banco.adicionar_milhas(prog_input, qtd_input, custo_input)
            st.success("Adicionado!")
            st.rerun()

    st.divider()

    # 2. Exibição da Carteira com Cotação em Tempo Real
    if not df_carteira.empty:
        # Vamos enriquecer a tabela com dados do mercado
        patrimonio_total = 0
        custo_total_carteira = 0
        
        # Lista para montar a tabela visual
        tabela_visual = []
        
        for index, row in df_carteira.iterrows():
            prog = row['programa']
            qtd = row['quantidade']
            custo = row['custo_total']
            cpm_pago = row['cpm_medio']
            
            # Busca quanto vale HOJE
            preco_mercado = pegar_preco_atual(prog, df_cotacoes)
            
            # Cálculos Financeiros
            valor_atual_venda = (qtd / 1000) * preco_mercado
            lucro_prejuizo = valor_atual_venda - custo
            margem = ((valor_atual_venda - custo) / custo) * 100 if custo > 0 else 0
            
            patrimonio_total += valor_atual_venda
            custo_total_carteira += custo
            
            tabela_visual.append({
                "ID": row['id'],
                "Programa": prog,
                "Milhas": f"{qtd:,.0f}",
                "CPM Pago": f"R$ {cpm_pago:.2f}",
                "CPM Venda (Hoje)": f"R$ {preco_mercado:.2f}",
                "Valor de Venda": f"R$ {valor_atual_venda:.2f}",
                "Lucro/Prejuízo": lucro_prejuizo, # Numérico para colorir depois
                "Margem": f"{margem:.1f}%"
            })
            
        df_visual = pd.DataFrame(tabela_visual)
        
        # KPIs do Topo
        k1, k2, k3 = st.columns(3)
        k1.metric("Patrimônio Total (Se vender hoje)", f"R$ {patrimonio_total:,.2f}")
        k2.metric("Custo de Aquisição", f"R$ {custo_total_carteira:,.2f}")
        
        lucro_total = patrimonio_total - custo_total_carteira
        k3.metric("Resultado Geral", f"R$ {lucro_total:,.2f}", delta=f"{(lucro_total/custo_total_carteira)*100:.1f}%" if custo_total_carteira else 0)
        
        st.divider()
        st.subheader("Detalhamento por Lote")
        
        # Mostra tabela colorida
        st.dataframe(
            df_visual.style.applymap(lambda x: 'color: green' if x > 0 else 'color: red', subset=['Lucro/Prejuízo']),
            use_container_width=True
        )
        
        # Botão para deletar
        st.caption("Para vender/remover um lote, veja o ID na tabela acima.")
        id_del = st.number_input("ID para remover", min_value=0, step=1)
        if st.button("🗑️ Remover Lote"):
            banco.remover_item_carteira(id_del)
            st.rerun()
            
    else:
        st.info("Sua carteira está vazia. Registre suas milhas acima para começar a gerenciar seu patrimônio.")

# ==============================================================================
# ABA 2: ANÁLISE DE MERCADO (O QUE JÁ TINHA ANTES)
# ==============================================================================
elif menu == "Análise de Mercado":
    st.header("📊 Pulso do Mercado (Cotação 90 dias)")
    
    # ... (Código simplificado da exibição de métricas que fizemos antes)
    if not df_cotacoes.empty:
        cols = st.columns(3)
        programas = ["Latam", "Smiles", "Azul"]
        for i, prog in enumerate(programas):
            dados_prog = df_cotacoes[df_cotacoes['programa'].str.contains(prog, case=False, na=False)]
            with cols[i]:
                if not dados_prog.empty:
                    atual = dados_prog.iloc[-1]['cpm']
                    st.metric(prog, f"R$ {atual:.2f}")
                    st.line_chart(dados_prog, x="data_hora", y="cpm")
                else:
                    st.metric(prog, "Sem dados")

# ==============================================================================
# ABA 3: PROMOÇÕES
# ==============================================================================
elif menu == "Promoções":
    st.header("🔥 Radar de Oportunidades")
    
    def carregar_promocoes():
        try:
            conexao = sqlite3.connect("milhas.db")
            return pd.read_sql_query("SELECT * FROM promocoes ORDER BY id DESC LIMIT 15", conexao)
        except: return pd.DataFrame()

    df_promos = carregar_promocoes()
    if not df_promos.empty:
        for index, row in df_promos.iterrows():
            st.markdown(f"**{row['data_hora'][5:10]}** | [{row['titulo']}]({row['link']})")
    else:
        st.info("Nenhuma promoção recente.")
