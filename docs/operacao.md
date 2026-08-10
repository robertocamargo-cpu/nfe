# 🛠️ Operação e Manutenção

## Onde Consultar Logs

```bash
# Log completo de execução (automático + avulso)
cat /Users/nevine/Documents/nfe/logs/nfe_cron.log

# Últimas 100 linhas (mais prático)
tail -100 /Users/nevine/Documents/nfe/logs/nfe_cron.log

# Acompanhar em tempo real (útil ao rodar manualmente)
tail -f /Users/nevine/Documents/nfe/logs/nfe_cron.log
```

---

## Como Identificar Problemas

### 1. Pedido Não Gerado — Ver o Motivo

```bash
grep "9999" /Users/nevine/Documents/nfe/logs/nfe_cron.log
# Substitua 9999 pelo número do pedido
```

### 2. Ver Todos os Erros do Dia

```bash
grep -i "ERRO\|FALHA\|VERIFICAR" /Users/nevine/Documents/nfe/logs/nfe_cron.log | grep "$(date '+%Y-%m-%d')"
```

### 3. Confirmar que o Cron Rodou Hoje

```bash
grep "Automacao NFe Independente" /Users/nevine/Documents/nfe/logs/nfe_cron.log | tail -5
```

---

## Erros Conhecidos e Soluções

| Erro | Causa | Solução |
|------|-------|---------|
| `ERRO FATAL: Credenciais do ERP não encontradas no .env!` | `.env` está faltando ou sem `ERP_USER`/`ERP_PASS` | Preencher o `.env` corretamente |
| `TimeoutError: waiting for selector` | ERP ou Google Sheets demorou além de 60s para carregar | Verificar a internet e o ERP. O cron tentará de novo na próxima hora |
| `Browser has been closed` | Sessão do Chromium corrompida | Deletar a pasta de sessão (ver abaixo) |
| `network_io_suspended` | Mac entrou em hibernação durante execução | Desabilitar o modo de suspensão automática nas Preferências |
| `Rejeicao retornada pelo ERP/SEFAZ` | Problema fiscal no pedido (NCM, CFOP, cadastro) | Requer correção manual no ERP — o robô não pode resolver |
| `VERIFICAR - Sem confirmacao clara` | NFe possivelmente emitida mas a tela não mostrou confirmação clara | Verificar manualmente no ERP se a NFe foi gerada |
| Bot do Discord offline | Token expirou ou máquina reiniciou | Reiniciar o `discord_bot.py` e/ou renovar token |

### Limpar Sessão do Browser (resolver crashes do Playwright)

```bash
rm -rf ~/Library/Application\ Support/Automacao_NFe_Transporte/sessao_robo/
# Na próxima execução o robô fará login novamente
```

---

## Como Reiniciar o Bot do Discord

```bash
# Verificar se o bot está rodando
ps aux | grep discord_bot

# Matar o processo se necessário
kill $(ps aux | grep "discord_bot.py" | grep -v grep | awk '{print $2}')

# Iniciar novamente
cd /Users/nevine/Documents/nfe
nohup python3 discord_bot.py > logs/bot_discord.log 2>&1 &
```

---

## Como Reprocessar um Pedido Manualmente

Se um pedido foi pulado ou falhou e você quer forçar:

**Via Discord (recomendado):**
```
@SofIA crie a NF 9999
```

**Via terminal:**
```bash
# Não existe comando direto para pedido avulso via linha de comando.
# Use o Discord com @SofIA ou edite temporariamente a planilha para
# deixar a célula de NFe vazia e rode o cron manualmente.
python3 gerar_nfe_automatica.py
```

---

## Rotinas de Manutenção Periódica

### Semanal
- [ ] Verificar o log por erros recorrentes: `grep "FALHA\|VERIFICAR" logs/nfe_cron.log`
- [ ] Confirmar que o bot Discord está online (teste com `@SofIA crie a NF 1`)

### Mensal
- [ ] Verificar o tamanho do log: `du -sh logs/nfe_cron.log`
- [ ] Arquivar logs antigos se necessário:
  ```bash
  gzip logs/nfe_cron.log
  # O sistema criará um novo arquivo na próxima execução
  ```
- [ ] Limpar vídeos antigos do robô:
  ```bash
  ls -lh videos/   # ver tamanho
  rm videos/*.webm  # apagar se não precisar
  ```

### Anual (Virada de Ano)
- A variável `ABA_ALVO` usa o número do dia, mas o complemento padrão de pedidos muda de `/2026` para `/2027`.
- **Nenhuma alteração no código é necessária** — o bot ignora o ano e usa apenas os dígitos do pedido.
- Verificar se as planilhas do Google Sheets ganharam novas abas para o novo ano.

---

## Responsáveis e Suporte

| Papel | Contato |
|-------|---------|
| Responsável técnico | Equipe TI / Desenvolvedor |
| Responsável operacional | Equipe Financeira/Administrativa |
| Suporte ERP ADMSIS | Suporte do fornecedor do ERP |
| Suporte Discord | discord.com/support |

---

## Plano de Recuperação

### O Mac foi reiniciado e o bot do Discord parou
1. Abrir terminal
2. `cd /Users/nevine/Documents/nfe`
3. `python3 discord_bot.py &` — rodar em background

### O Cron parou de executar sem motivo
1. Verificar: `crontab -l` — se vazio, o cron foi apagado
2. Recriar: ver seção de instalação em [instalacao.md](instalacao.md)
3. Verificar permissão de Acesso Total ao Disco (ver [cron.md](cron.md))

### A sessão do ERP está presa/corrompida
1. `rm -rf ~/Library/Application\ Support/Automacao_NFe_Transporte/sessao_robo/`
2. Rodar `python3 gerar_nfe_automatica.py` manualmente para refazer o login

### Uma NFe não foi gerada e está urgente
1. `@SofIA crie a NF XXXX` no Discord
2. OU acesse o ERP manualmente e gere a nota
