# 🕒 Cron e Agendamentos

## Visão Geral

O sistema usa o **Crontab nativo do macOS** para agendar a execução automática. Não há servidor de tarefas externo.

**Fuso Horário:** America/Sao_Paulo (Brasília — UTC-3)

---

## Tarefas Agendadas

### Tarefa 1: Geração Automática de NFe

| Campo | Valor |
|-------|-------|
| **Nome** | Automação NFe Cron |
| **Script** | `gerar_nfe_automatica.py` |
| **Frequência** | De hora em hora, das 07:50 às 17:50 |
| **Dias** | Segunda a Sexta (1-5) |
| **Expressão Cron** | `50 7-17 * * 1-5` |
| **Fuso** | macOS local (America/Sao_Paulo) |

**Linha exata no crontab:**
```
50 7-17 * * 1-5 cd /Users/nevine/Documents/nfe && /usr/bin/python3 gerar_nfe_automatica.py >> /Users/nevine/Documents/nfe/logs/nfe_cron.log 2>&1
```

**O que o cron faz a cada hora:**
1. Abre as 3 planilhas do Google Sheets
2. Identifica pedidos sem NFe para o dia corrente (ou próximo, dependendo do horário)
3. Acessa o ERP ADMSIS e gera as notas pendentes
4. Registra todos os resultados no log
5. Envia alerta no Discord se algum pedido falhar

**Dados processados:** Pedidos comerciais das planilhas Principal, Transporte e Valdex.

---

## Regra de Horário Especial

> A partir das **08:50**, o robô passa a trabalhar com os pedidos do **dia seguinte** (adiantando para ter os dados prontos para o próximo dia útil).

Isso significa:
- Execuções às **07:50** → processa pedidos de **hoje** (aba do dia atual)
- Execuções das **08:50 em diante** → processa pedidos de **amanhã** (aba do dia seguinte)

---

## O que Acontece em Caso de Erro?

| Situação | Comportamento |
|----------|---------------|
| Falha de rede com o ERP | Retenta até 3 vezes, com 5s de espera |
| Rejeição da SEFAZ | Alerta no Discord, pula para o próximo pedido |
| Planilha indisponível | Pula aquela planilha e segue com as demais |
| Falha após 5 tentativas | Alerta no Discord com detalhes do erro |
| Mac desligado no horário | O cron não executa. A próxima hora compensará os pendentes |

---

## Como Verificar se o Cron Foi Executado

```bash
# Ver as últimas 50 linhas do log
tail -50 /Users/nevine/Documents/nfe/logs/nfe_cron.log

# Buscar os starts de execução de hoje
grep "Automacao NFe Independente" /Users/nevine/Documents/nfe/logs/nfe_cron.log | tail -10

# Buscar erros nas últimas 24h
grep -i "ERRO\|FALHA\|VERIFICAR" /Users/nevine/Documents/nfe/logs/nfe_cron.log | tail -20
```

---

## Como Executar Manualmente (Fora do Agendamento)

```bash
cd /Users/nevine/Documents/nfe

# Processar o dia automático (hoje ou amanhã conforme regra das 08:50)
python3 gerar_nfe_automatica.py

# Processar dia específico (ex: dia 15)
python3 gerar_nfe_automatica.py 15
```

---

## Gerenciar o Agendamento

```bash
# Ver todos os crons ativos
crontab -l

# Editar os crons
crontab -e

# Remover TODOS os crons (cuidado!)
crontab -r

# Verificar se o cron está ativo no macOS
launchctl list | grep cron
```

---

## Verificação do Cron no macOS

No macOS, o Crontab requer permissão de **Acesso Total ao Disco** (Full Disk Access) para funcionar. Se o cron parar de executar sem motivo aparente:

1. Abra **Preferências do Sistema** → **Privacidade e Segurança** → **Acesso Total ao Disco**
2. Verifique se `/usr/sbin/cron` está na lista e habilitado
3. Se não estiver, clique em `+` e adicione `/usr/sbin/cron`
