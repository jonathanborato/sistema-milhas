import asyncio
import re
from playwright.async_api import async_playwright
from telegram import Bot # Importa o Telegram
import banco # Importa o nosso novo arquivo de banco

# --- SUAS CONFIGURAÇÕES ---
SEU_EMAIL = "jonathanfborato@gmail.com"
QTD_MILHAS = "100000"

# CONFIG DO TELEGRAM (Pegue os mesmos do robo.py)
import os
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def enviar_telegram(mensagem):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensagem)
        print("📱 Notificação enviada para o Telegram!")
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")

async def rodar_cotacao():
    # 1. Garante que o banco existe antes de começar
    banco.iniciar_banco()
    
    print("🚀 Iniciando Sistema Completo...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=50) 
        page = await browser.new_page()
        await page.goto("https://hotmilhas.com.br/")

        print("✍️  Preenchendo formulário...")
        await page.get_by_role("textbox", name="Digite seu e-mail *").fill(SEU_EMAIL)
        await page.get_by_role("combobox").select_option("2")
        
        campo_qtd = page.get_by_role("textbox", name="Quantidade de milhas *")
        await campo_qtd.click()
        await campo_qtd.fill(QTD_MILHAS)
        try:
            await page.get_by_text("100.000", exact=True).click()
        except:
            await page.keyboard.press("Enter")

        print("👆 Cotando...")
        await page.locator("#form").get_by_role("button", name="Cotar minhas milhas").click(force=True)

        print("\n🕵️  Analisando resultados...")
        
        try:
            await page.wait_for_selector("text=R$", timeout=25000)
            texto_completo = await page.locator("body").inner_text()
            
            # Regex que já validamos
            padrao = r"(?:em|Até)\s+(\d+)\s+dia[s]?.*?R\$\s?([\d\.,]+)"
            todas_opcoes = re.findall(padrao, texto_completo, re.DOTALL | re.IGNORECASE)
            
            if todas_opcoes:
                dados_processados = []
                mensagem_telegram = "📊 *COTAÇÃO ATUALIZADA HOTMILHAS*\n\n"

                # Processa os dados
                for dias_str, valor_str in todas_opcoes:
                    dias_int = int(dias_str)
                    valor_float = float(valor_str.replace('.', '').replace(',', '.'))
                    cpm = valor_float / (float(QTD_MILHAS) / 1000)
                    
                    dados_processados.append({
                        "dias": dias_int,
                        "valor": valor_float,
                        "cpm": cpm
                    })

                # Ordena e Limpa duplicatas
                dados_unicos = {}
                for item in dados_processados:
                    dias = item['dias']
                    if dias not in dados_unicos or item['valor'] > dados_unicos[dias]['valor']:
                        dados_unicos[dias] = item
                
                lista_final = sorted(dados_unicos.values(), key=lambda x: x['dias'])

                # --- SALVAR E GERAR RELATÓRIO ---
                print("\n" + "="*60)
                print(f"{'PRAZO':<10} | {'CPM (Milheiro)':<15} | STATUS")
                print("-" * 60)
                
                melhor_cpm = 0
                
                for item in lista_final:
                    # 1. Salvar no Banco
                    banco.salvar_cotacao(SEU_EMAIL, item['dias'], item['valor'], item['cpm'])
                    
                    # 2. Adicionar ao texto do Telegram
                    mensagem_telegram += f"📅 {item['dias']} dias: R$ {item['cpm']:.2f}/milheiro\n"
                    
                    # 3. Mostrar no Terminal
                    print(f"{item['dias']} dias".ljust(10) + f" | R$ {item['cpm']:.2f}".ljust(15) + " | 💾 Salvo")
                    
                    if item['cpm'] > melhor_cpm:
                        melhor_cpm = item['cpm']

                print("="*60 + "\n")
                
                # --- FINALIZAÇÃO ---
                mensagem_telegram += f"\n🏆 *Melhor Preço:* R$ {melhor_cpm:.2f}"
                
                # Enviar para o celular
                await enviar_telegram(mensagem_telegram)

            else:
                print("⚠️ Não encontrei dados para salvar.")

        except Exception as e:
            print(f"❌ Erro: {e}")
            await page.screenshot(path="erro_sistema.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(rodar_cotacao())
