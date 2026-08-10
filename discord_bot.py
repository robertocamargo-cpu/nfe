import os
import re
import asyncio
import discord
from dotenv import load_dotenv

# Importa a lógica do script existente
from gerar_nfe_automatica import processar_pedido_avulso

# Carrega variáveis de ambiente do .env
load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')

if not TOKEN:
    print("ERRO: Token do bot não encontrado. Adicione DISCORD_BOT_TOKEN no arquivo .env")
    exit(1)


def env_int(nome_variavel):
    valor = os.getenv(nome_variavel, "").strip()
    if not valor:
        return None
    try:
        return int(valor)
    except ValueError:
        print(f"AVISO: {nome_variavel} deve conter apenas o ID numerico do canal. Valor ignorado.")
        return None


def env_int_set(nome_variavel):
    valores = set()
    for parte in os.getenv(nome_variavel, "").replace(";", ",").split(","):
        parte = parte.strip()
        if not parte:
            continue
        try:
            valores.add(int(parte))
        except ValueError:
            print(f"AVISO: {nome_variavel} contem um ID invalido e foi ignorado: {parte}")
    return valores


# ─── Configuração de Canais ────────────────────────────────────────────────────
# Cada canal tem uma finalidade exclusiva. A SofIA só executa o comando correto
# no canal correto. Em canais desconhecidos, ela ignora silenciosamente.
#
# Este repositório só executa NFe. Outros objetivos, como GNRE, devem viver
# no projeto correspondente e usar seus próprios canais/configurações.
CANAL_NFE_ID = env_int("DISCORD_NFE_CHANNEL_ID") or env_int("DISCORD_CHANNEL_ID")
USUARIOS_AUTORIZADOS = env_int_set("DISCORD_NFE_ALLOWED_USER_IDS")
CARGOS_AUTORIZADOS = env_int_set("DISCORD_NFE_ALLOWED_ROLE_IDS")

CANAIS_PERMITIDOS = {
    CANAL_NFE_ID: {
        "finalidade": "nfe",
        "descricao": "Canal de Notas Fiscais Eletrônicas"
    },
} if CANAL_NFE_ID else {}


def usuario_autorizado(message):
    if not USUARIOS_AUTORIZADOS and not CARGOS_AUTORIZADOS:
        return True
    if message.author.id in USUARIOS_AUTORIZADOS:
        return True
    cargos_usuario = {role.id for role in getattr(message.author, "roles", [])}
    return bool(cargos_usuario & CARGOS_AUTORIZADOS)

# Configura as intenções necessárias (Message Content Intent)
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# Fila de pedidos NFe (criada dentro do event loop do discord no on_ready)
pedido_queue = None
worker_task = None
processando_agora = None

async def worker_fila():
    global processando_agora
    await client.wait_until_ready()
    while not client.is_closed():
        item = await pedido_queue.get()
        pedido_extraido = item['pedido']
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
    global pedido_queue, worker_task
    if pedido_queue is None:
        # Criar a Queue AQUI garante que ela pertença ao mesmo event loop do discord.py
        pedido_queue = asyncio.Queue()
    if worker_task is None or worker_task.done():
        worker_task = asyncio.create_task(worker_fila())
    print(f'Bot {client.user} conectado com sucesso e pronto para ouvir comandos!')
    if not CANAIS_PERMITIDOS:
        print("AVISO: Nenhum canal configurado. Defina DISCORD_NFE_CHANNEL_ID no .env para aceitar pedidos de NFe.")

@client.event
async def on_message(message):
    global processando_agora

    # Ignora mensagens do próprio bot
    if message.author == client.user:
        return

    # Só processa se o bot for explicitamente mencionado (@SofIA)
    if client.user not in message.mentions:
        return

    canal_id = message.channel.id
    canal_config = CANAIS_PERMITIDOS.get(canal_id)

    # Usa clean_content para evitar que IDs de menção virem números de pedido
    texto_msg = message.clean_content.lower().strip()

    print(f"[DEBUG] Mencao recebida de {message.author} no canal {canal_id}.")

    # ─── Canal não mapeado: ignora silenciosamente ───────────────────────────
    if canal_config is None:
        print(f"[DEBUG] Canal {canal_id} não configurado. Ignorando.")
        return

    if not usuario_autorizado(message):
        await message.reply("⚠️ Você não tem permissão para acionar a automação de NFe neste canal.")
        print(f"[SEGURANCA] Usuario sem permissao tentou acionar NFe: {message.author} ({message.author.id})")
        return

    finalidade = canal_config["finalidade"]

    # ─── Canal NFe ──────────────────────────────────────────────────────────────
    if finalidade == "nfe":

        # Comando de parada fica restrito ao canal/finalidade NFe e usuarios autorizados.
        if "parar" in texto_msg or "cancelar" in texto_msg or "stop" in texto_msg:
            await message.reply("🛑 **Comando de parada recebido!** Reiniciando bot de emergência...")
            os._exit(1)
            return

        # Se o usuário tentar pedir GNRE ou outro serviço no canal de NFe
        if re.search(r"\bgnre\b", texto_msg):
            await message.reply(
                "⚠️ Este canal é exclusivo para **Notas Fiscais Eletrônicas**.\n"
                "Para solicitações de GNRE, utilize o canal correto."
            )
            return

        # Comando para gerar NFe
        if re.search(r"(crie|gere|faça|faca|gerar|emitir).*(nf|nfe|nota)", texto_msg):
            match_pedido = re.search(r"(\d+)(?:/(\d{2,4}))?", texto_msg)

            if not match_pedido:
                await message.reply("Não consegui identificar o número do pedido. Exemplo válido: `@SofIA crie a nf 9999`")
                return

            pedido_extraido = str(match_pedido.group(1))

            print(f"[Discord Bot] NFe - Pedido {pedido_extraido} solicitado por {message.author}.")

            # Informar posição na fila ou início imediato
            if processando_agora:
                posicao = pedido_queue.qsize() + 1
                msg_status = await message.reply(
                    f"⏳ O pedido **{pedido_extraido}** entrou na fila (Posição {posicao}). "
                    f"Atualmente processando o pedido **{processando_agora}**..."
                )
            else:
                msg_status = await message.reply(
                    f"⏳ Iniciando a automação para o pedido **{pedido_extraido}**. Por favor, aguarde..."
                )

            await pedido_queue.put({
                'pedido': pedido_extraido,
                'msg_status': msg_status
            })
            return

        # Mensagem mencionou a SofIA mas não é um comando reconhecido neste canal
        await message.reply(
            "Olá! 👋 Neste canal posso **emitir Notas Fiscais**.\n"
            "Use: `@SofIA crie a nf 9999` para gerar uma NF."
        )

client.run(TOKEN)
