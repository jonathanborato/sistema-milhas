import streamlit as st
import time

# --- 1. CONFIGURAÇÃO INICIAL (BLINDADA) ---
try:
    st.set_page_config(
        page_title="MilhasPro System",
        page_icon="✈️",
        layout="wide"
    )
except:
    pass # Ignora se já estiver setado

# --- 2. ÁREA DE DIAGNÓSTICO DE ERROS ---
# Vamos envolver o sistema todo num bloco de segurança
try:
    import pandas as pd
    import sqlite3
    import hashlib
    from datetime import datetime
    import os

    # Tenta importar Supabase, se falhar, avisa mas não quebra
    try:
        from supabase import create_client
        SUPABASE_AVAILABLE = True
    except ImportError:
        SUPABASE_AVAILABLE = False
        st.warning("⚠️ Biblioteca 'supabase' não encontrada. Verifique o requirements.txt. Rodando em modo local.")

    # --- 3. INFRAESTRUTURA DE DADOS ---
    NOME_BANCO_LOCAL = "milhas.db"

    def conectar_local():
        return sqlite3.connect(NOME_BANCO_LOCAL)

    def iniciar_banco():
        con = conectar_local()
        cur = con.cursor()
        # Tabelas Essenciais
        cur.execute('CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, email TEXT, prazo_dias INTEGER, valor_total REAL, cpm REAL)')
        cur.execute('CREATE TABLE IF NOT EXISTS promocoes (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, titulo TEXT, link TEXT, origem TEXT)')
        cur.execute('CREATE TABLE IF NOT EXISTS carteira (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_email TEXT, data_compra TEXT, programa TEXT, quantidade INTEGER, custo_total REAL, cpm_medio REAL)')
        cur.execute('CREATE TABLE IF NOT EXISTS mercado_p2p (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, grupo_nome TEXT, programa TEXT, tipo TEXT, valor REAL, observacao TEXT)')
        cur.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, nome TEXT, senha_hash TEXT, data_cadastro TEXT)')
        con.commit()
        con.close()

    def criar_hash(senha):
        return hashlib.sha256(senha.encode()).hexdigest()

    def get_supabase():
        if not SUPABASE_AVAILABLE: return None
        try:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
            return create_client(url, key)
        except:
            return None

    # --- 4. FUNÇÕES DE NEGÓCIO ---
    def registrar_usuario(nome, email, senha, telefone):
        sb = get_supabase()
        if sb:
            try:
                res = sb.table("usuarios").select("*").eq("email", email).execute()
                if len(res.data) > 0: return False, "E-mail já existe (Nuvem)."
                dados = {"email": email, "nome": nome, "senha_hash": criar_hash(senha), "telefone": telefone, "plano": "Free"}
                sb.table("usuarios").insert(dados).execute()
                return True, "Conta criada na Nuvem!"
            except Exception as e:
                return False, f"Erro Nuvem: {e}"
        
        # Fallback Local
        try:
            con = conectar_local()
            con.execute("INSERT INTO usuarios (email, nome, senha_hash) VALUES (?, ?, ?)", (email, nome, criar_hash(senha)))
            con.commit(); con.close()
            return True, "Conta criada Localmente (Aviso: Pode apagar ao reiniciar)"
        except: return False, "Erro ao criar conta."

    def autenticar_usuario(email, senha):
        senha_hash = criar_hash(senha)
        sb = get_supabase()
        
        # Tenta Nuvem
        if sb:
            try:
                res = sb.table("usuarios").select("*").eq("email", email).eq("senha_hash", senha_hash).execute()
                if len(res.data) > 0:
                    u = res.data[0]
                    return {"nome": u['nome'], "plano": u.get('plano', 'Free'), "email": email}
            except: pass
        
        # Tenta Local
        con = conectar_local()
        res = con.execute("SELECT nome FROM usuarios WHERE email = ? AND senha_hash = ?", (email, senha_hash)).fetchone()
        con.close()
        if res: return {"nome": res[0], "plano": "Local", "email": email}
        return None

    # Funções de Leitura e Escrita Genéricas
    def run_query(query, params=None):
        con = conectar_local()
        try:
            if params: df = pd.read_sql_query(query, con, params=params)
            else: df = pd.read_sql_query(query, con)
        except: df = pd.DataFrame()
        con.close()
        return df

    def run_command(sql, params):
        con = conectar_local()
        con.execute(sql, params)
        con.commit(); con.close()

    # --- INICIALIZAÇÃO ---
    iniciar_banco()

    # --- CSS ---
    st.markdown("""<style>.stButton>button {width: 100%;}</style>""", unsafe_allow_html=True)

    # --- SESSÃO ---
    if 'user' not in st.session_state: st.session_state['user'] = None

    # --- TELAS ---
    def tela_login():
        c1, c2, c3 = st.columns([1, 1.5, 1])
        with c2:
            st.markdown("<h1 style='text-align: center;'>✈️ MilhasPro</h1>", unsafe_allow_html=True)
            
            tab1, tab2 = st.tabs(["ENTRAR", "CRIAR CONTA"])
            with tab1:
                email = st.text_input("E-mail", key="log_email")
                senha = st.text_input("Senha", type="password", key="log_pass")
                if st.button("Acessar", type="primary", key="btn_log"):
                    # Admin Backdoor
                    try:
                        if email == st.secrets["admin"]["email"] and senha == st.secrets["admin"]["senha"]:
                            st.session_state['user'] = {"nome": st.secrets["admin"]["nome"], "plano": "Admin", "email": email}
                            st.rerun()
                    except: pass
                    
                    user = autenticar_usuario(email, senha)
                    if user:
                        st.session_state['user'] = user
                        st.success("Login OK!"); time.sleep(0.5); st.rerun()
                    else: st.error("Dados inválidos.")
            
            with tab2:
                st.info("Cadastro Seguro")
                n = st.text_input("Nome", key="cad_nome")
                e = st.text_input("E-mail", key="cad_email")
                w = st.text_input("Whats", key="cad_whats")
                p = st.text_input("Senha", type="password", key="cad_pass")
                if st.button("Cadastrar", key="btn_cad"):
                    if len(p) < 4: st.warning("Senha curta")
                    else:
                        ok, msg = registrar_usuario(n, e, p, w)
                        if ok: st.success(msg)
                        else: st.error(msg)

    def sistema_logado():
        user = st.session_state['user']
        with st.sidebar:
            st.title("✈️ Painel")
            st.write(f"Olá, **{user['nome']}**")
            if user['plano'] == "Admin": st.success("👑 ADMIN")
            else: st.info(f"🔹 {user['plano']}")
            st.divider()
            menu = st.radio("Menu", ["Dashboard", "Carteira", "Mercado P2P", "Promoções"])
            st.divider()
            if st.button("Sair"): st.session_state['user'] = None; st.rerun()

        # Carrega dados
        df_cot = run_query("SELECT * FROM historico ORDER BY data_hora ASC")
        if not df_cot.empty:
            df_cot['data_hora'] = pd.to_datetime(df_cot['data_hora'])
            if 'email' in df_cot.columns: df_cot = df_cot.rename(columns={'email': 'programa'})

        if menu == "Dashboard":
            st.header("📊 Mercado (Hotmilhas)")
            if not df_cot.empty:
                st.line_chart(df_cot, x="data_hora", y="cpm", color="programa")
            else: st.warning("Aguardando dados do robô.")

        elif menu == "Carteira":
            st.header("💼 Carteira")
            with st.expander("➕ Adicionar"):
                c1, c2, c3 = st.columns(3)
                p = c1.selectbox("Prog", ["Latam", "Smiles", "Azul", "Livelo"])
                q = c2.number_input("Qtd", 1000, step=1000)
                v = c3.number_input("R$ Total", 0.0, step=10.0)
                if st.button("Salvar"):
                    cpm = v/(q/1000) if q>0 else 0
                    run_command("INSERT INTO carteira (usuario_email, data_compra, programa, quantidade, custo_total, cpm_medio) VALUES (?, ?, ?, ?, ?, ?)", 
                                (user['email'], datetime.now().strftime("%Y-%m-%d"), p, q, v, cpm))
                    st.rerun()
            
            dfc = run_query("SELECT * FROM carteira WHERE usuario_email = ?", (user['email'],))
            if not dfc.empty:
                st.dataframe(dfc)
                rid = st.number_input("ID Remover", step=1)
                if st.button("Remover"): run_command("DELETE FROM carteira WHERE id = ?", (rid,)); st.rerun()
            else: st.info("Vazia.")

        elif menu == "Mercado P2P":
            st.header("📢 P2P Manual")
            with st.form("p2p"):
                c1, c2 = st.columns(2)
                g = c1.text_input("Grupo")
                p = c2.selectbox("Prog", ["Latam", "Smiles"])
                t = st.radio("Tipo", ["VENDA", "COMPRA"])
                val = st.number_input("Valor", 15.0)
                obs = st.text_input("Obs")
                if st.form_submit_button("Salvar"):
                    run_command("INSERT INTO mercado_p2p (data_hora, grupo_nome, programa, tipo, valor, observacao) VALUES (?, ?, ?, ?, ?, ?)",
                                (datetime.now().strftime("%Y-%m-%d %H:%M"), g, p, t, val, obs))
                    st.rerun()
            dfp = run_query("SELECT * FROM mercado_p2p ORDER BY id DESC")
            if not dfp.empty: st.dataframe(dfp)

        elif menu == "Promoções":
            st.header("🔥 Radar")
            dfp = run_query("SELECT * FROM promocoes ORDER BY id DESC LIMIT 15")
            if not dfp.empty:
                for _, r in dfp.iterrows(): st.markdown(f"[{r['titulo']}]({r['link']})")
            else: st.write("Nada.")

    # Roteador
    if st.session_state['user']: sistema_logado()
    else: tela_login()

except Exception as e:
    # SE DER QUALQUER ERRO, ELE MOSTRA AQUI EM VEZ DE TELA BRANCA
    st.error("🚨 ERRO CRÍTICO NO SISTEMA")
    st.code(str(e))
    st.info("Por favor, verifique se o arquivo requirements.txt contém todas as bibliotecas.")
