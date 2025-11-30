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
# FUNÇÃO 1: TELA DE LOGIN / CADASTRO (CORRIGIDA)
# ==============================================================================
def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.image("https://cdn-icons-png.flaticon.com/512/723/723955.png", width=80)
        st.title("Milhas Pro System")
        st.markdown("### O seu Centro de Inteligência de Milhas Aéreas")
        
        # AQUI ESTÁ A CORREÇÃO: Voltamos com as ABAS
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Criar Conta"])
        
        # --- ABA 1: LOGIN ---
        with tab_login:
            email_login = st.text_input("E-mail")
            senha_login = st.text_input("Senha", type="password")
            
            if st.button("Acessar Sistema", type="primary"):
                usuario_encontrado = False
                
                # 1. Tenta Login Mestre (Secrets do Streamlit Cloud)
                try:
                    if email_login == st.secrets["admin"]["email"] and senha_login == st.secrets["admin"]["senha"]:
                        st.session_state['logado'] = True
                        st.session_state['usuario_nome'] = st.secrets["admin"]["nome"]
                        usuario_encontrado = True
                except:
                    pass
                
                # 2. Se não for mestre, tenta Banco de Dados Local
                if not usuario_encontrado:
                    nome_db = banco.verificar_login(email_login, senha_login)
                    if nome_db:
                        st.session_state['logado'] = True
                        st.session_state['usuario_nome'] = nome_db
                        usuario_encontrado = True
                
                # Resultado
                if usuario_encontrado:
                    st.success(f"Bem-vindo, {st.session_state['usuario_nome']}!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("E-mail ou senha incorretos.")

        # --- ABA 2: CADASTRO (VOLTOU!) ---
        with tab_cadastro:
            st.warning("⚠️ O cadastro salva o usuário no banco atual. Se o site reiniciar na nuvem (plano grátis), o cadastro pode ser resetado. Para acesso permanente, use o Login Admin configurado nos Secrets.")
            
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
                        st.success("Conta criada! Vá na aba 'Entrar' e faça login.")
                    else:
                        st.error("Este e-mail já está cadastrado.")

# ==============================================================================
# FUNÇÃO 2: O SISTEMA COMPLETO (ÁREA LOGADA)
# ==============================================================================
def sistema_principal():
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/723/723955.png", width=100)
        st.write(f"👤 Olá, **{st.session_state['usuario_nome']}**")
        
        if st.button("Sair / Logout"):
            st.session_state['logado'] = False
            st.rerun()
        st.divider()
        
        # Menu de Navegação na Lateral
        menu = st.radio("Navegação", ["Minha Carteira", "Análise de Mercado", "Mercado P2P (Grupos)", "Promoções"])
        st.divider()
        st.caption("Milhas Pro System v3.1")
    
    st.title("🏦 Gestão de Patrimônio em Milhas")

    # --- FUNÇÕES DE CARREGAMENTO ---
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

    # ==========================================================================
    # ABA: MINHA CARTEIRA
    # ==========================================================================
    if menu == "Minha Carteira":
        st.header("💼 Seu Estoque de Milhas")
        with st.expander("➕ Registrar Nova Compra", expanded=False):
            c1, c2, c3 = st.columns(3)
            prog_input = c1.selectbox("Programa", ["Latam Pass", "Smiles", "TudoAzul", "Livelo", "Esfera"])
            qtd_input = c2.number_input("Quantidade", min_value=1000, step=1000)
            custo_
