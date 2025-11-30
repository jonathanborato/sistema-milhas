import streamlit as st
import time

st.set_page_config(page_title="Teste Supabase", layout="centered")

st.title("🕵️ Diagnóstico de Conexão")
st.write("Vamos descobrir por que não está gravando na nuvem.")

# --- TESTE 1: BIBLIOTECA ---
st.header("1. Verificando Biblioteca")
try:
    from supabase import create_client, Client
    st.success("✅ Biblioteca `supabase` está instalada corretamente.")
except ImportError:
    st.error("❌ ERRO CRÍTICO: A biblioteca `supabase` NÃO foi encontrada.")
    st.info("Solução: Verifique se o arquivo `requirements.txt` no GitHub contém a palavra `supabase` e reinicie o app.")
    st.stop()

# --- TESTE 2: SEGREDOS (SECRETS) ---
st.header("2. Verificando Segredos")
url = ""
key = ""
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    if url and key:
        st.success("✅ Chaves de acesso encontradas nos Secrets.")
        st.text(f"URL detectada: {url[:20]}...")
    else:
        st.error("❌ Chaves encontradas mas estão vazias.")
except Exception as e:
    st.error(f"❌ ERRO: Não consegui ler os Secrets. {e}")
    st.info("Solução: Vá no painel do Streamlit Cloud > Settings > Secrets e cole as chaves corretamente.")
    st.stop()

# --- TESTE 3: CONEXÃO REAL ---
st.header("3. Tentando Conectar no Banco")
try:
    supabase = create_client(url, key)
    # Tenta ler a tabela de usuários
    response = supabase.table("usuarios").select("*").limit(1).execute()
    st.success("✅ Conexão BEM SUCEDIDA com o Supabase!")
    st.write("Dados recebidos do banco:", response.data)
    
    # Tenta Gravar um Usuário de Teste
    if st.button("Testar Gravação (Criar usuário fake)"):
        try:
            teste_email = f"teste_{int(time.time())}@email.com"
            dados = {
                "email": teste_email,
                "nome": "Usuario Teste",
                "senha_hash": "teste123",
                "plano": "Free"
            }
            supabase.table("usuarios").insert(dados).execute()
            st.success(f"🎉 SUCESSO TOTAL! Gravei o usuário: {teste_email}")
            st.balloons()
        except Exception as e_grav:
            st.error(f"❌ Conectou, mas falhou ao gravar: {e_grav}")
            st.info("Dica: Verifique se você criou a tabela 'usuarios' no SQL Editor do Supabase.")

except Exception as e:
    st.error(f"❌ Falha ao conectar: {e}")
    st.warning("Verifique se a 'Project URL' e 'API Key' estão corretas nos Secrets.")
