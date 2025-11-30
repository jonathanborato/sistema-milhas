import streamlit as st
import pandas as pd
import sqlite3
import banco
import time

st.set_page_config(page_title="Milhas Pro System", page_icon="✈️", layout="wide")
banco.iniciar_banco()

# --- LOGIN ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
    st.session_state['usuario_nome'] = ""

def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://cdn-icons-png.flaticon.com/512/723/723955.png", width=80)
        st.title("Milhas Pro System")
        st.markdown("### Acesso Restrito")
        
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        
        if st.button("Entrar", type="primary"):
            # Verifica Secrets (Admin Cloud)
            try:
                if email == st.secrets["admin"]["email"] and senha == st.secrets["admin"]["senha"]:
                    st.session_state['logado'] = True
                    st.session_state['usuario_nome'] = st.secrets["admin"]["nome"]
                    st.rerun()
            except: pass
            
            # Verifica Banco (Local/Teste)
            user = banco.verificar_login(email, senha)
            if user:
                st.session_state['logado'] = True
                st.session_state['usuario_nome'] = user
                st.rerun()
            else:
                st.error("Dados incorretos.")

def sistema_principal():
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/723/723955.png", width=100)
        st.write(f"Olá, **{st.session_state['usuario_nome']}**")
        if st.button("Sair"):
            st.session_state['logado'] = False
            st.rerun()
        st.divider()
        
        # MENU ATUALIZADO
        menu = st.radio("Navegação", ["Minha Carteira", "Análise de Mercado", "Mercado P2P (Grupos)", "Promoções"])

    st.title("🏦 Gestão de Patrimônio em Milhas")

    # Funções de Dados
    def carregar_cotacoes():
        try:
            con = sqlite3.connect("milhas.db")
            df = pd.read_sql_query("SELECT * FROM historico ORDER BY data_hora ASC", con)
            con.close()
            if not df.empty:
                df['data_hora'] = pd.to_datetime(df['data_hora'])
                if 'email' in df.columns: df = df.rename(columns={'email': 'programa'})
            return df
        except: return pd.DataFrame()

    df_cotacoes = carregar_cotacoes()

    # --- ABA: MINHA CARTEIRA ---
    if menu == "Minha Carteira":
        st.header("💼 Seu Estoque")
        with st.expander("➕ Adicionar Lote", expanded=False):
            c1, c2, c3 = st.columns(3)
            prog = c1.selectbox("Programa", ["Latam Pass", "Smiles", "TudoAzul", "Livelo", "Esfera"])
            qtd = c2.number_input("Qtd Milhas", 1000, step=1000)
            custo = c3.number_input("Custo Total (R$)", 0.0, step=10.0)
            if st.button("Salvar Lote"):
                banco.adicionar_milhas(prog, qtd, custo)
                st.rerun()
        
        df_cart = banco.ler_carteira()
        if not df_cart.empty:
            total_pat = 0
            total_cus = 0
            
            # Tabela Enriquecida
            lista_view = []
            for _, row in df_cart.iterrows():
                # Pega preço atual (venda)
                filtro = df_cotacoes[df_cotacoes['programa'].str.contains(row['programa'].split()[0], case=False, na=False)]
                preco_atual = filtro.iloc[-1]['cpm'] if not filtro.empty else 0.0
                
                val_venda = (row['quantidade']/1000) * preco_atual
                lucro = val_venda - row['custo_total']
                
                total_pat += val_venda
                total_cus += row['custo_total']
                
                lista_view.append({
                    "ID": row['id'],
                    "Programa": row['programa'],
                    "Qtd": row['quantidade'],
                    "CPM Pago": row['cpm_medio'],
                    "Venda Hoje": preco_atual,
                    "Lucro Proj.": profit_color(lucro) # Função fake, uso style no dataframe
                })
            
            # KPIs
            k1, k2, k3 = st.columns(3)
            k1.metric("Patrimônio", f"R$ {total_pat:,.2f}")
            k2.metric("Custo", f"R$ {total_cus:,.2f}")
            k3.metric("Lucro Potencial", f"R$ {total_pat - total_cus:,.2f}")
            
            st.dataframe(pd.DataFrame(lista_view))
            
            # Remover
            rid = st.number_input("ID para remover", step=1)
            if st.button("Excluir Lote"):
                banco.remover_item_carteira(rid)
                st.rerun()
        else:
            st.info("Carteira Vazia.")

    # --- ABA: ANÁLISE DE MERCADO ---
    elif menu == "Análise de Mercado":
        st.header("📊 Cotações (Hotmilhas)")
        if not df_cotacoes.empty:
            cols = st.columns(3)
            for i, p in enumerate(["Latam", "Smiles", "Azul"]):
                d = df_cotacoes[df_cotacoes['programa'].str.contains(p, case=False, na=False)]
                with cols[i]:
                    if not d.empty:
                        st.metric(p, f"R$ {d.iloc[-1]['cpm']:.2f}")
                        st.line_chart(d, x="data_hora", y="cpm")
                    else: st.metric(p, "--")

    # --- ABA: MERCADO P2P (NOVO!) ---
    elif menu == "Mercado P2P (Grupos)":
        st.header("📢 Radar de Grupos (Telegram/WhatsApp)")
        st.info("Registe aqui as oportunidades que você vê nos grupos.")
        
        with st.form("form_p2p"):
            c1, c2 = st.columns(2)
            grupo = c1.text_input("Nome do Grupo (Ex: Balcão Milhas)")
            prog = c2.selectbox("Programa", ["Latam", "Smiles", "Azul", "Livelo", "Esfera"])
            
            c3, c4 = st.columns(2)
            tipo = c3.radio("Tipo", ["VENDA (Estão vendendo)", "COMPRA (Estão comprando)"])
            valor = c4.number_input("Valor do Milheiro (R$)", 10.00, 40.00, step=0.10)
            
            obs = st.text_area("Observações (Ex: Pagamento no pix, nome do vendedor)")
            
            enviou = st.form_submit_button("💾 Registrar Oferta")
            
            if enviou:
                banco.adicionar_oferta_p2p(grupo, prog, tipo, valor, obs)
                st.success("Registrado!")
                time.sleep(1)
                st.rerun()
        
        st.divider()
        st.subheader("📋 Últimos Registros")
        df_p2p = banco.ler_p2p()
        
        if not df_p2p.empty:
            st.dataframe(df_p2p, hide_index=True, use_container_width=True)
        else:
            st.write("Nenhum registro manual ainda.")

    # --- ABA: PROMOÇÕES ---
    elif menu == "Promoções":
        st.header("🔥 Promoções (Blogs)")
        try:
            con = sqlite3.connect("milhas.db")
            dfp = pd.read_sql_query("SELECT * FROM promocoes ORDER BY id DESC LIMIT 20", con)
            con.close()
            for _, r in dfp.iterrows():
                st.markdown(f"**{r['data_hora'][5:10]}** | [{r['titulo']}]({r['link']})")
        except: st.write("Nada ainda.")

def profit_color(val):
    return val # Apenas placeholder

if st.session_state['logado']: sistema_principal()
else: tela_login()
