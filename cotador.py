import asyncio
import re
import os
from playwright.async_api import async_playwright
from telegram import Bot
import banco

# --- CONFIGURAÇÕES ---
SEU_EMAIL = "jonathanfborato@gmail.com"
QTD_MILHAS = "100000"

PROGRAMAS = {
    "1": "Smiles",
    "2": "Latam",
    "3": "TudoAzul"
}

# Metas de Venda (Se passar disso, é Ouro!)
METAS = {
    "Smiles": 17.80,
    "Latam": 28.50,
    "TudoAzul": 22.00
}

# Segredos
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def enviar_telegram(mensagem):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensagem, parse_mode='Markdown')
        print("📱 Notificação enviada!")
    except Exception as e:
        print(f"Erro Telegram: {e}")

async def rodar_cotacao():
    banco.iniciar_banco()
    print("🚀 Iniciando Análise de Mercado...")
    
    # Cabeçalho da Mensagem
    relatorio = "📊 *BOLETIM DE MILHAS (90d)* 📊\n\n"
    tem_oportunidade = False
    
    async with async_playwright() as p:
        # headless=True para nuvem
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        for id_prog, nome_prog in PROGRAMAS.items():
            print(f"🔍 Analisando: {nome_prog}...")
            
            try:
                # 1. Recuperar preço de ONTEM (Memória)
                cpm_ontem = banco.pegar_ultimo_preco(nome_prog)
                
                # 2. Ir buscar preço de HOJE (Scraping)
                await page.goto("https://hotmilhas.com.br/")
                await page.get_by_role("textbox", name="Digite seu e-mail *").fill(SEU_EMAIL)
                await page.get_by_role("combobox").select_option(id_prog)
                
                campo_qtd = page.get_by_role("textbox", name="Quantidade de milhas *")
                await campo_qtd.click()
                await campo_qtd.fill(QTD_MILHAS)
                try:
                    await page.get_by_text("100.000", exact=True).click()
                except:
                    await page.keyboard.press("Enter")

                await page.locator("#form").get_by_role("button", name="Cotar minhas milhas").click(force=True)
                
                # Leitura
                await page.wait_for_selector("text=R$", timeout=20000)
                texto = await page.locator("body").inner_text()
                
                padrao = r"(?:em|Até)\s+(90)\s+dia[s]?.*?R\$\s?([\d\.,]+)"
                match = re.search(padrao, texto, re.DOTALL | re.IGNORECASE)
                
                if match:
                    valor_texto = match.group(2)
                    valor_float = float(valor_texto.replace('.', '').replace(',', '.'))
                    cpm_hoje = valor_float / 100
                    
                    # 3. ANÁLISE DE INTELIGÊNCIA (Comparação)
                    icone = "⚪" # Igual
                    diff = cpm_hoje - cpm_ontem
                    
                    if diff > 0.10:
                        icone = "🟢 ⬆️" # Subiu
                    elif diff < -0.10:
                        icone = "🔴 ⬇️" # Caiu
                    
                    # Verifica se bateu a meta de lucro
                    meta_aviso = ""
                    if cpm_hoje >= METAS.get(nome_prog, 100):
                        meta_aviso = "🔥 *PREÇO TOP!* "
                        tem_oportunidade = True
                    
                    # Monta a linha do relatório
                    relatorio += f"{icone} *{nome_prog}*: R$ {cpm_hoje:.2f}\n"
                    
                    if diff != 0 and cpm_ontem > 0:
                        relatorio += f"   _(Antes: R$ {cpm_ontem:.2f})_\n"
                    
                    if meta_aviso:
                        relatorio += f"   {meta_aviso}\n"
                        
                    # Salva no banco
                    banco.salvar_cotacao(nome_prog, 90, valor_float, cpm_hoje)
                    print(f"✅ {nome_prog}: R$ {cpm_hoje:.2f}")
                    
                else:
                    relatorio += f"⚠️ *{nome_prog}*: Sem oferta 90d\n"

            except Exception as e:
                print(f"Erro {nome_prog}: {e}")
                relatorio += f"❌ *{nome_prog}*: Erro\n"
            
            await context.clear_cookies()
        
        await browser.close()
        
        # Só adiciona rodapé se tiver notícia boa
        if tem_oportunidade:
            relatorio += "\n💰 *HORA DE VENDER!* Consulte o Painel."
        
        relatorio += "\n[Ver Dashboard Completo](https://share.streamlit.io)" # Você pode por seu link aqui
        
        await enviar_telegram(relatorio)

if __name__ == "__main__":
    asyncio.run(rodar_cotacao())
