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

### Bot SofIA (Pedidos Avulsos + Relatórios do Cron)

| Campo | Detalhe |
|-------|---------|
| **Nome** | SofIA#7305 |
| **Objetivo** | Receber pedidos manuais de NFe + enviar relatórios automáticos do cron |
| **Autenticação** | Token do bot (`DISCORD_BOT_TOKEN`) |
| **Canal de relatórios** | Configurado via `DISCORD_CHANNEL_ID` no `.env` |
| **Biblioteca** | discord.py 2.3.2 |
| **Intents necessários** | `message_content = True` |

**Como Usar (pedido avulso):**
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

---

### Relatório Automático do Cron

Ao final de cada execução agendada, a SofIA envia um **relatório consolidado** no canal configurado. Exemplo de mensagem:

```
📋 Relatório NFe — 10/08/2026 às 11:50

✅ NFes geradas com sucesso:
• Pedido 1585 (Planilha Principal) → ✅ OK - NFe e Boleto Gerados
• Pedido 2001 (Planilha Transporte) → ✅ OK - NFe e Boleto Gerados

⏭️ Já faturados (pulados):
• Pedido 1580 (Planilha Valdex) → ⏭️ Já faturado

❌ Erros — requerem atenção:
• Pedido 1595 (Planilha Principal) → ❌ Rejeicao retornada pelo ERP/SEFAZ
```

Se não houver nenhum pedido pendente:
```
📋 Relatório NFe — 10/08/2026 às 12:50

✅ Nenhum pedido pendente encontrado nas planilhas.
```

**Prioridade de envio:**
1. **API do Bot** (mensagem aparece como SofIA) — usa `DISCORD_BOT_TOKEN` + `DISCORD_CHANNEL_ID`
2. **Webhook fallback** — usa `DISCORD_WEBHOOK_URL` (mensagem genérica, sem identidade da SofIA)
3. Se nenhum estiver configurado, apenas registra no log

---

### Alertas de Erro Pontuais

Além do relatório final, a SofIA também manda alertas imediatos quando:
- Um pedido é rejeitado pela SEFAZ (não vale tentar de novo)
- Um pedido falha em todas as 5 tentativas

**O que acontece se o Discord cair?**
- O robô tenta enviar com timeout de 20 segundos
- Se falhar, registra no log: `Falha ao enviar relatório Discord`
- A automação **continua normalmente** — o Discord é só notificação, não bloqueia o processo
