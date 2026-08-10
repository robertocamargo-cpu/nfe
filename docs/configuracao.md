# ⚙️ Configuração — Variáveis de Ambiente

Todas as configurações sensíveis ficam no arquivo `.env` localizado em:
```
/Users/nevine/Documents/nfe/.env
```

> [!CAUTION]
> **NUNCA** envie o arquivo `.env` para o GitHub ou compartilhe seu conteúdo. Ele contém senhas e tokens reais. O `.gitignore` já o exclui.

---

## Variáveis do Sistema

### 🔐 Credenciais do ERP ADMSIS

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `ERP_USER` | ✅ Sim | Usuário de login no ERP ADMSIS |
| `ERP_PASS` | ✅ Sim | Senha correspondente ao usuário do ERP |

```
ERP_USER=
ERP_PASS=
```

**Como obter/trocar:** Acesse o painel de usuários do ERP ADMSIS em `erp.admsis.com` com uma conta administrativa e gerencie o usuário robô.

**O que acontece se faltar:** O script aborta imediatamente com mensagem `ERRO FATAL: Credenciais do ERP não encontradas no .env!` e **não roda nenhuma automação**.

---

### 📊 Planilha Principal (Google Sheets)

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `SPREADSHEET_ID` | ✅ Sim | ID da planilha principal de pedidos |

```
SPREADSHEET_ID=
```

**Como obter:** Copie da URL da planilha:
```
https://docs.google.com/spreadsheets/d/ **[ESTE_É_O_ID]** /edit
```

> As outras 2 planilhas (Transporte e Valdex) têm seus IDs diretamente no código em `gerar_nfe_automatica.py` e podem ser atualizadas lá se necessário.

---

### 🔑 Conta Google (para autenticação na planilha)

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `GOOGLE_USER` | ⚠️ Recomendada | E-mail da conta Google com acesso às planilhas |
| `GOOGLE_PASS` | ⚠️ Recomendada | Senha da conta Google |

```
GOOGLE_USER=
GOOGLE_PASS=
```

**Nota:** O robô usa um perfil persistente de navegador (`sessao_robo`). Após o primeiro login bem-sucedido, a sessão fica salva e o robô não precisa mais dessas credenciais a cada execução. Se a sessão expirar, ele usará estas variáveis para relogar.

---

### 🤖 Discord

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `DISCORD_BOT_TOKEN` | ✅ Sim (para o bot) | Token do bot SofIA no Discord |
| `DISCORD_NFE_CHANNEL_ID` | ✅ Sim (para o bot NFe) | ID do canal onde a SofIA aceita pedidos de NFe |
| `DISCORD_NFE_REPORT_CHANNEL_ID` | ⚠️ Opcional | ID do canal onde a SofIA enviará os relatórios automáticos; se vazio, usa `DISCORD_NFE_CHANNEL_ID` |
| `DISCORD_NFE_ALLOWED_USER_IDS` | ⚠️ Opcional | IDs de usuários autorizados, separados por vírgula |
| `DISCORD_NFE_ALLOWED_ROLE_IDS` | ⚠️ Opcional | IDs de cargos autorizados, separados por vírgula |
| `DISCORD_CHANNEL_ID` | ⚠️ Legado | Alias antigo mantido por compatibilidade com `DISCORD_NFE_CHANNEL_ID` |
| `DISCORD_WEBHOOK_URL` | ⚠️ Opcional (fallback) | Webhook genérico (usado apenas se o bot não estiver configurado) |

```
DISCORD_BOT_TOKEN=
DISCORD_NFE_CHANNEL_ID=
DISCORD_NFE_REPORT_CHANNEL_ID=
DISCORD_NFE_ALLOWED_USER_IDS=
DISCORD_NFE_ALLOWED_ROLE_IDS=
DISCORD_WEBHOOK_URL=
```

