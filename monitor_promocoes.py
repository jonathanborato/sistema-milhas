import feedparser
import banco
import re

# Fontes de Inteligência (RSS Feeds)
FEEDS = [
    {"url": "https://passageirodeprimeira.com/feed/", "nome": "Passageiro de Primeira"},
    {"url": "https://pontospravoar.com/feed/", "nome": "Pontos pra Voar"},
    {"url": "https://www.melhoresdestinos.com.br/feed", "nome": "Melhores Destinos"}
]

# Palavras-Chave (O que estamos procurando?)
# Ex: "Compra de pontos Livelo", "Transferência Latam", "Bônus"
PALAVRAS_CHAVE = [
    "livelo", "esfera", "smiles", "latam", "tudoazul", "azul", 
    "compra de pontos", "transferência", "bônus", "% de desconto"
]

def contem_palavra_chave(texto):
    texto_lower = texto.lower()
    # Verifica se tem alguma das empresas
    tem_empresa = any(empresa in texto_lower for empresa in ["livelo", "esfera", "smiles", "latam", "azul"])
    # Verifica se tem palavra de ação
    tem_acao = any(acao in texto_lower for acao in ["bônus", "transferência", "compra", "desconto", "off"])
    
    return tem_empresa and tem_acao

def rodar_monitoramento():
    print("📡 Iniciando Radar de Promoções...")
    banco.iniciar_banco()
    
    for fonte in FEEDS:
        print(f"Lendo: {fonte['nome']}...")
        try:
            feed = feedparser.parse(fonte['url'])
            
            # Pega as 10 notícias mais recentes
            for entry in feed.entries[:10]:
                titulo = entry.title
                link = entry.link
                
                if contem_palavra_chave(titulo):
                    # Salva no banco
                    banco.salvar_promocao(titulo, link, fonte['nome'])
                    
        except Exception as e:
            print(f"Erro ao ler {fonte['nome']}: {e}")

if __name__ == "__main__":
    rodar_monitoramento()
