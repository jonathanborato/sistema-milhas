import streamlit as st
import pandas as pd
import sqlite3
import banco
import time

# Configuração da página
st.set_page_config(page_title="Milhas Pro System", page_icon="✈️", layout="wide")

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
        st.image("https://cdn-icons-png.flaticon.com/512/723/723955.png", width=80)
        st.title("Milhas Pro System")
        st.markdown("### O seu Centro de Inteligência de Milhas Aéreas")
        
        # --- LOGIN ---
        email_login = st.text_input("E-mail")
        senha_login = st.text_input("Senha", type="password")
        
        if st.button("Acessar Sistema", type="primary"):
            # 1. Tenta Login Mestre (Secrets)
            # Verifica se existem segredos configurados e se batem
            usuario_mestre = False
            try:
                if email_login == st.secrets["admin"]["email"] and senha_login == st.secrets["admin"]["senha"]:
                    st.session_state['logado'] = True
                    st.session_state['usuario_nome'] = st.secrets["admin"]["nome"]
                    usuario_mestre = True
            except:
                pass # Se não tiver secrets configurado, ignora
            
            # 2. Se não for mestre, tenta Banco de Dados (Para rodar local)
            if not usuario_mestre:
                nome_db = banco.verificar_login(email_login, senha_login)
                if nome_db:
                    st.session_state['logado'] = True
                    st.session_state['usuario_nome'] = nome_db
                    usuario_mestre = True
            
            # Resultado Final
            if usuario_mestre:
                st.success(f"Bem-vindo, {st.session_state['usuario_nome']}!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Acesso Negado. Verifique e-mail e senha.")

        # Aviso sobre cadastro na nuvem
        with st.expander("ℹ️ Sobre Cadastros"):
            st.info("Para acesso permanente na versão Cloud, configure o usuário Admin nos 'Secrets' do Streamlit.")
            
# ==============================================================================
# FUNÇÃO 2: O SISTEMA COMPLETO (ÁREA LOGADA)
# ==============================================================================
def sistema_principal():
    # --- BARRA LATERAL COM LOGO, USER E MENU ---
    with st.sidebar:
        # LOGOMARCA AQUI
        st.image("https://cdn-icons-png.flaticon.com/512/723/723955.png", width=100)
        
        st.write(f"👤 Olá, **{st.session_state['usuario_nome']}**")
        
        if st.button("Sair / Logout"):
            st.session_state['logado'] = False
            st.rerun()
        st.divider()
        
        # Menu de Navegação na Lateral
        menu = st.radio("Navegação", ["Minha Carteira", "Análise de Mercado", "Promoções"])
        st.divider()
        st.caption("Milhas Pro System v3.0")
    
    # --- TÍTULO DA PÁGINA ---
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

    # Carrega dados
    df_cotacoes = carregar_cotacoes()
    df_carteira = banco.ler_carteira()

    # ==========================================================================
    # ABA: MINHA CARTEIRA
    # ==========================================================================
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
                
                # Cálculos
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
            
            # KPIs Financeiros
            k1, k2, k3 = st.columns(3)
            k1.metric("Patrimônio Total", f"R$ {patrimonio_total:,.2f}")
            k2.metric("Custo Total", f"R$ {custo_total_carteira:,.2f}")
            lucro_total = patrimonio_total - custo_total_carteira
            k3.metric("Resultado", f"R$ {lucro_total:,.2f}", delta=f"{(lucro_total/custo_total_carteira)*100:.1f}%" if custo_total_carteira else 0)
            
            # Tabela Colorida
            st.dataframe(df_visual.style.applymap(lambda x: 'color: green' if x > 0 else 'color: red', subset=['Lucro']), use_container_width=True)
            
            # Remoção
            id_del = st.number_input("ID para remover", min_value=0, step=1)
            if st.button("🗑️ Remover Lote"):
                banco.remover_item_carteira(id_del)
                st.rerun()
        else:
            st.info("Carteira vazia. Adicione suas milhas acima!")

    # ==========================================================================
    # ABA: ANÁLISE DE MERCADO
    # ==========================================================================
    elif menu == "Análise de Mercado":
        st.header("📊 Cotações de Venda (Hotmilhas - 90d)")
        if not df_cotacoes.empty:
            cols = st.columns(3)
            programas = ["Latam", "Smiles", "Azul"]
            for i, prog in enumerate(programas):
                dados_prog = df_cotacoes[df_cotacoes['programa'].str.contains(prog, case=False, na=False)]
                with cols[i]:
                    if not dados_prog.empty:
                        atual = dados_prog.iloc[-1]['cpm']
                        
                        # Cálculo de Variação
                        delta = 0
                        if len(dados_prog) > 1:
                            anterior = dados_prog.iloc[-2]['cpm']
                            delta = atual - anterior
                            
                        st.metric(prog, f"R$ {atual:.2f}", delta=f"{delta:.2f}")
                        st.line_chart(dados_prog, x="data_hora", y="cpm")
                    else:
                        st.metric(prog, "Sem dados")
        else:
            st.warning("Aguardando o robô rodar pela primeira vez...")

    # ==========================================================================
    # ABA: PROMOÇÕES
    # ==========================================================================
    elif menu == "Promoções":
        st.header("🔥 Radar de Promoções (Blogs)")
        def carregar_promocoes():
            try:
                conexao = sqlite3.connect("milhas.db")
                return pd.read_sql_query("SELECT * FROM promocoes ORDER BY id DESC LIMIT 15", conexao)
            except: return pd.DataFrame()

        df_promos = carregar_promocoes()
        if not df_promos.empty:
            for index, row in df_promos.iterrows():
                st.markdown(f"**{row['data_hora'][5:10]}** | [{row['titulo']}]({row['link']}) _via {row['origem']}_")
        else:
            st.info("Nenhuma promoção recente detectada.")

# ==============================================================================
# CONTROLE PRINCIPAL (MAIN)
# ==============================================================================
if st.session_state['logado']:
    sistema_principal()
else:
    tela_login()
