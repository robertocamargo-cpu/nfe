# 🔗 Integrações Externas

O sistema se comunica com 3 serviços externos: ERP ADMSIS, Google Sheets e Discord.

---

## 1. ERP ADMSIS

| Campo | Detalhe |
|-------|---------|
| **Nome** | ADMSIS ERP |
| **Objetivo** | Emitir Notas Fiscais Eletrônicas |
| **URL** | `https://erp.admsis.com/Home` |
| **Tela de NFe** | `https://erp.admsis.com/Home?eng_tela=0103030100` |
| **Autenticação** | Usuário e senha via formulário de login |
| **Método** | Playwright (automação de browser, simula cliques humanos) |

### Fluxo de Interação
1. O robô acessa a URL do ERP e verifica se já está logado
2. Se não estiver, preenche `usu_codigo` e `usu_senha` e clica em login
3. Navega para a tela de geração de NFe (`eng_tela=0103030100`)
4. Clica na lupa de pesquisa, preenche o número do pedido e clica em **Filtrar**
5. Dá duplo-clique no resultado encontrado para abrir o pedido
6. Clica no botão **Gerar NFE** e confirma com **SIM**
7. Aguarda confirmação da SEFAZ e clica em **Boleto** se autorizado

### Retornos Possíveis
| Resultado | Significado |
|-----------|-------------|
| `OK - NFe e Boleto Gerados` | ✅ Sucesso completo |
| `PULADO - Ja Faturado ou Indisponivel` | ⏭️ Pedido já tinha nota |
| `VERIFICAR - Sem confirmacao clara` | ⚠️ Emitido mas sem confirmação visual — checar manualmente |
| `FALHA: Rejeicao retornada pelo ERP/SEFAZ` | ❌ SEFAZ rejeitou — requer correção manual |
| `ERRO ao clicar Filtrar` | ❌ Timeout ou falha de rede — será retentado |

### Tolerância a Falhas
- O robô tenta até **5 vezes** por pedido antes de desistir
- Em falhas de rede/sessão, abre uma nova página do browser e refaz o login
- Em falhas da SEFAZ (rejeições), envia alerta no Discord e **não** retenta (precisa de correção)

### O que acontece se o ERP cair?
- O robô retenta 3 vezes com intervalo de 5 segundos cada
- Se ainda falhar, registra no log e envia alerta no Discord
- O pedido fica pendente e será retentado na próxima execução do cron (próxima hora)

---

## 2. Google Sheets

| Campo | Detalhe |
|-------|---------|
| **Nome** | Google Sheets |
| **Objetivo** | Ler a lista de pedidos pendentes de NFe |
| **Autenticação** | Conta Google (sessão persistente do Chromium) |
| **Método** | Playwright abre a planilha no browser; download de CSV via URL de exportação |

### Planilhas Configuradas

| Nome | ID | Aba | Coluna NFe |
|------|-----|-----|-----------|
| Planilha Principal | Configurada no `.env` via `SPREADSHEET_ID` | Número do dia (ex: `10`) | Coluna H (índice 7) — auto-detectada |
| Planilha Transporte | `1pVnhOWvuGKn66CmXNhEZNTPpsiQMcBUpyrYtHMcmp-g` | Aba do mês atual (ex: `AGOSTO`) | Coluna J (índice 9) |
| Planilha Valdex | `1hIVyui_6Ciol94CVtdhNDv7WKSkqz8lM79I0z9TvA_c` | Número do dia (ex: `10`) | Coluna H (índice 7) |

### Como o Sistema Lê os Dados
1. Abre a planilha no browser para selecionar a aba correta e obter o `GID` (ID da aba na URL)
2. Baixa os dados da aba como CSV via URL de exportação do Google Sheets
3. Analisa o CSV linha por linha a partir da linha 3 (linha 2 = cabeçalho)
4. Para cada linha, verifica se há um número de pedido e se a coluna de NFe está **vazia**
5. Adiciona à fila apenas os pedidos sem NFe

### Identificação de Pedidos sem NFe
- A coluna de NFe é considerada **preenchida** se contiver um número antes de `/` (ex: `1234/2026`)
- Planilhas que têm apenas `/2026` ou célula vazia são tratadas como **pendentes**

### O que acontece se o Google Sheets estiver indisponível?
- O robô tenta abrir a planilha até 3 vezes com intervalos de 5 segundos
- Se ainda falhar, pula aquela planilha e segue para a próxima
- Nenhum alerta é enviado para planilha indisponível (apenas registrado no log)

---

## 3. Discord

### Bot SofIA (Pedidos Avulsos)

| Campo | Detalhe |
|-------|---------|
| **Nome** | SofIA#7305 |
| **Objetivo** | Receber pedidos manuais de NFe da equipe |
| **Autenticação** | Token do bot (`DISCORD_BOT_TOKEN`) |
| **Biblioteca** | discord.py 2.3.2 |
| **Intents necessários** | `message_content = True` |

**Como Usar:**
```
@SofIA crie a NF 9999
@SofIA gere a nfe 9999
@SofIA emitir nota 9999
@SofIA parar          (cancela tudo e reinicia o bot de emergência)
```

**Sistema de Fila:**
- O bot gerencia uma fila interna (`asyncio.Queue`)
- Se a SofIA estiver processando um pedido e chegar outro, ela coloca na fila e informa a posição
- Processamento é sempre sequencial (1 pedido de cada vez) para não sobrecarregar o ERP

### Webhook de Alertas (Avisos Automáticos)

| Campo | Detalhe |
|-------|---------|
| **Objetivo** | Receber alertas do cron quando há erros ou rejeições |
| **URL** | Configurada no `.env` via `DISCORD_WEBHOOK_URL` |
| **Quando dispara** | NFe rejeitada pela SEFAZ ou falha após 5 tentativas |

**Formato das mensagens enviadas:**
```
NFe nao gerada para o pedido 9999 (Planilha Principal).
Motivo externo: Rejeicao retornada pelo ERP/SEFAZ.
Detalhe: [texto da tela do ERP]
```

**O que acontece se o Discord cair?**
- O robô tenta enviar o alerta com timeout de 20 segundos
- Se falhar, registra no log: `Falha ao enviar aviso ao Discord`
- A automação **continua normalmente** — o Discord é só notificação, não bloqueia o processo
