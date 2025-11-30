import streamlit as st
import pandas as pd
import banco # Importa nosso backend limpo
import time

# --- CONFIGURAÇÃO VISUAL (PRIMEIRA LINHA) ---
st.set_page_config(
    page_title="MilhasPro | Intelligence",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializa Backend
banco.iniciar_banco()

# --- CSS PERSONALIZADO (PARA FICAR BONITO) ---
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #ff4b4b;}
    .big-font {font-size: 20px !important;}
    div.stButton > button:first-child {width: 100%;}
</style>
""", unsafe_allow_html=True)

# --- GESTÃO DE SESSÃO ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

# ==============================================================================
# VIEW 1: LANDING PAGE & LOGIN (A PORTA DE ENTRADA)
# ==============================================================================
def tela_login():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    
    with c2:
        st.markdown("<div style='text-align: center; margin-top: 50px;'><h1>✈️ MilhasPro</h1><p>Sistema Profissional de Gestão de Ativos Aéreos</p></div>", unsafe_allow_html=True)
        
        tab_entrar, tab_criar = st.tabs(["🔒 Acessar Painel", "✨ Criar Nova Conta"])
        
        with tab_entrar:
            email = st.text_input("E-mail Profissional", placeholder="seu@email.com")
            senha = st.text_input("Sua Senha", type="password")
            
            if st.button("ENTRAR NO SISTEMA", type="primary"):
                # 1. Backdoor do Admin (Secrets)
                try:
                    if email == st.secrets["admin"]["email"] and senha == st.secrets["admin"]["senha"]:
                        st.session_state['user'] = {"nome": st.secrets["admin"]["nome"], "email": email, "plano": "Admin"}
                        st.rerun()
                except: pass
                
                # 2. Login Real
                usuario = banco.autenticar_usuario(email, senha)
                if usuario:
                    st.session_state['user'] = {"nome": usuario['nome'], "email": email, "plano": usuario['plano']}
                    st.toast("Login realizado com sucesso!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")
        
        with tab_criar:
            st.info("🚀 Comece a gerenciar suas milhas hoje.")
            nome = st.text_input("Nome Completo")
            cad_email = st.text_input("E-mail para cadastro")
            cad_tel = st.text_input("WhatsApp")
            cad_senha = st.text_input("Defina uma senha", type="password")
            
            if st.button("CRIAR CONTA GRATUITA"):
                if len(cad_senha) < 4:
                    st.warning("Senha muito curta.")
                else:
                    ok, msg = banco.registrar_usuario(nome, cad_email, cad_senha, cad_tel)
                    if ok:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(msg)

# ==============================================================================
# VIEW 2: O SISTEMA (DASHBOARD)
# ==============================================================================
def sistema_logado():
    user = st.session_state['user']
    
    # --- SIDEBAR PROFISSIONAL ---
    with st.sidebar:
        st.title("✈️ MilhasPro")
        st.write(f"Bem-vindo, **{user['nome']}**")
        
        # Badge do Plano
        if user['plano'] == "Admin":
            st.success("👑 MODO ADMIN")
        elif user['plano'] == "Pro":
            st.success("⭐ PLANO PRO")
        else:
            st.info("🔹 PLANO FREE")
            st.caption("Faça upgrade para ver análises P2P.")
            
        st.markdown("---")
        menu = st.radio("Menu Principal", ["Dashboard Geral", "Minha Carteira", "Mercado & Cotações", "Promoções"])
        
        st.markdown("---")
        if st.button("Sair"):
            st.session_state['user'] = None
            st.rerun()

    # --- CARREGAMENTO DE DADOS ---
    df_cotacoes = banco.ler_dados_historico()
    
    # --- PÁGINA: DASHBOARD GERAL ---
    if menu == "Dashboard Geral":
        st.header(f"Olá, {user['nome'].split()[0]}")
        
        # Últimas Cotações (Resumo)
        if not df_cotacoes.empty:
            k1, k2, k3 = st.columns(3)
            # Pega as ultimas de cada programa
            for i, p in enumerate(["Latam", "Smiles", "Azul"]):
                d = df_cotacoes[df_cotacoes['programa'].str.contains(p, case=False, na=False)]
                col = [k1, k2, k3][i]
                if not d.empty:
                    atual = d.iloc[-1]['cpm']
                    delta = atual - d.iloc[-2]['cpm'] if len(d) > 1 else 0
                    col.metric(f"Venda {p}", f"R$ {atual:.2f}", f"{delta:.2f}")
                else:
                    col.metric(p, "--")
        
        st.markdown("### 📈 Visão Rápida de Tendência")
        if not df_cotacoes.empty:
            st.line_chart(df_cotacoes, x="data_hora", y="cpm", color="programa")
        else:
            st.warning("Aguardando dados do Robô. Certifique-se que o GitHub Actions rodou.")

    # --- PÁGINA: CARTEIRA ---
    elif menu == "Minha Carteira":
        st.header("💼 Gestão de Ativos")
        
        # Área de Adicionar
        with st.expander("➕ Adicionar Novo Lote de Milhas", expanded=True):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
            prog = c1.selectbox("Programa", ["Latam Pass", "Smiles", "TudoAzul", "Livelo", "Esfera"])
            qtd = c2.number_input("Qtd Milhas", 1000, step=1000)
            custo = c3.number_input("Custo Total (R$)", 0.0, step=10.0)
            c4.write("")
            c4.write("")
            if c4.button("Salvar"):
                banco.adicionar_carteira(user['email'], prog, qtd, custo)
                st.toast("Lote adicionado!", icon="💾")
                time.sleep(0.5)
                st.rerun()

        # Exibição da Tabela
        df_cart = banco.ler_carteira_usuario(user['email'])
        
        if not df_cart.empty:
            st.markdown("### Seu Estoque Atual")
            
            # Tabela Visual
            view_data = []
            total_investido = 0
            
            for _, row in df_cart.iterrows():
                # Tenta pegar preço de mercado
                filtro = df_cotacoes[df_cotacoes['programa'].str.contains(row['programa'].split()[0], case=False, na=False)]
                preco_mercado = filtro.iloc[-1]['cpm'] if not filtro.empty else 0.0
                
                val_mercado = (row['quantidade']/1000) * preco_mercado
                lucro = val_mercado - row['custo_total']
                margem = (lucro / row['custo_total']) * 100 if row['custo_total'] > 0 else 0
                
                total_investido += row['custo_total']
                
                view_data.append({
                    "ID": row['id'],
                    "Programa": row['programa'],
                    "Qtd": f"{row['quantidade']:,.0f}",
                    "CPM Médio": f"R$ {row['cpm_medio']:.2f}",
                    "Valor Mercado": f"R$ {val_mercado:,.2f}",
                    "Lucro (Est.)": lucro,
                    "Margem": f"{margem:.1f}%"
                })
            
            df_view = pd.DataFrame(view_data)
            
            # Cards de Resumo da Carteira
            rc1, rc2 = st.columns(2)
            rc1.metric("Total Investido", f"R$ {total_investido:,.2f}")
            rc2.info("Dica: Venda lotes com Margem acima de 15%")

            # Tabela com Cores
            st.dataframe(
                df_view.style.background_gradient(cmap='RdYlGn', subset=['Lucro (Est.)']),
                use_container_width=True
            )
            
            # Remover Lote
            st.markdown("---")
            col_del, _ = st.columns([1, 3])
            id_del = col_del.number_input("ID para excluir", min_value=0)
            if col_del.button("Excluir Lote Selecionado"):
                banco.remover_carteira(id_del)
                st.rerun()
        else:
            st.info("Sua carteira está vazia. Adicione seus ativos acima.")

    # --- PÁGINA: MERCADO ---
    elif menu == "Mercado & Cotações":
        st.header("📊 Análise de Mercado (Hotmilhas)")
        
        if df_cotacoes.empty:
            st.warning("Sem dados. O robô precisa rodar pelo menos uma vez.")
        else:
            # Filtros
            selecao = st.multiselect("Filtrar Programas", df_cotacoes['programa'].unique(), default=df_cotacoes['programa'].unique())
            df_filtrado = df_cotacoes[df_cotacoes['programa'].isin(selecao)]
            
            st.line_chart(df_filtrado, x="data_hora", y="cpm", color="programa")
            
            with st.expander("Ver Dados Brutos (Tabela)"):
                st.dataframe(df_filtrado.sort_values(by='data_hora', ascending=False), use_container_width=True)

    # --- PÁGINA: PROMOÇÕES ---
    elif menu == "Promoções":
        st.header("🔥 Radar de Oportunidades")
        try:
            con = sqlite3.connect("milhas.db")
            dfp = pd.read_sql_query("SELECT * FROM promocoes ORDER BY id DESC LIMIT 20", con)
            con.close()
            
            if not dfp.empty:
                for _, r in dfp.iterrows():
                    with st.container():
                        st.markdown(f"#### [{r['titulo']}]({r['link']})")
                        st.caption(f"Fonte: {r['origem']} | Detectado em: {r['data_hora']}")
                        st.divider()
            else:
                st.info("Nenhuma promoção detectada recentemente.")
        except:
            st.error("Erro ao carregar promoções.")

# --- ROTEADOR ---
if st.session_state['user']:
    sistema_logado()
else:
    tela_login()
