# 🔒 Segurança

## Modelo de Segurança

Este sistema roda **localmente** em um Mac (sem exposição à internet). Não há servidor web, não há porta aberta, não há endpoint público. O único vetor de entrada externo é o bot do Discord.

---

## Autenticação

### ERP ADMSIS
- O robô faz login com usuário (`ERP_USER`) e senha (`ERP_PASS`) definidos no `.env`.
- A sessão é **persistida** no diretório:
  ```
  ~/Library/Application Support/Automacao_NFe_Transporte/sessao_robo/
  ```
- O Playwright reutiliza essa sessão a cada execução, evitando logar repetidamente.
- Se a sessão expirar, o sistema refaz o login automaticamente.

### Google Sheets
- Autenticação via conta Google armazenada no mesmo perfil persistente do Chromium.
- As credenciais `GOOGLE_USER` e `GOOGLE_PASS` no `.env` são usadas apenas como fallback se a sessão expirar.

### Discord (Bot SofIA)
- O bot autentica via `DISCORD_BOT_TOKEN` no arquivo `.env`.
- Tokens do Discord expiram se o bot for reiniciado da plataforma ou se o token for revogado manualmente.
- O primeiro controle de acesso é o **canal NFe** (`DISCORD_NFE_CHANNEL_ID`).
- Opcionalmente, o bot também restringe por usuários (`DISCORD_NFE_ALLOWED_USER_IDS`) ou cargos (`DISCORD_NFE_ALLOWED_ROLE_IDS`).
- Canais de outros projetos, como GNRE, devem ter automações próprias e não devem chamar a automação deste repositório.

---

## Controle de Acesso

| Quem | O que pode fazer |
|------|-----------------|
| Usuários autorizados no canal NFe | Solicitar geração de NFe avulsa (`@SofIA crie a NF XXXX`) |
| Usuários autorizados no canal NFe | Parar o robô de emergência (`@SofIA parar`) |
| Acesso ao Mac (local) | Tudo — executar scripts, alterar `.env`, reiniciar o cron |

> **Decisão de design:** O bot ignora silenciosamente canais não configurados. Dentro do canal NFe, a autorização por cargo/usuário é opcional, mas recomendada para produção.

---

## Dados Sensíveis Tratados

| Dado | Onde Fica | Proteção |
|------|-----------|---------|
| Senha do ERP | `.env` | Arquivo local, no `.gitignore` |
| Senha do Google | `.env` | Arquivo local, no `.gitignore` |
| Token do Discord Bot | `.env` | Arquivo local, no `.gitignore` |
| URL do Webhook Discord | `.env` | Arquivo local, no `.gitignore` |
| Sessão do Chromium | `~/Library/...sessao_robo/` | Diretório local, sem sincronização |
| Números de pedidos | Logs (`logs/nfe_cron.log`) | Arquivo local apenas |

---

## Proteção de Credenciais

### O que já está feito ✅
- Nenhuma senha ou token está escrito diretamente no código-fonte
- Todos os segredos estão no `.env`
- O `.gitignore` exclui o `.env` do controle de versão
- Se o `.env` não tiver as credenciais do ERP, o sistema **se recusa a iniciar**

### O que NUNCA fazer ❌
- Não adicione senhas como valor padrão em `os.getenv("VAR", "senha_aqui")`
- Não compartilhe o arquivo `.env` por e-mail, WhatsApp ou Slack
- Não commite o `.env` no GitHub (verifique com `git status` antes de `git push`)

---

## Logs e Auditoria

- Todas as ações do robô são registradas em `logs/nfe_cron.log` com timestamp
- Formato: `2026-08-10 12:00:00,000 [INFO] Mensagem`
- O log nunca registra senhas ou tokens — apenas pedidos, resultados e erros
- Por padrão, o bot não registra o texto completo das mensagens recebidas no Discord
- Por padrão, o cron não registra todas as linhas da planilha; `NFE_DEBUG_CSV=1` ativa esse detalhe para investigação
- Os vídeos em `videos/` gravam visualmente o que o robô fez e podem conter dados fiscais. Use `NFE_RECORD_VIDEO=1` apenas para debug e remova gravações antigas periodicamente.

---

## Procedimento em Caso de Vazamento de Credencial

### Se a senha do ERP for comprometida:
1. Acesse o ERP ADMSIS como administrador
2. Altere a senha do usuário `N_ROBOTRON` (ou o que estiver em `ERP_USER`)
3. Atualize o `ERP_PASS` no arquivo `.env`
4. Reinicie o bot do Discord se estiver rodando

### Se o Token do Discord for comprometido:
1. Acesse [discord.com/developers/applications](https://discord.com/developers/applications)
2. Vá em **Bot** → **Reset Token** — isso invalida o token antigo imediatamente
3. Copie o novo token
4. Atualize `DISCORD_BOT_TOKEN` no `.env`
5. Reinicie o `discord_bot.py`

### Se o Webhook do Discord for comprometido:
1. No servidor do Discord → Canal → Integrações → Webhooks
2. Delete o webhook comprometido
3. Crie um novo webhook
4. Atualize `DISCORD_WEBHOOK_URL` no `.env`

### Se a conta Google for comprometida:
1. Acesse a conta Google e altere a senha
2. Atualize `GOOGLE_PASS` no `.env`
3. Delete a sessão salva para forçar novo login:
   ```bash
   rm -rf ~/Library/Application\ Support/Automacao_NFe_Transporte/sessao_robo/
   ```
4. Na próxima execução o robô fará login novamente

---

## Atualização de Dependências Vulneráveis

Para verificar e atualizar:
```bash
cd /Users/nevine/Documents/nfe
pip3 list --outdated
pip3 install --upgrade playwright discord.py pandas python-dotenv
```

Após atualizar, verifique se o `requirements.txt` reflete as versões novas:
```bash
pip3 freeze | grep -E "playwright|discord|pandas|dotenv" > requirements.txt
```

Sempre teste a automação manualmente após atualizar o Playwright.
