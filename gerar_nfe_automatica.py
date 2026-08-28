import asyncio
import re
import sys
import logging

import csv
import io
import os
import datetime
import json
import time
import urllib.request
import urllib.error
from playwright.async_api import async_playwright

import database

# Pegar o diretorio onde o script esta localizado
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "logs", "nfe_cron.log")
LOCKS_DIR = os.path.join(BASE_DIR, "locks")

log_handlers = [logging.FileHandler(LOG_PATH)]
if sys.stdout.isatty():
    log_handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=log_handlers,
)

# Tentar carregar variaveis do arquivo .env se ele existir
try:
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value
except:
    pass

# ─── Configuracoes ─────────────────────────────────────────────────────────
SPREADSHEET_ID_1  = os.getenv("SPREADSHEET_ID_PRINCIPAL", os.getenv("SPREADSHEET_ID", "1dvIgAH5B3ePkB_4npXRMVcOB6GUBt8JhCFy5D5u-igs"))
SPREADSHEET_URL_1 = "https://docs.google.com/spreadsheets/d/" + SPREADSHEET_ID_1 + "/edit"

SPREADSHEET_ID_2  = os.getenv("SPREADSHEET_ID_TRANSPORTE", "1pVnhOWvuGKn66CmXNhEZNTPpsiQMcBUpyrYtHMcmp-g")
SPREADSHEET_URL_2 = "https://docs.google.com/spreadsheets/d/" + SPREADSHEET_ID_2 + "/edit"

SPREADSHEET_ID_3  = os.getenv("SPREADSHEET_ID_VALDEX", "1hIVyui_6Ciol94CVtdhNDv7WKSkqz8lM79I0z9TvA_c")
SPREADSHEET_URL_3 = "https://docs.google.com/spreadsheets/d/" + SPREADSHEET_ID_3 + "/edit"

def get_target_day():
    now = datetime.datetime.now()
    # Antes das 08:50 olha para hoje. A partir das 08:50 olha para o dia seguinte (+1).
    if now.hour < 8 or (now.hour == 8 and now.minute < 50):
        target_date = now
    else:
        target_date = now + datetime.timedelta(days=1)
    return target_date.strftime("%d")

ABA_ALVO = get_target_day()

ERP_URL = "https://erp.admsis.com/Home"
USUARIO = os.getenv("ERP_USER")
SENHA   = os.getenv("ERP_PASS")

