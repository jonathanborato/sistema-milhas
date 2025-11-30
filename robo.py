import asyncio
import feedparser
import time
from telegram import Bot

# --- CONFIGURAÇÃO (COLOQUE SEUS DADOS AQUI) ---
SEU_TOKEN = "8314873975:AAFTKjrbEWaCK_xplgYoEngxjRbjq3h84_I"
SEU_CHAT_ID = "5905547025" # Se for número, pode ser sem aspas ou com aspas

# Sites que vamos vigiar
SITES_PARA_MONITORAR = [
    "https://www.melhoresdestinos.com.br/feed",
    "https://passageirodeprimeira.com/feed/",
    "https://pontospravoar.com/feed/"
]

# Palavras que indicam lucro
PALAVRAS_CHAVE = ["bônus", "100%", "livelo", "esfera", "transferência", "compre pontos"]

class RoboMilhas:
    def __init__(self, token, chat_id):
        self.bot = Bot(token=token)
        self.chat_id = chat_id
        self.noticias_vistas = set() 

    async def enviar_alerta(self, titulo, link):
        """Manda mensagem pro seu celular"""
        mensagem = f"🚨 *OPORTUNIDADE DETECTADA* 🚨\n\n{titulo}\n\n🔗 {link}"
        try:
            print(f"Enviando alerta: {titulo}")
            await self.bot.send_message(chat_id=self.chat_id, text=mensagem)
        except Exception as e:
            print(f"Erro no Telegram: {e}")

    def verificar_promocoes(self):
        print("👀 Olhando os sites de milhas...")
        encontrou_algo = False
        
        for site in SITES_PARA_MONITORAR:
            try:
                feed = feedparser.parse(site)
                
                # Olha as 5 primeiras notícias
                for entrada in feed.entries[:5]:
                    titulo = entrada.title
                    link = entrada.link
                    
                    if link in self.noticias_vistas:
                        continue
                    
                    tem_palavra_chave = False
                    for palavra in PALAVRAS_CHAVE:
                        if palavra.lower() in titulo.lower():
                            tem_palavra_chave = True
                            break
                    
                    if tem_palavra_chave:
                        self.noticias_vistas.add(link)
                        asyncio.run(self.enviar_alerta(titulo, link))
                        encontrou_algo = True
                        
            except Exception as e:
                print(f"Erro ao ler site: {e}")
        
        if not encontrou_algo:
            print("Nada de novo por enquanto.")

    def iniciar(self):
        print("🤖 ROBÔ INICIADO! (Pressione Ctrl+C para parar)")
        asyncio.run(self.enviar_alerta("ROBÔ LIGADO", "Estou monitorando as promoções para você!"))
        
        while True:
            self.verificar_promocoes()
            time.sleep(60)

if __name__ == "__main__":
    robo = RoboMilhas(SEU_TOKEN, SEU_CHAT_ID)
    robo.iniciar()