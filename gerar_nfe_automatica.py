import asyncio
import re
import sys
import csv
import io
import os
import datetime
from playwright.async_api import async_playwright

# Pegar o diretorio onde o script esta localizado
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
SPREADSHEET_ID_1  = os.getenv("SPREADSHEET_ID", "1YAKtpZw-1wbEPG5fTCgg-kQ0NQs3CFgbdof-IU4shEs")
SPREADSHEET_URL_1 = "https://docs.google.com/spreadsheets/d/" + SPREADSHEET_ID_1 + "/edit"

SPREADSHEET_ID_2  = "1pVnhOWvuGKn66CmXNhEZNTPpsiQMcBUpyrYtHMcmp-g"
SPREADSHEET_URL_2 = "https://docs.google.com/spreadsheets/d/" + SPREADSHEET_ID_2 + "/edit"

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
USUARIO = os.getenv("ERP_USER", "N_FERNANDO")
SENHA   = os.getenv("ERP_PASS", "FF(25)Nevine+")

GOOGLE_USER = os.getenv("GOOGLE_USER", "")
GOOGLE_PASS = os.getenv("GOOGLE_PASS", "")


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
        print("      [LOGIN] Detectado necessidade de interação no Google...")
        try:
            # 1. Verificar se ja existe a conta na lista (Seleção de conta)
            conta_na_lista = page.locator(f'[data-email="{user}"], [data-identifier="{user}"]').first
            if await conta_na_lista.count() == 0:
                conta_na_lista = page.get_by_text(user).first

            if await conta_na_lista.count() > 0 and await conta_na_lista.is_visible():
                print(f"      [LOGIN] Selecionando conta já listada: {user}")
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
                print("      [LOGIN] Senha enviada. Aguardando...")
                await asyncio.sleep(5)
            
            # 4. Lidar com botões de "Continuar" ou "Confirmar"
            btn_continuar = page.locator('button:has-text("Continuar"), button:has-text("Continue"), button:has-text("Próxima")').first
            if await btn_continuar.count() > 0 and await btn_continuar.is_visible():
                await btn_continuar.click()
                await asyncio.sleep(3)

            # Se ainda estiver na página de contas, pode ser MFA
            if "accounts.google.com" in page.url:
                print("      [!] Google pode estar solicitando MFA/CAPTCHA. Verifique o navegador.")
                for _ in range(30):
                    if "accounts.google.com" not in page.url: break
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"      [AVISO] Erro no login automático: {e}")

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
    print(f"[1/4] Abrindo planilha: {url_planilha[:50]}...")
    
    # Adicionar lógica de retentativa para abertura da planilha
    max_tentativas = 3
    for tentativa in range(max_tentativas):
        try:
            # Aumentar timeout para 60s em execuções agendadas
            await page.goto(url_planilha, timeout=60000, wait_until="load")
            break
        except Exception as e:
            if tentativa < max_tentativas - 1:
                print(f"      [!] Falha na tentativa {tentativa+1}. Tentando novamente em 5s... ({e})")
                await asyncio.sleep(5)
            else:
                print(f"      [ERRO] Nao foi possivel abrir a planilha apos {max_tentativas} tentativas.")
                return page, None
    
    # Tentar login se necessário
    await fazer_login_google(page, GOOGLE_USER, GOOGLE_PASS)
    
    try:
        await page.wait_for_selector(".docs-sheet-tab-name", timeout=120000)
        print("      Planilha carregada!")
    except Exception:
        print("      [ERRO] Timeout na planilha.")
        return page, None

    await asyncio.sleep(2)

    print("[2/4] Selecionando aba alvo...")
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
                print("      Aba do mês atual '" + nome + "' selecionada.")
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
                print(f"      Aba '{nome}' selecionada (correspondente a '{aba}').")
                aba_selecionada = True
                await asyncio.sleep(3)
                break

    if aba_selecionada:
        url_atual = page.url
        match = re.search(r"gid=(\d+)", url_atual)
        if match:
            gid = match.group(1)
            print("      GID encontrado: " + gid)
            return page, gid
        else:
            print("      [AVISO] GID nao encontrado na URL.")
            return page, None

    if is_mes_atual:
        print("      [ERRO] Aba do mês atual não encontrada. Abas disponíveis: " + str(nomes))
    else:
        print("      [ERRO] Aba '" + aba + "' nao encontrada. Abas disponíveis: " + str(nomes))
    return page, None


