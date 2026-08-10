# 🔧 Instalação e Execução

## Pré-requisitos

| Requisito | Versão mínima | Como verificar |
|-----------|--------------|----------------|
| Python | 3.10+ | `python3 --version` |
| pip | Qualquer | `pip3 --version` |
| macOS | 12+ | Configurações → Sobre |
| Acesso ao Discord | Token válido | Verificar `.env` |
| Acesso ao ERP ADMSIS | Usuário ativo | Verificar `.env` |

---

## 1. Clonar / Obter o Projeto

Se o projeto já existe na máquina, localize-o em:
```
/Users/nevine/Documents/nfe/
```

Se precisar clonar do Git:
```bash
git clone <URL_DO_REPOSITORIO> /Users/nevine/Documents/nfe
cd /Users/nevine/Documents/nfe
```

---

## 2. Instalar Dependências Python

```bash
cd /Users/nevine/Documents/nfe
pip3 install -r requirements.txt
```

Isso instalará:
- `playwright` — robô de navegador
- `discord.py` — bot do Discord
- `pandas` — leitura de planilhas Excel
- `python-dotenv` — carregamento do `.env`

---

## 3. Instalar os Navegadores do Playwright

Este passo é **obrigatório** e só precisa ser feito uma vez por máquina:

```bash
python3 -m playwright install chromium
```

Isso baixa o Chromium que o robô vai usar para acessar o ERP.

---

## 4. Configurar o Arquivo `.env`

Crie o arquivo de credenciais (ver [configuracao.md](configuracao.md) para detalhes de cada variável):

```bash
cp .env.example .env  # se existir exemplo
# OU crie manualmente conforme docs/configuracao.md
```

O arquivo `.env` deve estar em `/Users/nevine/Documents/nfe/.env`.

---

## 5. Executar Manualmente

### Rodar a automação completa (todas as planilhas)
```bash
cd /Users/nevine/Documents/nfe
python3 gerar_nfe_automatica.py
```
> O robô abre o Chromium (visível na tela), acessa as planilhas e o ERP, e processa os pendentes do dia.

### Rodar para um dia específico
```bash
python3 gerar_nfe_automatica.py 15
# Processa os pedidos da aba "15" (dia 15 do mês atual)
```

### Rodar o Bot Discord (SofIA)
```bash
python3 discord_bot.py
```
> Mantém o bot online para receber pedidos avulsos via Discord.

---

## 6. Verificar se Está Funcionando

```bash
# Ver o log de execução em tempo real
tail -f /Users/nevine/Documents/nfe/logs/nfe_cron.log

# Ver os agendamentos ativos
crontab -l
```

---

## 7. Configurar o Agendamento Automático (Crontab)

O sistema já está configurado. Para verificar:
```bash
crontab -l | grep nfe
```

Saída esperada:
```
50 7-17 * * 1-5 cd /Users/nevine/Documents/nfe && /usr/bin/python3 gerar_nfe_automatica.py >> /Users/nevine/Documents/nfe/logs/nfe_cron.log 2>&1
```

Para recriar caso tenha sido perdido (ver [cron.md](cron.md) para detalhes):
```bash
(crontab -l; echo "50 7-17 * * 1-5 cd /Users/nevine/Documents/nfe && /usr/bin/python3 gerar_nfe_automatica.py >> /Users/nevine/Documents/nfe/logs/nfe_cron.log 2>&1") | crontab -
```
