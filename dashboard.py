import streamlit as st
import pandas as pd
import sqlite3
import banco
import time

# Configuração da página
st.set_page_config(page_title="Milhas Pro System", page_icon="🔐", layout="wide")

# Garante banco iniciado
banco.iniciar_banco()

# --- GESTÃO DE SESSÃO (LOGIN) ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
    st.session_state['usuario_nome'] = ""

# ==============================================================================
# FUNÇÃO 1: TELA DE LOGIN / CADASTRO
# ==============================================================================
def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("✈️ Milhas Pro System")
        st.markdown("### O seu Centro de Inteligência de Milhas Aéreas")
        
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Criar Conta"])
        
        with tab_login:
            email_login = st.text_input("E-mail")
            senha_login = st.text_input("Senha", type="password")
            
            if st.button("Acessar Sistema", type="primary"):
                nome_usuario = banco.verificar_login(email_login, senha_login)
                if nome_usuario:
                    st.session_state['logado'] = True
                    st.session_state['usuario_nome'] = nome_usuario
                    st.success(f"Bem-vindo, {nome_usuario}!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("E-mail ou senha incorretos.")

        with tab_cadastro:
            st.warning("⚠️ Área de novos membros")
            novo_nome = st.text_input("Seu Nome Completo")
            novo_email = st.text_input("Seu Melhor E-mail")
            nova_senha = st.text_input("Crie uma Senha", type="password")
            confirma_senha = st.text_input("Confirme a Senha", type="password")
            
            if st.button("Cadastrar"):
                if nova_senha != confirma_senha:
                    st.error("As senhas não coincidem!")
                elif len(nova_senha) < 4:
                    st.error("A senha deve ter pelo menos 4 caracteres.")
                else:
                    sucesso = banco.cadastrar_usuario(novo_email, novo_nome, nova_senha)
                    if sucesso:
                        st.success("Conta criada com sucesso! Faça login na aba ao lado.")
                    else:
                        st.error("Este e-mail já está cadastrado.")

# ==============================================================================
# FUNÇÃO 2: O SISTEMA COMPLETO (ÁREA LOGADA)
# ==============================================================================
def sistema_principal():
    # --- BARRA LATERAL COM LOGOUT ---
    with st.sidebar:
        st.write(f"👤 Olá, **{st.session_state['usuario_nome']}**")
        if st.button("Sair / Logout"):
            st.session_state['logado'] = False
            st.rerun()
        st.divider()
    
    # --- AQUI COMEÇA O SEU SISTEMA ORIGINAL (COPIADO E COLADO) ---
    st.title("🏦 Gestão de Patrimônio em Milhas")

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
        if df_historico.empty: return 0.0
        filtro = df_historico[df_historico['programa'].str.contains(programa.split()[0], case=False, na=False)]
        if not filtro.empty:
            return filtro.iloc[-1]['cpm']
        return 0.0

    df_cotacoes = carregar_cotacoes()
    df_carteira = banco.ler_carteira()

    # MENU DE NAVEGAÇÃO
    menu = st.sidebar.radio("Navegação", ["Minha Carteira", "Análise de Mercado", "Promoções"])

    # ABA: CARTEIRA
    if menu == "Minha Carteira":
        st.header("💼 Seu Estoque de Milhas")
        with st.expander("➕ Registrar Nova Compra", expanded=False):
            c1, c2, c3 = st.columns(3)
            prog_input = c1.selectbox("Programa", ["Latam Pass", "Smiles", "TudoAzul", "Livelo", "Esfera"])
            qtd_input = c2.number_input("Quantidade", min_value=1000, step=1000)
            custo_input = c3.number_input("Custo Total (R$)", min_value=0.0, step=10.0)
            
            if st.button("Salvar na Carteira"):
                banco.adicionar_milhas(prog_input, qtd_input, custo_input)
                st.success("Adicionado!")
                st.rerun()

        st.divider()

        if not df_carteira.empty:
            patrimonio_total = 0
            custo_total_carteira = 0
            tabela_visual = []
            
            for index, row in df_carteira.iterrows():
                prog = row['programa']
                qtd = row['quantidade']
                custo = row['custo_total']
                cpm_pago = row['cpm_medio']
                preco_mercado = pegar_preco_atual(prog, df_cotacoes)
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
                    "Valor Venda": f"R$ {valor_atual_venda:.2f}",
                    "Lucro": lucro_prejuizo,
                    "Margem": f"{margem:.1f}%"
                })
            
            df_visual = pd.DataFrame(tabela_visual)
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Patrimônio Total", f"R$ {patrimonio_total:,.2f}")
            k2.metric("Custo Total", f"R$ {custo_total_carteira:,.2f}")
            lucro_total = patrimonio_total - custo_total_carteira
            k3.metric("Resultado", f"R$ {lucro_total:,.2f}", delta=f"{(lucro_total/custo_total_carteira)*100:.1f}%" if custo_total_carteira else 0)
            
            st.dataframe(df_visual.style.applymap(lambda x: 'color: green' if x > 0 else 'color: red', subset=['Lucro']), use_container_width=True)
            
            id_del = st.number_input("ID para remover", min_value=0, step=1)
            if st.button("🗑️ Remover"):
                banco.remover_item_carteira(id_del)
                st.rerun()
        else:
            st.info("Carteira vazia.")

    # ABA: MERCADO
    elif menu == "Análise de Mercado":
        st.header("📊 Cotações (Hotmilhas)")
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

    # ABA: PROMOÇÕES
    elif menu == "Promoções":
        st.header("🔥 Radar de Promoções")
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

# ==============================================================================
# CONTROLE PRINCIPAL (MAIN)
# ==============================================================================
if st.session_state['logado']:
    sistema_principal()
else:
    tela_login()
