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

# Variável global para armazenar a tarefa atual
current_task = None

@client.event
async def on_ready():
    print(f'Bot {client.user} conectado com sucesso e pronto para ouvir comandos!')

@client.event
async def on_message(message):
    global current_task

    # Ignora mensagens do próprio bot
    if message.author == client.user:
        return

    print(f"[DEBUG] Msg de {message.author}: {message.content} | Menções: {[m.name for m in message.mentions]}")

    # Só processa se o bot for explicitamente mencionado (marcado com @SofIA)
    if client.user not in message.mentions:
        print(f"[DEBUG] Ignorado: Bot não foi mencionado na mensagem.")
        return

    # Usa clean_content para converter IDs de menções (<@123...>) em nomes textuais (@SofIA)
    # Isso evita que a expressão regular confunda o ID do bot com o número da nota fiscal.
    texto_msg = message.clean_content.lower().strip()

    # Comando para parar/cancelar a automação
    if "parar" in texto_msg or "cancelar" in texto_msg or "stop" in texto_msg:
        if current_task is not None and not current_task.done():
            current_task.cancel()
            await message.reply("🛑 **Comando de parada recebido!** Interrompendo o processo em andamento...")
        else:
            await message.reply("Não há nenhum processo rodando no momento para ser cancelado.")
        return

    import datetime

    # Verifica se a mensagem é um comando para gerar nota usando uma expressão regular para capturar variações
    # Ex: crie a nf, gere nf, faça a nota, gerar nfe, emitir nf, etc.
    if re.search(r"(crie|gere|faça|faca|gerar|emitir).*(nf|nfe|nota)", texto_msg):
        if current_task is not None and not current_task.done():
            await message.reply("⚠️ Já estou processando um pedido no momento. Por favor, aguarde terminar ou envie `parar` para cancelar o atual.")
            return

        # Extrai o número do pedido e opcionalmente o ano (ex: 9999 ou 9999/2026)
        match_pedido = re.search(r"(\d+)(?:/(\d{2,4}))?", texto_msg)
        
        if not match_pedido:
            await message.reply("Não consegui identificar o número do pedido na sua mensagem. Exemplo válido: `crie a nf 9999`")
            return

        numero = match_pedido.group(1)
        ano = match_pedido.group(2)

        # A pesquisa do ERP aceita apenas os dígitos do pedido (sem barra e sem ano).
        # Ignoramos o ano mesmo se fornecido.
        pedido_extraido = str(numero)

        print(f"[Discord Bot] Pedido {pedido_extraido} solicitado por {message.author}.")
        
        # Responde que começou a trabalhar
        msg_status = await message.reply(f"⏳ Iniciando a automação para o pedido **{pedido_extraido}**. Por favor, aguarde... O processo no ERP pode demorar alguns minutos.")
        
        try:
            # Cria a task e armazena na variável global
            current_task = asyncio.create_task(processar_pedido_avulso(pedido_extraido))
            resultado = await current_task
            
            # Formata o resultado para ficar bonito
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

client.run(TOKEN)