async def ler_dados_csv(page, url_planilha, gid):
    """Baixa o CSV da aba usando a mesma pagina para manter sessao."""
    import tempfile, os
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url_planilha)
    sheet_id = match.group(1) if match else SPREADSHEET_ID_1
    
    export_url = ("https://docs.google.com/spreadsheets/d/" + sheet_id +
                  "/export?format=csv&gid=" + gid)
    print("[3/4] Baixando dados via CSV...")

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
                    print(f"      [AVISO] Erro no goto: {e}")
        download = await download_info.value
        await download.save_as(tmp_path)
    except Exception as e:
        print("      [ERRO] Download falhou: " + str(e))
        return None

    try:
        with open(tmp_path, encoding="utf-8", errors="replace") as f:
            conteudo = f.read()
    except Exception as e:
        print("      [ERRO] Leitura do arquivo: " + str(e))
        return None

    linhas = []
    reader = csv.reader(io.StringIO(conteudo))
    for i, row in enumerate(reader):
        if any(cell.strip() for cell in row):
            linhas.append({"linha": i + 1, "cells": row})

    print("      " + str(len(linhas)) + " linhas encontradas no CSV.")
    return linhas


async def gerar_nfe_erp(erp_page, pedido):
    """Fluxo ERP completo."""
    print("\n  --- Pedido " + pedido + " ---")

    # Tentar navegar com retentativas para lidar com instabilidades de rede
    max_retries = 3
    for i in range(max_retries):
        try:
            await erp_page.goto("https://erp.admsis.com/Home?eng_tela=0103030100", timeout=60000)
            break
        except Exception as e:
            if i == max_retries - 1:
                return f"ERRO fatal ao acessar tela de NFe: {str(e)}"
            print(f"      [!] Falha ao carregar tela (tentativa {i+1}). Tentando novamente em 5s... ({str(e)})")
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
        print("  Clicado em Filtrar.")
    except Exception as e:
        return "ERRO ao clicar Filtrar: " + str(e)
    
    await asyncio.sleep(3)
    await esperar_carregamento_erp(erp_page)

    # Abrir detalhes
    try:
        resultado = erp_page.locator("td:has-text('" + pedido + "'), tr:has-text('" + pedido + "')").first
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
        
        # --- FLUXO VITORIOSO (PADRAO 1585) ---
        # Tentar encontrar o botao GERAR NFE. Se ele existir, fazemos o processo.
        try:
            btn_gerar = erp_page.get_by_text(re.compile(r"Gerar NFE", re.IGNORECASE)).last
            
            if await btn_gerar.count() > 0 and await btn_gerar.is_visible():
                print(f"  Botao Gerar NFE encontrado para o pedido {pedido}. Iniciando emissao...")
                await btn_gerar.click()
                await asyncio.sleep(2)
                await erp_page.click('button:has-text("SIM"), button:has-text("Sim")')
                await asyncio.sleep(5)
                await esperar_carregamento_erp(erp_page)

                # Verificar autorizacao e gerar boleto
                conteudo = (await erp_page.content()).lower()
                if any(k in conteudo for k in ["autoriza", "sucesso", "emitida"]):
                    print("  NFe autorizada. Gerando boleto...")
                    try:
                        btn_boleto = erp_page.get_by_text(re.compile(r"Boleto", re.IGNORECASE)).last
                        if await btn_boleto.count() > 0:
                            await btn_boleto.click()
                            print("  Clicado em Boleto.")
                            await asyncio.sleep(3)
                    except: pass
                    return "OK - NFe e Boleto Gerados"
            else:
                print(f"  [!] Botao Gerar NFE nao disponivel para o pedido {pedido}. Provavelmente ja faturado.")
                return "PULADO - Ja Faturado ou Indisponivel"
        except Exception as e:
            return "ERRO no processo de geracao: " + str(e)
        # -------------------------------------
    except Exception as e:
        return "ERRO ao abrir detalhes: " + str(e)
    
    return "VERIFICAR - Sem confirmacao clara"

async def realizar_login_erp(erp_page):
    """Realiza o login no ERP se necessário."""
    print("\n  [ERP] Acessando sistema...")
    try:
        await erp_page.goto(ERP_URL, timeout=90000, wait_until="load")
        
        # Verificar se ja esta logado (se ja vemos o nome do usuario ou menu)
        print("      Verificando sessao ativa...")
        usuario_logado = erp_page.locator(f'text="{USUARIO}"').first
        dashboard = erp_page.locator('text="Faturamento", text="Pedidos"').first
        
        esta_logado = False
        try:
            # Esperar 5s para ver se ja carrega logado
            if await usuario_logado.count() > 0 or await dashboard.count() > 0:
                esta_logado = True
        except: pass

        if esta_logado:
            print(f"      Sessao ativa detectada ({USUARIO}). Pulando login.")
            return True
        else:
            # Nao esta logado, fazer o processo normal
            print("      Sessao nao encontrada. Iniciando login...")
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
            print("      Login realizado com sucesso.")
            return True
        
    except Exception as e:
        print(f"      [ERRO] Falha ao realizar login ERP: {e}")
        return False

