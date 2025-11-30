import asyncio
import re
import os
from playwright.async_api import async_playwright
from telegram import Bot
import banco

# --- CONFIGURAÇÕES ---
SEU_EMAIL = "jonathanfborato@gmail.com"
QTD_MILHAS = "100000"

# Dicionário dos Programas (ID no site : Nome Amigável)
PROGRAMAS = {
    "1": "Smiles (Gol)",
    "2": "Latam Pass",
    "3": "TudoAzul"
}

# --- SEGREDOS ---
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
    print("🚀 Iniciando Varredura de Mercado (Smiles, Latam, Azul)...")
    
    relatorio_final = "✈️ *RESUMO DO MERCADO DE MILHAS* ✈️\n"
    
    async with async_playwright() as p:
        # headless=True para rodar na nuvem
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # --- O LOOP MESTRE ---
        for id_programa, nome_programa in PROGRAMAS.items():
            print(f"\n🔍 Cotando: {nome_programa}...")
            
            try:
                await page.goto("https://hotmilhas.com.br/")
                
                # Preenche E-mail
                await page.get_by_role("textbox", name="Digite seu e-mail *").fill(SEU_EMAIL)
                
                # Seleciona o Programa da vez (1, 2 ou 3)
                await page.get_by_role("combobox").select_option(id_programa)
                
                # Preenche Quantidade
                campo_qtd = page.get_by_role("textbox", name="Quantidade de milhas *")
                await campo_qtd.click()
                await campo_qtd.fill(QTD_MILHAS)
                try:
                    await page.get_by_text("100.000", exact=True).click()
                except:
                    await page.keyboard.press("Enter")

                # Clica em Cotar
                await page.locator("#form").get_by_role("button", name="Cotar minhas milhas").click(force=True)

                # Espera o preço
                await page.wait_for_selector("text=R$", timeout=20000)
                
                # Lê os dados
                texto = await page.locator("body").inner_text()
                
                # Regex para pegar o preço de 90 dias (ou o maior prazo)
                # Procura por "90 dias" e pega o valor associado
                padrao = r"(?:em|Até)\s+(90)\s+dia[s]?.*?R\$\s?([\d\.,]+)"
                match = re.search(padrao, texto, re.DOTALL | re.IGNORECASE)
                
                if match:
                    valor_texto = match.group(2)
                    valor_float = float(valor_texto.replace('.', '').replace(',', '.'))
                    cpm = valor_float / 100 # Para 100k milhas, dividir por 100 dá o CPM
                    
                    print(f"✅ {nome_programa}: R$ {cpm:.2f}/milheiro")
                    
                    # Salva no Banco
                    banco.salvar_cotacao(nome_programa, 90, valor_float, cpm)
                    
                    # Adiciona ao relatório
                    relatorio_final += f"\n🟦 *{nome_programa}*\n   💰 Venda (90d): R$ {cpm:.2f}\n"
                else:
                    print(f"⚠️ Não achei preço de 90 dias para {nome_programa}")
                    relatorio_final += f"\n🔻 *{nome_programa}*: Sem cotação 90d\n"

            except Exception as e:
                print(f"❌ Erro ao cotar {nome_programa}: {e}")
                relatorio_final += f"\n🔻 *{nome_programa}*: Erro ao acessar\n"
            
            # Limpa os cookies para a próxima cotação não bugar
            await context.clear_cookies()
        
        await browser.close()
        
        # Envia o resumão no final
        await enviar_telegram(relatorio_final)

if __name__ == "__main__":
    asyncio.run(rodar_cotacao())