**Como obter o Token:**
1. Acesse [discord.com/developers/applications](https://discord.com/developers/applications)
2. Selecione o app **SofIA**
3. Vá em **Bot** → **Reset Token**
4. Copie o novo token e cole no `.env`

**Como obter o Channel ID:**
1. No Discord, vá em **Configurações** → **Avançado** → ative **Modo Desenvolvedor**
2. Clique com o botão direito no canal desejado
3. Clique em **"Copiar ID do canal"**
4. Cole o número no `.env` como `DISCORD_NFE_CHANNEL_ID`

**Como obter User ID ou Role ID para autorização opcional:**
1. No Discord, ative **Modo Desenvolvedor**
2. Para usuário: clique com o botão direito no usuário → **Copiar ID do usuário**
3. Para cargo: abra Configurações do Servidor → Cargos → clique com o botão direito no cargo → **Copiar ID**
4. Cole no `.env`, separado por vírgula se houver mais de um

Se `DISCORD_NFE_ALLOWED_USER_IDS` e `DISCORD_NFE_ALLOWED_ROLE_IDS` ficarem vazios, qualquer pessoa com acesso ao canal NFe poderá acionar a automação.

**O que acontece se faltar o Channel ID:** O cron envia via webhook como fallback (mensagem genérica, não aparece como SofIA). Se ambos estiverem ausentes, nenhum aviso é enviado mas a automação continua funcionando normalmente.

---

### ⚡ Performance e Debug do Playwright

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `NFE_HEADLESS` | `false` | Quando `true`, roda o Chromium sem janela visível |
| `NFE_SLOW_MO_MS` | `0` | Atraso artificial entre ações do Playwright; use `200` apenas para depuração visual |
| `NFE_RECORD_VIDEO` | `false` | Quando `true`, grava vídeos em `videos/` |
| `NFE_DEBUG_CSV` | `false` | Quando `true`, registra linhas/cabeçalho da planilha no log |

Para o cron, a configuração mais leve costuma ser:
```env
NFE_HEADLESS=true
NFE_SLOW_MO_MS=0
NFE_RECORD_VIDEO=false
NFE_DEBUG_CSV=false
```

---

## Exemplo de `.env` Completo (com campos vazios)

```env
# ERP ADMSIS
ERP_USER=
ERP_PASS=

# Google Sheets
SPREADSHEET_ID=

# Google Account
GOOGLE_USER=
GOOGLE_PASS=

# Discord
DISCORD_BOT_TOKEN=
DISCORD_NFE_CHANNEL_ID=
DISCORD_NFE_REPORT_CHANNEL_ID=
DISCORD_NFE_ALLOWED_USER_IDS=
DISCORD_NFE_ALLOWED_ROLE_IDS=
DISCORD_WEBHOOK_URL=

# Performance/debug do Playwright
NFE_HEADLESS=
NFE_SLOW_MO_MS=
NFE_RECORD_VIDEO=
NFE_DEBUG_CSV=
```

---

## Onde Cada Variável é Usada

| Variável | Arquivo |
|----------|---------|
| `ERP_USER`, `ERP_PASS` | `gerar_nfe_automatica.py` — login no ERP |
| `SPREADSHEET_ID` | `gerar_nfe_automatica.py` — abre planilha principal |
| `GOOGLE_USER`, `GOOGLE_PASS` | `gerar_nfe_automatica.py` — login Google se sessão expirar |
| `DISCORD_BOT_TOKEN` | `discord_bot.py` — autenticar o bot SofIA |
| `DISCORD_NFE_CHANNEL_ID` | `discord_bot.py` e `gerar_nfe_automatica.py` — canal permitido para pedidos e relatórios NFe |
| `DISCORD_NFE_REPORT_CHANNEL_ID` | `gerar_nfe_automatica.py` — canal opcional só para relatórios NFe |
| `DISCORD_NFE_ALLOWED_USER_IDS`, `DISCORD_NFE_ALLOWED_ROLE_IDS` | `discord_bot.py` — controle opcional de autorização |
| `DISCORD_WEBHOOK_URL` | `gerar_nfe_automatica.py` — fallback para enviar alertas e relatórios |
| `NFE_HEADLESS`, `NFE_SLOW_MO_MS`, `NFE_RECORD_VIDEO`, `NFE_DEBUG_CSV` | `gerar_nfe_automatica.py` — performance e depuração |