async def main():
    aba_param = sys.argv[1] if len(sys.argv) > 1 else ABA_ALVO
    print("=== Automacao NFe Independente ===")

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
        }
    ]

    if not os.path.exists(os.path.join(BASE_DIR, "videos")): 
        os.makedirs(os.path.join(BASE_DIR, "videos"))
    
    # Usar LOCALAPPDATA para evitar conflitos de sincronizacao do OneDrive
    local_app_data = os.getenv("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    user_data_dir = os.path.join(local_app_data, "Automacao_NFe_Transporte", "sessao_robo")
    if not os.path.exists(user_data_dir): 
        os.makedirs(user_data_dir, exist_ok=True)
    print(f"      Sessao do robo em: {user_data_dir}")

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            slow_mo=200, # Um pouco mais rapido
            viewport={"width": 1366, "height": 768},
            record_video_dir=os.path.join(BASE_DIR, "videos/")
        )
        
        # Reutilizar a primeira pagina se ja existir
        page = context.pages[0] if context.pages else await context.new_page()

        # Aceitar dialogos automaticamente (Permitir acessar outros apps, etc)
        page.on("dialog", lambda dialog: dialog.accept())

        todos_pendentes = []

        for p_conf in planilhas_config:
            print(f"\n--- Processando {p_conf['nome']} ---")
            page, gid = await obter_gid_da_aba(page, p_conf['url'], p_conf['aba'], p_conf['is_mes_atual'])
            if gid is None: 
                continue

            linhas = await ler_dados_csv(page, p_conf['url'], gid)
            if linhas is None: 
                continue

            # Mostrar as primeiras linhas para depurar cabecalho
            print("\n  Depuracao de cabecalho (primeiras 3 linhas do CSV):")
            for l in linhas[:3]:
                print(f"    L{l['linha']}: {l['cells']}")

            # Detectar indices de forma mais robusta (L2 e o cabecalho)
            idx_c, idx_h = 2, 7 # Padrao encontrado no debug
            for row in linhas:
                if row["linha"] == 2: # Linha do cabecalho
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

            print(f"\n  Iniciando analise de {len(linhas)} linhas...")
            for row in linhas:
                if row["linha"] <= 2: continue # Pular cabecalho
                
                cells = row["cells"]
                if len(cells) <= max(idx_c, idx_h): continue

                val_c = cells[idx_c].strip()
                val_h = cells[idx_h].strip()
                
                # Extrair apenas os numeros do pedido (ex: 1585/2026 -> 1585)
                pedido = extrair_pedido(val_c)
                
                if pedido:
                    tem_nfe = numero_antes_da_barra(val_h)
                    # DEBUG de cada linha para o usuario ver
                    status_txt = "[NFe OK]" if tem_nfe else "[PENDENTE]"
                    print(f"    L{row['linha']} | Pedido: {pedido} | NFe: '{val_h}' -> {status_txt}")

                    if not tem_nfe and pedido != "16":
                        print(f"      [!] Adicionado a fila: {pedido}")
                        todos_pendentes.append({"pedido": pedido, "planilha": p_conf['nome']})
        
        if not todos_pendentes:
            print("\n  [OK] Nada pendente em nenhuma planilha!")
            await context.close()
            return

        print("\n  Pendentes totais: " + str([p["pedido"] for p in todos_pendentes]))

        erp_page = await context.new_page()
        if not await realizar_login_erp(erp_page):
            await context.close()
            return

        for item in todos_pendentes:
            try:
                # Resetar estado da pagina ou navegar novamente se necessario
                res = await gerar_nfe_erp(erp_page, item["pedido"])
                print(f"  Resultado Pedido {item['pedido']} ({item['planilha']}): {res}")
            except Exception as e:
                msg_erro = str(e).lower()
                print(f"  Erro no pedido {item['pedido']}: {str(e)}")
                
                # Se o erro for de suspensao de rede, fechamento de pagina ou falha grave de navegacao
                if any(k in msg_erro for k in ["closed", "network_io_suspended", "navigation failed", "connection refused"]):
                    print("      [!] Detectada falha de rede ou sessao. Tentando recuperar...")
                    await asyncio.sleep(10) # Esperar um pouco para a rede voltar
                    try:
                        erp_page = await context.new_page()
                        await realizar_login_erp(erp_page)
                    except:
                        print("      [!] Nao foi possivel recuperar a sessao ERP.")
        
        print("\n" + "="*50)
        print("PROCESSAMENTO CONCLUIDO")
        print("="*50)
        input("\nPressione ENTER para fechar o navegador...")
        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
