import os
import re
import asyncio
import discord
from dotenv import load_dotenv

import database
# Importa a lógica do script existente
from gerar_nfe_automatica import processar_pedido_avulso, obter_arquivos_nfe_pedido

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
                await msg_status.reply(f"✅ Pedido **{pedido_extraido}** — Processado com sucesso\n📄 Resultado: {resultado}")
            elif "FALHA" in resultado or "ERRO" in resultado:
                await msg_status.reply(f"❌ Pedido **{pedido_extraido}** — Erro no processamento\n↳ Detalhe: {resultado}")
            else:
                await msg_status.reply(f"⚠️ Pedido **{pedido_extraido}** — {resultado}")
        except asyncio.CancelledError:
            await msg_status.reply(f"🛑 Pedido **{pedido_extraido}** — Processamento interrompido.")
        except Exception as e:
            await msg_status.reply(f"❌ Pedido **{pedido_extraido}** — Erro na automação\n↳ {str(e)}")
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

    # Processa se o bot for mencionado (@SofIA) ou se o nome 'sofia' estiver no texto
    mencionou_bot = (client.user in message.mentions) or ("sofia" in message.clean_content.lower())
    if not mencionou_bot:
        return

    # Se a mensagem mencionar explicitamente outro usuário no texto (ex: @Fulano), ignora conversa de terceiros
    # Não ignora se for apenas uma resposta (reply) do Discord onde o usuário marcou @SofIA
    outras_mencoes_no_texto = [
        m for m in message.mentions 
        if m != client.user and (f"@{m.display_name.lower()}" in message.clean_content.lower() or f"@{m.name.lower()}" in message.clean_content.lower())
    ]
    if outras_mencoes_no_texto:
        print(f"[DEBUG] Mensagem cita outro usuário no texto ({[m.name for m in outras_mencoes_no_texto]}). Ignorando conversa de terceiros.")
        return

    canal_id = message.channel.id
    canal_config = CANAIS_PERMITIDOS.get(canal_id)

    # Usa clean_content para evitar que IDs de menção virem números de pedido
    texto_msg = message.clean_content.lower().strip()

    print(f"[DEBUG] Mencao recebida de {message.author} no canal {canal_id}: '{texto_msg}'")

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

        # Comando de métricas de emissão
        if any(k in texto_msg for k in ["metricas", "métricas", "relatorio", "relatório", "resumo", "quantas"]):
            m = database.obter_metricas()
            msg_metricas = (
                f"📊 **Relatório de Emissões — SofIA** ({m['atualizado_em']})\n"
                f"🟢 **Hoje ({m['hoje']['data']}):** {m['hoje']['nfe']} NFes | {m['hoje']['boletos']} Boletos\n"
                f"🟡 **Ontem ({m['ontem']['data']}):** {m['ontem']['nfe']} NFes | {m['ontem']['boletos']} Boletos\n"
                f"🔵 **Este Mês ({m['este_mes']['mes']}):** {m['este_mes']['nfe']} NFes | {m['este_mes']['boletos']} Boletos\n"
                f"🟣 **Mês Passado ({m['mes_passado']['mes']}):** {m['mes_passado']['nfe']} NFes | {m['mes_passado']['boletos']} Boletos"
            )
            await message.reply(msg_metricas)
            return

        # Comando "mostrar nota fiscal <pedido>", "ver nf <pedido>", "pdf nota fiscal <pedido>", "3352 pdf", etc.
        palavras_consulta = ["mostrar", "ver", "buscar", "baixar", "enviar", "pdf", "obter", "danfe", "segunda via", "2via"]
        eh_consulta = any(p in texto_msg for p in palavras_consulta)

        match_numero = re.search(r"\b(\d{3,6})(?:/(\d{2,4}))?\b", texto_msg)

        if eh_consulta and match_numero:
            pedido_req = match_numero.group(1)
            msg_busca = await message.reply(f"🔎 Buscando DANFE/Boleto do pedido **{pedido_req}** no ERP, aguarde...")
            
            arquivos = await obter_arquivos_nfe_pedido(pedido_req)
            if not arquivos:
                await msg_busca.edit(content=f"❌ Não foi possível localizar ou baixar a nota fiscal do pedido **{pedido_req}** no ERP.")
                return

            discord_files = [discord.File(filepath) for filepath in arquivos if os.path.exists(filepath)]
            if discord_files:
                await message.reply(
                    f"📄 Aqui está a Nota Fiscal / Boleto do pedido **{pedido_req}**:",
                    files=discord_files
                )
                await msg_busca.delete()
                # Limpar arquivos temporários
                for filepath in arquivos:
                    try: os.remove(filepath)
                    except: pass
            else:
                await msg_busca.edit(content=f"❌ Erro ao anexar o arquivo PDF da nota do pedido **{pedido_req}**.")
            return

        # Comando para gerar/emitir NFe - Apenas aciona faturamento se contiver verbos de emissão ou apenas o número solto
        palavras_emissao = ["gerar", "emitir", "faturar", "crie", "criar", "faz", "fazer"]
        eh_emissao_explicita = any(p in texto_msg for p in palavras_emissao) or re.match(r"^(?:<@!?\d+>|\bsofia\b)?\s*(\d{3,6})(?:/(\d{2,4}))?\s*$", texto_msg)

        if match_numero and (eh_emissao_explicita or not eh_consulta):
            pedido_extraido = str(match_numero.group(1))

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
            "Olá! 👋 Neste canal posso **enviar Notas Fiscais/Boletos** em PDF ou **emitir NFes**.\n"
            "• Para ver PDF: `@SofIA mostrar nota fiscal 3352` ou `@SofIA ver nf 3352`\n"
            "• Para emitir NF: `@SofIA emitir nf 3352` ou `@SofIA faturar 3352`"
        )


client.run(TOKEN)
