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
| `DISCORD_CHANNEL_ID` | ✅ Sim (para relatórios do cron) | ID do canal onde a SofIA enviará os relatórios automáticos |
| `DISCORD_WEBHOOK_URL` | ⚠️ Opcional (fallback) | Webhook genérico (usado apenas se o bot não estiver configurado) |

```
DISCORD_BOT_TOKEN=
DISCORD_CHANNEL_ID=
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
4. Cole o número no `.env` como `DISCORD_CHANNEL_ID`

**O que acontece se faltar o Channel ID:** O cron envia via webhook como fallback (mensagem genérica, não aparece como SofIA). Se ambos estiverem ausentes, nenhum aviso é enviado mas a automação continua funcionando normalmente.

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
DISCORD_WEBHOOK_URL=
```

---

## Onde Cada Variável é Usada

| Variável | Arquivo |
|----------|---------|
| `ERP_USER`, `ERP_PASS` | `gerar_nfe_automatica.py` — login no ERP |
| `SPREADSHEET_ID` | `gerar_nfe_automatica.py` — abre planilha principal |
| `GOOGLE_USER`, `GOOGLE_PASS` | `gerar_nfe_automatica.py` — login Google se sessão expirar |
| `DISCORD_BOT_TOKEN` | `discord_bot.py` — autenticar o bot SofIA |
| `DISCORD_WEBHOOK_URL` | `gerar_nfe_automatica.py` — enviar alertas de erro |
