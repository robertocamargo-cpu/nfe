import os
import re
import asyncio
import discord
from dotenv import load_dotenv

# Importa a lógica do script existente
from gerar_nfe_automatica import processar_pedido_avulso, extrair_pedido

# Carrega variáveis de ambiente do .env
load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')

if not TOKEN:
    print("ERRO: Token do bot não encontrado. Adicione DISCORD_BOT_TOKEN no arquivo .env")
    exit(1)

# Configura as intenções necessárias (Message Content Intent)
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# Variável global para a fila de pedidos
pedido_queue = asyncio.Queue()
processando_agora = None

async def worker_fila():
    global processando_agora
    await client.wait_until_ready()
    while not client.is_closed():
        # Pega o próximo item da fila
        item = await pedido_queue.get()
        pedido_extraido = item['pedido']
        msg_original = item['msg_original']
        msg_status = item['msg_status']
        
        processando_agora = pedido_extraido
        try:
            resultado = await processar_pedido_avulso(pedido_extraido)
            if "OK" in resultado:
                await msg_status.reply(f"✅ **Sucesso!** O pedido **{pedido_extraido}** foi processado. Resultado: `{resultado}`")
            elif "FALHA" in resultado or "ERRO" in resultado:
                await msg_status.reply(f"❌ **Erro!** Ocorreu um problema ao processar o pedido **{pedido_extraido}**. Detalhe: `{resultado}`")
            else:
                await msg_status.reply(f"⚠️ **Aviso:** Resultado do pedido **{pedido_extraido}**: `{resultado}`")
        except asyncio.CancelledError:
            await msg_status.reply(f"🛑 **Cancelado:** O processamento do pedido **{pedido_extraido}** foi interrompido.")
        except Exception as e:
            await msg_status.reply(f"❌ **Erro fatal** ao executar a automação: `{str(e)}`")
        finally:
            processando_agora = None
            pedido_queue.task_done()

@client.event
async def on_ready():
    print(f'Bot {client.user} conectado com sucesso e pronto para ouvir comandos!')
    # Inicia o worker que vai ler a fila
    client.loop.create_task(worker_fila())

@client.event
async def on_message(message):
    global processando_agora

    # Ignora mensagens do próprio bot
    if message.author == client.user:
        return

    print(f"[DEBUG] Msg de {message.author}: {message.content} | Menções: {[m.name for m in message.mentions]}")

    # Só processa se o bot for explicitamente mencionado (marcado com @SofIA)
    if client.user not in message.mentions:
        print(f"[DEBUG] Ignorado: Bot não foi mencionado na mensagem.")
        return

    # Usa clean_content para converter IDs de menções (<@123...>) em nomes textuais (@SofIA)
    texto_msg = message.clean_content.lower().strip()

    # Comando para parar/cancelar a automação
    if "parar" in texto_msg or "cancelar" in texto_msg or "stop" in texto_msg:
        # Nota: Parar uma queue e matar o processo rodando no asyncio.create_task externo é complexo no asyncio nativo sem referenciar a task atual do worker.
        # Por simplicidade de segurança, cancelamos tudo saindo do script se pedirem para parar agressivamente.
        # Mas para o dia-a-dia, avisamos que está cancelando:
        await message.reply("🛑 **Comando de parada recebido!** Reiniciando bot de emergência...")
        os._exit(1) # Força a saída. Como geralmente roda num serviço ou podemos relogar, é a forma mais segura de abortar o Playwright limpo.
        return

    import datetime

    # Verifica se a mensagem é um comando para gerar nota usando uma expressão regular para capturar variações
    # Ex: crie a nf, gere nf, faça a nota, gerar nfe, emitir nf, etc.
    if re.search(r"(crie|gere|faça|faca|gerar|emitir).*(nf|nfe|nota)", texto_msg):
        
        # Extrai o número do pedido e opcionalmente o ano (ex: 9999 ou 9999/2026)
        match_pedido = re.search(r"(\d+)(?:/(\d{2,4}))?", texto_msg)
        
        if not match_pedido:
            await message.reply("Não consegui identificar o número do pedido na sua mensagem. Exemplo válido: `crie a nf 9999`")
            return

        numero = match_pedido.group(1)
        ano = match_pedido.group(2)
        pedido_extraido = str(numero)

        print(f"[Discord Bot] Pedido {pedido_extraido} solicitado por {message.author}.")
        
        # Avaliar fila
        tamanho_fila = pedido_queue.qsize()
        if processando_agora:
            posicao = tamanho_fila + 1
            msg_status = await message.reply(f"⏳ O pedido **{pedido_extraido}** entrou na fila (Posição {posicao}). Atualmente processando o {processando_agora}...")
        else:
            msg_status = await message.reply(f"⏳ Iniciando a automação para o pedido **{pedido_extraido}**. Por favor, aguarde...")
            
        await pedido_queue.put({
            'pedido': pedido_extraido,
            'msg_original': message,
            'msg_status': msg_status
        })

client.run(TOKEN)