GOOGLE_USER = os.getenv("GOOGLE_USER", "")
GOOGLE_PASS = os.getenv("GOOGLE_PASS", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_BOT_TOKEN   = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_NFE_REPORT_CHANNEL_ID  = (
    os.getenv("DISCORD_NFE_REPORT_CHANNEL_ID")
    or os.getenv("DISCORD_NFE_CHANNEL_ID")
    or os.getenv("DISCORD_CHANNEL_ID", "")
)

MAX_TENTATIVAS_GERACAO = 5
LOCK_PEDIDO_TTL_SEGUNDOS = 2 * 60 * 60


def env_bool(nome_variavel, padrao=False):
    valor = os.getenv(nome_variavel)
    if valor is None:
        return padrao
    return valor.strip().lower() in ("1", "true", "sim", "yes", "on")


def env_int(nome_variavel, padrao=0):
    valor = os.getenv(nome_variavel)
    if valor is None or not valor.strip():
        return padrao
    try:
        return int(valor)
    except ValueError:
        logging.info(f"[AVISO] {nome_variavel} invalido: use apenas numeros. Usando {padrao}.")
        return padrao


def validar_credenciais_erp():
    if USUARIO and SENHA:
        return True
    logging.info("ERRO FATAL: Credenciais do ERP nao encontradas no .env!")
    return False


def get_user_data_dir():
    if os.name == 'nt':  # Windows
        local_app_data = os.getenv("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    else:  # Mac / Linux
        local_app_data = os.path.expanduser("~/Library/Application Support")
    user_data_dir = os.path.join(local_app_data, "Automacao_NFe_Transporte", "sessao_robo")
    os.makedirs(user_data_dir, exist_ok=True)
    return user_data_dir


def get_browser_options():
    options = {
        "headless": env_bool("NFE_HEADLESS", True),
        "slow_mo": env_int("NFE_SLOW_MO_MS", 0),
        "viewport": {"width": 1366, "height": 768},
    }
    if env_bool("NFE_RECORD_VIDEO", True):
        os.makedirs(os.path.join(BASE_DIR, "videos"), exist_ok=True)
        options["record_video_dir"] = os.path.join(BASE_DIR, "videos/")
    return options


def texto_curto(texto, limite=900):
    if not texto:
        return ""
    linhas = [re.sub(r"[^\S\r\n]+", " ", line).strip() for line in str(texto).splitlines()]
    texto_formatado = "\n".join(linhas).strip()
    if len(texto_formatado) > limite:
        return texto_formatado[:limite - 3] + "..."
    return texto_formatado


def motivo_erro_externo(resultado):
    """Retorna um motivo quando o ERP indica bloqueio externo a automacao."""
    txt = str(resultado or "").lower()
    motivos = [
        ("rejei", "Rejeicao retornada pelo ERP/SEFAZ"),
        ("sefaz", "Falha ou rejeicao da SEFAZ"),
        ("deneg", "NFe denegada"),
        ("duplic", "Possivel duplicidade de NFe"),
        ("certificado", "Problema de certificado no emissor"),
        ("cnpj", "Problema cadastral/CNPJ"),
        ("inscri", "Problema cadastral/inscricao estadual"),
        ("cadastro", "Cadastro do cliente/produto precisa de ajuste"),
        ("tribut", "Configuracao fiscal/tributaria precisa de ajuste"),
        ("cfop", "Configuracao fiscal/CFOP precisa de ajuste"),
        ("ncm", "Configuracao fiscal/NCM precisa de ajuste"),
        ("sem estoque", "Pedido/produto sem estoque"),
        ("estoque insuficiente", "Pedido/produto sem estoque suficiente"),
        ("saldo insuficiente", "Saldo insuficiente para faturamento"),
        ("ja faturado", "Pedido ja faturado ou indisponivel para gerar NFe"),
        ("indisponivel", "ERP nao disponibilizou a geracao para este pedido"),
        ("sem confirmacao clara", "ERP nao confirmou autorizacao da NFe"),
        ("invalid child element", "Erro de validacao de dados no cadastro/SEFAZ"),
        ("element", "Erro de validacao de dados no cadastro/SEFAZ"),
        ("expected", "Erro de validacao de dados no cadastro/SEFAZ"),
        ("schema", "Erro de schema XML no cadastro/SEFAZ"),
    ]
    for chave, motivo in motivos:
        if chave in txt:
            return motivo
    return None


def erro_de_sessao_ou_rede(resultado):
    txt = str(resultado or "").lower()
    return any(k in txt for k in [
        "closed",
        "network_io_suspended",
        "navigation failed",
        "connection refused",
        "target page",
        "browser has been closed",
        "timeout",
        "net::",
    ])


def caminho_lock_pedido(pedido):
    pedido_limpo = re.sub(r"\D+", "", str(pedido or "")) or "sem_numero"
    return os.path.join(LOCKS_DIR, f"pedido_{pedido_limpo}.lock")


def adquirir_lock_pedido(pedido):
    os.makedirs(LOCKS_DIR, exist_ok=True)
    lock_path = caminho_lock_pedido(pedido)

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as f:
            f.write(f"pid={os.getpid()}\ncriado_em={datetime.datetime.now().isoformat()}\n")
        return lock_path
    except FileExistsError:
        try:
            idade = time.time() - os.path.getmtime(lock_path)
            if idade > LOCK_PEDIDO_TTL_SEGUNDOS:
                logging.info(f"      [AVISO] Lock antigo removido para o pedido {pedido}.")
                os.remove(lock_path)
                return adquirir_lock_pedido(pedido)
        except Exception as e:
            logging.info(f"      [AVISO] Nao foi possivel verificar lock do pedido {pedido}: {e}")
        return None


def liberar_lock_pedido(lock_path):
    if not lock_path:
        return
    try:
        os.remove(lock_path)
    except FileNotFoundError:
        pass
    except Exception as e:
        logging.info(f"      [AVISO] Nao foi possivel liberar lock {lock_path}: {e}")


async def boleto_ja_emitido(erp_page):
    """Detecta sinais fortes de boleto ja existente antes de gerar algo novo."""
    try:
        texto = await erp_page.locator("body").inner_text(timeout=5000)
    except Exception:
        return False, ""

    texto_normalizado = re.sub(r"\s+", " ", texto or "").strip().lower()
    if not texto_normalizado:
        return False, ""

    padroes_boleto_emitido = [
        r"boleto\s+(?:ja\s+)?(?:emitido|gerado|existente|registrado)",
        r"boleto\(s\)\s+(?:emitido|gerado|registrado)",
        r"2[ªa]\s+via\s+(?:do\s+)?boleto",
        r"segunda\s+via\s+(?:do\s+)?boleto",
        r"linha\s+digit[aá]vel\s*[:\-]?\s*\d",
        r"nosso\s+n[uú]mero\s*[:\-]?\s*\d",
        r"imprimir\s+boleto",
        r"visualizar\s+boleto",
        r"baixar\s+boleto",
        r"reimprimir\s+boleto",
    ]

    for padrao in padroes_boleto_emitido:
        if re.search(padrao, texto_normalizado, re.IGNORECASE):
            return True, padrao

    return False, ""


async def gerar_boleto_se_necessario(erp_page, pedido):
    boleto_emitido, padrao_boleto = await boleto_ja_emitido(erp_page)
    if boleto_emitido:
        logging.info(f"  Boleto ja consta no ERP para o pedido {pedido} ({padrao_boleto}).")
        return "OK - NFe autorizada; boleto ja consta no ERP"

    seletores_boleto = [
        r"Gerar\s+Boleto",
        r"Emitir\s+Boleto",
        r"Gerar\s+Boleto\(s\)",
    ]

    for padrao in seletores_boleto:
        btn_boleto = erp_page.get_by_text(re.compile(padrao, re.IGNORECASE)).last
        try:
            if await btn_boleto.count() > 0 and await btn_boleto.is_visible():
                await btn_boleto.click()
                logging.info(f"  Boleto gerado para o pedido {pedido}.")
                await asyncio.sleep(3)
                await esperar_carregamento_erp(erp_page)
                return "OK - NFe autorizada; boleto gerado"
        except Exception as e:
            return "ERRO ao gerar boleto: " + str(e)

    logging.info(f"  NFe autorizada com sucesso para o pedido {pedido}.")
    return "OK - NFe autorizada (sem boleto)"


async def contar_boletos_erp(erp_page):
    """Conta a quantidade de parcelas/boletos gerados na tela do ERP com verificação estrita de Pix/Cartão/À Vista."""
    try:
        # Verificar se a tela indica pagamento sem boleto (Pix, Cartão, Dinheiro, À vista)
        texto_tela = (await erp_page.locator("body").inner_text(timeout=5000)).lower()
        if any(metodo in texto_tela for metodo in ["pix", "cartão", "cartao", "à vista", "a vista", "dinheiro", "sem boleto"]):
            cnt_boletos = await erp_page.locator("a:has-text('Imprimir'), a:has-text('Boleto'), a:has-text('Visualizar')").count()
            if cnt_boletos == 0:
                logging.info("  Forma de pagamento sem boleto detectada (Pix/Cartão/À vista). Contabilizando 0 boletos.")
                return 0

        locators = [
            erp_page.locator("a:has-text('Imprimir'), a:has-text('Boleto'), a:has-text('Visualizar')"),
            erp_page.locator("tr:has-text('Parcela'), tr:has-text('Duplicata')"),
            erp_page.locator("text=/parcela\\s+\\d+/i"),
        ]
        qtd_maxima = 1
        for loc in locators:
            cnt = await loc.count()
            if cnt > qtd_maxima:
                qtd_maxima = cnt
        return qtd_maxima
    except Exception as e:
        logging.warning(f"  Aviso ao contar boletos no ERP: {e}")
        return 1


def _enviar_mensagem_discord_sync(mensagem: str):
    """Envia mensagem como a SofIA (bot) via API. Fallback para webhook se não houver bot configurado."""
    texto = texto_curto(mensagem, 1900)
    payload = json.dumps({"content": texto}).encode("utf-8")
    erro_bot = None

    # Preferir API do Bot (mensagem aparece como SofIA)
    if DISCORD_BOT_TOKEN and DISCORD_NFE_REPORT_CHANNEL_ID:
        url = f"https://discord.com/api/v10/channels/{DISCORD_NFE_REPORT_CHANNEL_ID}/messages"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
                "User-Agent": "SofIA-NFe-Bot/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp.read()
            return
        except urllib.error.HTTPError as e:
            erro_bot = f"Discord Bot API retornou HTTP {e.code}"
        except Exception as e:
            erro_bot = f"Discord Bot API falhou: {e}"

    # Fallback: webhook generico
    if DISCORD_WEBHOOK_URL:
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "SofIA-NFe-Bot/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp.read()
        return

    if erro_bot:
        raise RuntimeError(f"{erro_bot}. Configure permissoes do bot no canal ou defina DISCORD_WEBHOOK_URL.")

    raise RuntimeError("Nenhum meio de envio Discord configurado (DISCORD_BOT_TOKEN+DISCORD_NFE_CHANNEL_ID ou DISCORD_WEBHOOK_URL).")


async def avisar_discord(mensagem):
    """Envia aviso pontual de erro/alerta como a SofIA."""
    if not DISCORD_BOT_TOKEN and not DISCORD_WEBHOOK_URL:
        logging.info("      [AVISO] Discord nao configurado. Defina DISCORD_BOT_TOKEN+DISCORD_NFE_CHANNEL_ID no .env.")
        return
    try:
        await asyncio.to_thread(_enviar_mensagem_discord_sync, mensagem)
        logging.info("      [DISCORD] Aviso enviado.")
    except Exception as e:
        logging.info(f"      [AVISO] Falha ao enviar aviso ao Discord: {e}")


async def sofia_relatorio(resultados: list):
    """
    Envia um relatório consolidado da rodada do cron como a SofIA.
    resultados: lista de dicts com chaves 'pedido', 'planilha', 'resultado'
    Cada pedido é exibido em sua própria linha para facilitar a leitura no Discord.
    """
    if not DISCORD_BOT_TOKEN and not DISCORD_WEBHOOK_URL:
        return

    agora = datetime.datetime.now().strftime("%d/%m/%Y às %H:%M")

    ok_lines     = []
    pulado_lines = []
    erro_lines   = []

    for r in resultados:
        pedido   = r["pedido"]
        planilha = r["planilha"]
        res      = str(r["resultado"])

        if res.startswith("OK"):
            ok_lines.append(f"✅ Pedido {pedido} — {planilha} ➔ {res}")
        elif "PULADO" in res or "Ja Faturado" in res:
            pulado_lines.append(f"⏭️ Pedido {pedido} — {planilha}")
        else:
            motivo = motivo_erro_externo(res) or texto_curto(res, 150)
            erro_lines.append(f"❌ Pedido {pedido} — {planilha}\n↳ {motivo}")

    linhas = []

    # ── Cabeçalho ──────────────────────────────────────────────────────────────
    linhas.append(f"📋 Relatório NFe — {agora}")

    # ── Sucessos ───────────────────────────────────────────────────────────────
    if ok_lines:
        linhas.append(f"✅ NFes emitidas ({len(ok_lines)})")
        linhas.extend(ok_lines)

    # ── Já faturados ───────────────────────────────────────────────────────────
    if pulado_lines:
        linhas.append(f"⏭️ Já faturados ({len(pulado_lines)})")
        linhas.extend(pulado_lines)

    # ── Erros ──────────────────────────────────────────────────────────────────
    if erro_lines:
        linhas.append(f"❌ Erros — requerem atenção ({len(erro_lines)})")
        linhas.extend(erro_lines)

    # ── Sem pendências ─────────────────────────────────────────────────────────
    if not ok_lines and not pulado_lines and not erro_lines:
        linhas.append("✅ Nenhum pedido pendente encontrado nas planilhas.")

    mensagem_final = "\n".join(linhas)
    try:
        await asyncio.to_thread(_enviar_mensagem_discord_sync, mensagem_final)
        logging.info("[DISCORD] Relatório final enviado pela SofIA.")
    except Exception as e:
        logging.info(f"[AVISO] Falha ao enviar relatório Discord: {e}")


def get_possiveis_nomes_mes_atual():
    mes = datetime.datetime.now().month
    ano = str(datetime.datetime.now().year)
    ano_curto = ano[-2:]
    nomes_por_mes = {
        1: ["JANEIRO", "JAN", "01", "1"],
        2: ["FEVEREIRO", "FEV", "02", "2"],
        3: ["MARÇO", "MARCO", "MAR", "03", "3"],
        4: ["ABRIL", "ABR", "04", "4"],
        5: ["MAIO", "MAI", "05", "5"],
        6: ["JUNHO", "JUN", "06", "6"],
        7: ["JULHO", "JUL", "07", "7"],
        8: ["AGOSTO", "AGO", "08", "8"],
        9: ["SETEMBRO", "SET", "09", "9"],
        10: ["OUTUBRO", "OUT", "10"],
        11: ["NOVEMBRO", "NOV", "11"],
        12: ["DEZEMBRO", "DEZ", "12"]
    }
    base = nomes_por_mes[mes]
    variacoes = set()
    for b in base:
        variacoes.add(b)
        variacoes.add(b.capitalize())
        variacoes.add(b.lower())
        variacoes.add(f"{b}/{ano}")
        variacoes.add(f"{b}/{ano_curto}")
        variacoes.add(f"{b.capitalize()}/{ano}")
        variacoes.add(f"{b.lower()}/{ano}")
    return list(variacoes)


def numero_antes_da_barra(texto):
    """True se houver digito(s) antes da primeira '/'."""
    if not texto or not texto.strip():
        return False
    antes = texto.strip().split("/")[0].strip()
    return bool(re.search(r"\d", antes))


def extrair_pedido(texto):
    """Retorna apenas os digitos do numero do pedido."""
    if not texto:
        return None
    # Tenta pegar a primeira sequencia de digitos (ex: 1585/2026 -> 1585)
    match = re.search(r"(\d+)", texto.strip())
    if match:
        return match.group(1)
    return None

async def fazer_login_google(page, user, password):
    """Realiza o login no Google se necessário, lidando com seleção de conta."""
    if not user or not password:
        return

    # Verificar se estamos em uma página de login ou seleção de conta
    is_login_page = "accounts.google.com" in page.url or await page.locator('input[type="email"], [data-identifier], #identifierNext').count() > 0
    
    if is_login_page:
        logging.info("      [LOGIN] Detectado necessidade de interação no Google...")
        try:
            # 1. Verificar se ja existe a conta na lista (Seleção de conta)
            conta_na_lista = page.locator(f'[data-email="{user}"], [data-identifier="{user}"]').first
            if await conta_na_lista.count() == 0:
                conta_na_lista = page.get_by_text(user).first

            if await conta_na_lista.count() > 0 and await conta_na_lista.is_visible():
                logging.info(f"      [LOGIN] Selecionando conta já listada: {user}")
                await conta_na_lista.click()
                await asyncio.sleep(2)
            
            # 2. Preencher E-mail (se campo estiver visivel)
            elif await page.locator('input[type="email"]').is_visible():
                await page.fill('input[type="email"]', user)
                await page.click('#identifierNext')
                await asyncio.sleep(2)
            
            # 3. Preencher Senha
            # Esperar o campo de senha aparecer
            try:
                await page.wait_for_selector('input[type="password"]', timeout=5000)
            except: pass

            if await page.locator('input[type="password"]').count() > 0:
                await page.fill('input[type="password"]', password)
                await page.click('#passwordNext')
                logging.info("      [LOGIN] Senha enviada. Aguardando...")
                await asyncio.sleep(5)
            
            # 4. Lidar com botões de "Continuar" ou "Confirmar"
            btn_continuar = page.locator('button:has-text("Continuar"), button:has-text("Continue"), button:has-text("Próxima")').first
            if await btn_continuar.count() > 0 and await btn_continuar.is_visible():
                await btn_continuar.click()
                await asyncio.sleep(3)

            # Se ainda estiver na página de contas, pode ser MFA
            if "accounts.google.com" in page.url:
                logging.info("      [!] Google pode estar solicitando MFA/CAPTCHA. Verifique o navegador.")
                for _ in range(30):
                    if "accounts.google.com" not in page.url: break
                    await asyncio.sleep(1)
        except Exception as e:
            logging.info(f"      [AVISO] Erro no login automático: {e}")

async def esperar_carregamento_erp(erp_page):
    """Espera que mensagens de 'Aguarde' ou overlays sumam."""
    try:
        overlay = erp_page.locator('.blockUI, .loading, :text("Aguarde"), :text("carregando")').first
        for _ in range(20):
            if await overlay.is_visible():
                await asyncio.sleep(1)
            else:
                break
    except Exception:
        pass
    await asyncio.sleep(1)

async def obter_gid_da_aba(page, url_planilha, aba, is_mes_atual=False):
    """Navega para a planilha, clica na aba e retorna o GID da URL com retentativas."""
    logging.info(f"[1/4] Abrindo planilha: {url_planilha[:50]}...")
    
    # Adicionar lógica de retentativa para abertura da planilha
    max_tentativas = 3
    for tentativa in range(max_tentativas):
        try:
            # Aumentar timeout para 60s em execuções agendadas
            await page.goto(url_planilha, timeout=60000, wait_until="load")
            break
        except Exception as e:
            if tentativa < max_tentativas - 1:
                logging.info(f"      [!] Falha na tentativa {tentativa+1}. Tentando novamente em 5s... ({e})")
                await asyncio.sleep(5)
            else:
                logging.info(f"      [ERRO] Nao foi possivel abrir a planilha apos {max_tentativas} tentativas.")
                return page, None
    
    # Tentar login se necessário
    await fazer_login_google(page, GOOGLE_USER, GOOGLE_PASS)
    
    try:
        await page.wait_for_selector(".docs-sheet-tab-name", timeout=120000)
        logging.info("      Planilha carregada!")
    except Exception:
        logging.info("      [ERRO] Timeout na planilha.")
        return page, None

    await asyncio.sleep(2)

    logging.info("[2/4] Selecionando aba alvo...")
    tabs = await page.query_selector_all(".docs-sheet-tab-name")
    nomes = []
    
    aba_selecionada = False
    
    if is_mes_atual:
        possiveis = [p.upper() for p in get_possiveis_nomes_mes_atual()]
        for tab in tabs:
            nome = (await tab.inner_text()).strip()
            nomes.append(nome)
            if nome.upper() in possiveis:
                await tab.click()
                logging.info("      Aba do mês atual '" + nome + "' selecionada.")
                aba_selecionada = True
                await asyncio.sleep(3)
                break
    else:
        for tab in tabs:
            nome = (await tab.inner_text()).strip()
            nomes.append(nome)
            aba_limpa = aba.lstrip("0")
            nome_limpo = nome.lstrip("0")
            if nome == aba or (aba_limpa != "" and aba_limpa == nome_limpo):
                await tab.click()
                logging.info(f"      Aba '{nome}' selecionada (correspondente a '{aba}').")
                aba_selecionada = True
                await asyncio.sleep(3)
                break

    if aba_selecionada:
        url_atual = page.url
        match = re.search(r"gid=(\d+)", url_atual)
        if match:
            gid = match.group(1)
            logging.info("      GID encontrado: " + gid)
            return page, gid
        else:
            logging.info("      [AVISO] GID nao encontrado na URL.")
            return page, None

    if is_mes_atual:
        logging.info("      [ERRO] Aba do mês atual não encontrada. Abas disponíveis: " + str(nomes))
    else:
        logging.info("      [ERRO] Aba '" + aba + "' nao encontrada. Abas disponíveis: " + str(nomes))
    return page, None


async def ler_dados_csv(page, url_planilha, gid):
    """Baixa o CSV da aba usando a mesma pagina para manter sessao."""
    import tempfile, os
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url_planilha)
    sheet_id = match.group(1) if match else SPREADSHEET_ID_1
    
    export_url = ("https://docs.google.com/spreadsheets/d/" + sheet_id +
                  "/export?format=csv&gid=" + gid)
    logging.info("[3/4] Baixando dados via CSV...")

    tmp_path = os.path.join(tempfile.gettempdir(), "planilha_nfe_" + gid + ".csv")
    
    # Garantir que aceitamos dialogos nesta pagina tambem (caso mude o comportamento)
    page.on("dialog", lambda dialog: dialog.accept())

    try:
        async with page.expect_download(timeout=45000) as download_info:
            try:
                await page.goto(export_url)
            except Exception as e:
                # O Playwright gera um erro proposital quando um goto vira download
                if "Download is starting" not in str(e):
                    logging.info(f"      [AVISO] Erro no goto: {e}")
        download = await download_info.value
        await download.save_as(tmp_path)
    except Exception as e:
        logging.info("      [ERRO] Download falhou: " + str(e))
        return None

    try:
        with open(tmp_path, encoding="utf-8", errors="replace") as f:
            conteudo = f.read()
    except Exception as e:
        logging.info("      [ERRO] Leitura do arquivo: " + str(e))
        return None

    linhas = []
    reader = csv.reader(io.StringIO(conteudo))
    for i, row in enumerate(reader):
        if any(cell.strip() for cell in row):
            linhas.append({"linha": i + 1, "cells": row})

    logging.info("      " + str(len(linhas)) + " linhas encontradas no CSV.")
    return linhas


async def gerar_nfe_erp(erp_page, pedido):
    """Fluxo ERP completo."""
    logging.info("\n  --- Pedido " + pedido + " ---")

    # Tentar navegar com retentativas para lidar com instabilidades de rede
    max_retries = 3
    for i in range(max_retries):
        try:
            await erp_page.goto("https://erp.admsis.com/Home?eng_tela=0103030100", timeout=60000)
            break
        except Exception as e:
            if i == max_retries - 1:
                return f"ERRO fatal ao acessar tela de NFe: {str(e)}"
            logging.info(f"      [!] Falha ao carregar tela (tentativa {i+1}). Tentando novamente em 5s... ({str(e)})")
            await asyncio.sleep(5)
            
    await asyncio.sleep(3)
    await esperar_carregamento_erp(erp_page)

    # Pesquisar
    try:
        lupa = erp_page.locator('.fa-search, .glyphicon-search, button[title*="Pesquisa"]').first
        if await lupa.count() > 0:
            await lupa.click()
            await asyncio.sleep(1)
    except Exception: pass

    # Preencher Pedido
    preencheu = False
    for seletor in ['input[id*="ped_numero"]', 'input[placeholder*="edido"]', 'input[name="ped_numero"]']:
        campo = erp_page.locator(seletor).first
        if await campo.count() > 0:
            await campo.fill(pedido)
            preencheu = True
            break
    
    if not preencheu:
        await erp_page.keyboard.press("Enter")

    # Filtrar (com timeout maior para o ADMSIS lento)
    try:
        btn_filtrar = erp_page.locator('button:has-text("FILTRAR"), button:has-text("Filtrar")').first
        await btn_filtrar.click(timeout=60000)
        logging.info("  Clicado em Filtrar.")
    except Exception as e:
        return "ERRO ao clicar Filtrar: " + str(e)
    
    await asyncio.sleep(3)
    await esperar_carregamento_erp(erp_page)

    # Abrir detalhes
    try:
        resultado = erp_page.locator("td:has-text('" + pedido + "'), tr:has-text('" + pedido + "')").first
        if await resultado.count() == 0:
            logging.info(f"  [!] Pedido {pedido} nao encontrado na grade de NFe do ERP. Provavelmente ja faturado.")
            return "PULADO - Pedido nao localizado na grade (Ja Faturado)"

        await resultado.wait_for(state="visible", timeout=10000)
        await resultado.dblclick()
        await asyncio.sleep(2)
        await esperar_carregamento_erp(erp_page)

        # Fallback se dblclick falhar
        btn_check = erp_page.get_by_text(re.compile(r"Gerar NFE", re.IGNORECASE)).first
        if not await btn_check.is_visible():
            icone = resultado.locator('a, i, button, .fa-search, .fa-edit').first
            await icone.click()
            await asyncio.sleep(3)
            await esperar_carregamento_erp(erp_page)

        boleto_existente, padrao_boleto = await boleto_ja_emitido(erp_page)
        if boleto_existente:
            logging.info(
                f"  [!] Boleto ja emitido detectado para o pedido {pedido}. "
                f"Nenhuma geracao nova sera feita. Sinal: {padrao_boleto}"
            )
            return "PULADO - Boleto ja emitido; nenhuma nova geracao feita"
        
        # --- FLUXO VITORIOSO (PADRAO 1585) ---
        # Tentar encontrar o botao GERAR NFE. Se ele existir, fazemos o processo.
        try:
            btn_gerar = erp_page.get_by_text(re.compile(r"Gerar NFE", re.IGNORECASE)).last
            
            if await btn_gerar.count() > 0 and await btn_gerar.is_visible():
                logging.info(f"  Botao Gerar NFE encontrado para o pedido {pedido}. Iniciando emissao...")
                await btn_gerar.click()
                
                # Espera dinâmica pelo botão SIM
                btn_sim = erp_page.locator('button:has-text("SIM"), button:has-text("Sim")')
                await btn_sim.wait_for(state="visible", timeout=30000)
                await btn_sim.click()
                
                await esperar_carregamento_erp(erp_page)

                # Verificar autorizacao. O ERP gera o boleto automaticamente em alguns casos.
                conteudo = (await erp_page.content()).lower()
                if any(k in conteudo for k in ["autoriza", "sucesso", "emitida"]):
                    return await gerar_boleto_se_necessario(erp_page, pedido)
                texto_tela = await erp_page.locator("body").inner_text(timeout=5000)
                return "VERIFICAR - Sem confirmacao clara. Tela ERP: " + texto_curto(texto_tela, 700)
            else:
                logging.info(f"  [!] Botao Gerar NFE nao disponivel para o pedido {pedido}. Provavelmente ja faturado.")
                return "PULADO - Ja Faturado ou Indisponivel"
        except Exception as e:
            return "ERRO no processo de geracao: " + str(e)
        # -------------------------------------
    except Exception as e:
        return "ERRO ao abrir detalhes: " + str(e)
    
    return "VERIFICAR - Sem confirmacao clara"

async def realizar_login_erp(erp_page):
    """Realiza o login no ERP se necessário."""
    logging.info("\n  [ERP] Acessando sistema...")
    try:
        await erp_page.goto(ERP_URL, timeout=90000, wait_until="load")
        
        # Verificar se ja esta logado (se ja vemos o nome do usuario ou menu)
        logging.info("      Verificando sessao ativa...")
        usuario_logado = erp_page.locator(f'text="{USUARIO}"').first
        dashboard = erp_page.locator('text="Faturamento", text="Pedidos"').first
        
        esta_logado = False
        try:
            # Esperar 5s para ver se ja carrega logado
            if await usuario_logado.count() > 0 or await dashboard.count() > 0:
                esta_logado = True
        except: pass

        if esta_logado:
            logging.info(f"      Sessao ativa detectada ({USUARIO}). Pulando login.")
            return True
        else:
            # Nao esta logado, fazer o processo normal
            logging.info("      Sessao nao encontrada. Iniciando login...")
            try:
                await erp_page.wait_for_selector('input[name="usu_codigo"]', timeout=20000)
            except Exception:
                # Tentar reload se nao aparecer nada
                await erp_page.reload()
                await erp_page.wait_for_selector('input[name="usu_codigo"]', timeout=20000)

            await erp_page.fill('input[name="usu_codigo"]', USUARIO)
            await erp_page.fill('input[name="usu_senha"]', SENHA)
            await erp_page.click('button#login')
            await asyncio.sleep(5)
            await esperar_carregamento_erp(erp_page)
            logging.info("      Login realizado com sucesso.")
            return True
        
    except Exception as e:
        logging.info(f"      [ERRO] Falha ao realizar login ERP: {e}")
        return False


async def gerar_nfe_com_tentativas(context, erp_page, item):
    pedido = item["pedido"]
    planilha = item["planilha"]
    ultimo_resultado = None
    lock_path = adquirir_lock_pedido(pedido)

    if not lock_path:
        logging.info(f"  [!] Pedido {pedido} ja esta em processamento por outra execucao. Pulando para evitar duplicidade.")
        return erp_page, "PULADO - Pedido ja em processamento por outra execucao"

    try:
        for tentativa in range(1, MAX_TENTATIVAS_GERACAO + 1):
            logging.info(f"\n  Tentativa {tentativa}/{MAX_TENTATIVAS_GERACAO} para o pedido {pedido} ({planilha})")
            try:
                ultimo_resultado = await gerar_nfe_erp(erp_page, pedido)
            except Exception as e:
                ultimo_resultado = "ERRO inesperado na automacao: " + str(e)

            logging.info(f"  Resultado Pedido {pedido} ({planilha}): {ultimo_resultado}")

            if str(ultimo_resultado).startswith("OK"):
                qtd_bol = await contar_boletos_erp(erp_page)
                database.registrar_emissao(pedido, planilha, status="OK", qtd_boletos=qtd_bol, detalhes=str(ultimo_resultado))
                return erp_page, f"{ultimo_resultado} [{qtd_bol} boleto(s)]"

            if str(ultimo_resultado).startswith("PULADO"):
                qtd_bol = await contar_boletos_erp(erp_page)
                database.registrar_emissao(pedido, planilha, status="PULADO", qtd_boletos=max(1, qtd_bol), detalhes=str(ultimo_resultado))
                return erp_page, ultimo_resultado

            motivo_externo = motivo_erro_externo(ultimo_resultado)
            if motivo_externo:
                database.registrar_emissao(pedido, planilha, status="ERRO", qtd_boletos=0, detalhes=str(motivo_externo))
                await avisar_discord(
                    f"⚠️ **NFe não gerada**\n"
                    f"📦 Pedido {pedido} — {planilha}\n"
                    f"🔎 Motivo: {motivo_externo}\n"
                    f"📄 Detalhe: {texto_curto(ultimo_resultado, 300)}"
                )
                return erp_page, ultimo_resultado

            if tentativa < MAX_TENTATIVAS_GERACAO:
                if erro_de_sessao_ou_rede(ultimo_resultado):
                    logging.info("      [!] Detectada falha de rede/sessao. Recuperando ERP antes de tentar novamente...")
                    await asyncio.sleep(10)
                    try:
                        erp_page = await context.new_page()
                        await realizar_login_erp(erp_page)
                    except Exception as e:
                        logging.info(f"      [!] Nao foi possivel recuperar a sessao ERP agora: {e}")
                else:
                    logging.info("      [!] Falha possivelmente temporaria. Tentando novamente em 5s...")
                    await asyncio.sleep(5)

        await avisar_discord(
            f"❌ **NFe não gerada após {MAX_TENTATIVAS_GERACAO} tentativas**\n"
            f"📦 Pedido {pedido} — {planilha}\n"
            f"📄 Último retorno: {texto_curto(ultimo_resultado, 300)}"
        )
        return erp_page, ultimo_resultado
    finally:
        liberar_lock_pedido(lock_path)

def limpar_locks_sessao_chrome(user_data_dir):
    """Remove symlinks de lock do Chromium se deixados por um crash anterior."""
    lock_files = ["SingletonLock", "SingletonSocket", "SingletonCookie"]
    for lock in lock_files:
        path = os.path.join(user_data_dir, lock)
        if os.path.exists(path) or os.path.islink(path):
            try:
                os.remove(path)
                logging.info(f"      [SESSAO] Symlink de lock antigo {lock} removido.")
            except Exception as e:
                logging.info(f"      [AVISO] Nao foi possivel remover {lock}: {e}")


async def main():
    if not validar_credenciais_erp():
        return

    aba_param = sys.argv[1] if len(sys.argv) > 1 else ABA_ALVO
    logging.info("=== Automacao NFe Independente ===")

    planilhas_config = [
        {
            "nome": "Planilha Principal",
            "url": SPREADSHEET_URL_1,
            "aba": aba_param,
            "is_mes_atual": False,
            "force_idx_h": None
        },
        {
            "nome": "Planilha Transporte",
            "url": SPREADSHEET_URL_2,
            "aba": None,
            "is_mes_atual": True,
            "force_idx_h": 9 # Coluna J (0-indexed)
        },
        {
            "nome": "Planilha Valdex",
            "url": SPREADSHEET_URL_3,
            "aba": aba_param,
            "is_mes_atual": False,
            "force_idx_h": 7 # Coluna H (Nota Fiscal Filial)
        }
    ]

async def main():
    if not validar_credenciais_erp():
        return

    aba_param = sys.argv[1] if len(sys.argv) > 1 else ABA_ALVO
    logging.info("=== Automacao NFe Independente ===")

    planilhas_config = [
        {
            "nome": "Planilha Principal",
            "url": SPREADSHEET_URL_1,
            "aba": aba_param,
            "is_mes_atual": False,
            "force_idx_h": None
        },
        {
            "nome": "Planilha Transporte",
            "url": SPREADSHEET_URL_2,
            "aba": None,
            "is_mes_atual": True,
            "force_idx_h": 9 # Coluna J (0-indexed)
        },
        {
            "nome": "Planilha Valdex",
            "url": SPREADSHEET_URL_3,
            "aba": aba_param,
            "is_mes_atual": False,
            "force_idx_h": 7 # Coluna H (Nota Fiscal Filial)
        }
    ]

    user_data_dir = get_user_data_dir()
    logging.info(f"      Sessao do robo em: {user_data_dir}")

    MAX_RETENTATIVAS_CICLO = 3
    INTERVALO_MINUTOS = 3

    for ciclo in range(1, MAX_RETENTATIVAS_CICLO + 1):
        etapa_atual = "Inicialização do Navegador (Playwright / Chromium)"
        limpar_locks_sessao_chrome(user_data_dir)
        
        try:
            async with async_playwright() as p:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir,
                    timeout=45000,
                    **get_browser_options()
                )
                
                page = context.pages[0] if context.pages else await context.new_page()
                page.on("dialog", lambda dialog: dialog.accept())

                todos_pendentes = []

                for p_conf in planilhas_config:
                    etapa_atual = f"Abertura e leitura da {p_conf['nome']}"
                    logging.info(f"\n--- Processando {p_conf['nome']} ---")
                    page, gid = await obter_gid_da_aba(page, p_conf['url'], p_conf['aba'], p_conf['is_mes_atual'])
                    if gid is None: 
                        continue

                    linhas = await ler_dados_csv(page, p_conf['url'], gid)
                    if linhas is None: 
                        continue

                    debug_csv = env_bool("NFE_DEBUG_CSV", False)
                    if debug_csv:
                        logging.info("\n  Depuracao de cabecalho (primeiras 3 linhas do CSV):")
                        for l in linhas[:3]:
                            logging.info(f"    L{l['linha']}: {l['cells']}")

                    idx_c, idx_h = 2, 7
                    for row in linhas:
                        if row["linha"] == 2:
                            cells = row["cells"]
                            for j, cell in enumerate(cells):
                                txt = re.sub(r"[^a-z0-9]", "", cell.lower().strip())
                                if "numeropedido" in txt or "nrpedido" in txt: 
                                    idx_c = j
                                if "notafiscalfilial" in txt or "nffilial" in txt: 
                                    idx_h = j
                            break
                    
                    if p_conf['force_idx_h'] is not None:
                        idx_h = p_conf['force_idx_h']

                    logging.info(f"\n  Iniciando analise de {len(linhas)} linhas...")
                    pendentes_planilha = 0
                    for row in linhas:
                        if row["linha"] <= 2: continue
                        
                        cells = row["cells"]
                        if len(cells) <= max(idx_c, idx_h): continue

                        val_c = cells[idx_c].strip()
                        val_h = cells[idx_h].strip()
                        
                        pedido = extrair_pedido(val_c)
                        
                        if pedido:
                            tem_nfe = numero_antes_da_barra(val_h)
                            if debug_csv:
                                status_txt = "[NFe OK]" if tem_nfe else "[PENDENTE]"
                                logging.info(f"    L{row['linha']} | Pedido: {pedido} | NFe: '{val_h}' -> {status_txt}")

                            if not tem_nfe:
                                pendentes_planilha += 1
                                logging.info(f"      [!] Adicionado a fila: {pedido}")
                                todos_pendentes.append({"pedido": pedido, "planilha": p_conf['nome']})

                    logging.info(f"  Pendentes encontrados em {p_conf['nome']}: {pendentes_planilha}")
                
                if not todos_pendentes:
                    logging.info("\n  [OK] Nada pendente em nenhuma planilha!")
                    await sofia_relatorio([])
                    await context.close()
                    return

                logging.info("\n  Pendentes totais: " + str([p["pedido"] for p in todos_pendentes]))

                etapa_atual = f"Acesso e Login no ERP ({USUARIO})"
                erp_page = await context.new_page()
                if not await realizar_login_erp(erp_page):
                    await context.close()
                    raise RuntimeError("Não foi possível realizar login no ERP.")

                resultados_finais = []
                for item in todos_pendentes:
                    etapa_atual = f"Emissão NFe do Pedido {item['pedido']} ({item['planilha']})"
                    erp_page, resultado = await gerar_nfe_com_tentativas(context, erp_page, item)
                    resultados_finais.append({
                        "pedido":   item["pedido"],
                        "planilha": item["planilha"],
                        "resultado": resultado,
                    })
                
                await sofia_relatorio(resultados_finais)

                logging.info("\n" + "="*50)
                logging.info("PROCESSAMENTO CONCLUIDO")
                logging.info("="*50)
                if sys.stdin.isatty():
                    input("\nPressione ENTER para fechar o navegador...")
                await context.close()
                return # Sucesso!
        except Exception as e:
            logging.error(f"[ERRO CRITICO] Falha na etapa '{etapa_atual}': {e}")
            if ciclo < MAX_RETENTATIVAS_CICLO:
                await avisar_discord(
                    f"⚠️ **Timeout / Falha Temporária (Tentativa {ciclo}/{MAX_RETENTATIVAS_CICLO})**\n"
                    f"📍 Etapa: {etapa_atual}\n"
                    f"📄 Detalhe: {texto_curto(str(e), 200)}\n"
                    f"⏳ Tentando novamente em {INTERVALO_MINUTOS} minutos..."
                )
                logging.info(f"      [RETENTATIVA] Aguardando {INTERVALO_MINUTOS} minutos antes da tentativa {ciclo+1}...")
                await asyncio.sleep(INTERVALO_MINUTOS * 60)
            else:
                await avisar_discord(
                    f"❌ **Falha na Execução NFe após {MAX_RETENTATIVAS_CICLO} tentativas**\n"
                    f"📍 Etapa com falha: {etapa_atual}\n"
                    f"📄 Detalhe: {texto_curto(str(e), 250)}"
                )

async def processar_pedido_avulso(pedido: str) -> str:
    if not validar_credenciais_erp():
        return "FALHA: Credenciais do ERP nao encontradas no .env."

    logging.info(f"=== Automacao NFe Avulsa: Pedido {pedido} ===")
    user_data_dir = get_user_data_dir()

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            **get_browser_options()
        )
        
        try:
            erp_page = context.pages[0] if context.pages else await context.new_page()
            erp_page.on("dialog", lambda dialog: dialog.accept())

            if not await realizar_login_erp(erp_page):
                return "FALHA: Nao foi possivel fazer login no ERP."

            item = {"pedido": pedido, "planilha": "Discord (Avulso)"}
            _, resultado = await gerar_nfe_com_tentativas(context, erp_page, item)
            
            return str(resultado)
        finally:
            await context.close()

if __name__ == "__main__":
    asyncio.run(main())
