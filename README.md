# 📦 Sistema de Automação de NFe — Documentação Completa

> Sistema de geração automática de Notas Fiscais Eletrônicas integrado ao ERP ADMSIS, Google Sheets e Discord.

---

## 📋 Índice

| Documento | Conteúdo |
|-----------|----------|
| [Visão Geral](#-visão-geral) | O que é, quem usa, o que faz |
| [Arquitetura](#-arquitetura) | Tecnologias e fluxo de dados |
| [Instalação e Execução](docs/instalacao.md) | Como configurar e rodar |
| [Variáveis de Ambiente](docs/configuracao.md) | O que colocar no `.env` |
| [Segurança](docs/seguranca.md) | Credenciais, acesso e proteção |
| [Integrações Externas](docs/integracoes.md) | ERP, Google, Discord |
| [Cron e Agendamentos](docs/cron.md) | Execuções automáticas |
| [Operação e Manutenção](docs/operacao.md) | Como monitorar e resolver problemas |
| [Regras de Negócio](docs/regras-de-negocio.md) | Lógica de decisão do sistema |

---

## 🎯 Visão Geral

### Nome do Sistema
**Automação NFe Nevine** — Sistema RPA (Robotic Process Automation) de emissão de Notas Fiscais.

### Objetivo Principal
Eliminar o trabalho manual de entrar no ERP ADMSIS, pesquisar cada pedido e clicar em "Gerar NFE". O sistema faz isso automaticamente, todos os dias, varrendo as planilhas de pedidos e acionando o ERP para cada um que ainda não tem nota fiscal emitida.

### Problema que Resolve
A equipe financeira precisava abrir o ERP manualmente várias vezes ao dia, buscar pedido por pedido e emitir a nota. Com dezenas de pedidos diários vindos de múltiplas planilhas, o processo consumia horas de trabalho humano e estava sujeito a erros e esquecimentos.

### Quem Utiliza
- **Equipe Financeira/Administrativa** — solicita geração avulsa de notas pelo Discord
- **Sistema Automatizado (Cron)** — roda sozinho a cada hora, de segunda a sexta

### Principais Funcionalidades
- ✅ Varredura automática de 3 planilhas do Google Sheets (Principal, Transporte e Valdex)
- ✅ Identificação de pedidos **sem nota fiscal** ainda pendentes
- ✅ Acesso automatizado ao ERP ADMSIS via Playwright (robô de navegador)
- ✅ Emissão da NFe e geração do Boleto em sequência
- ✅ Bot Discord **SofIA** para solicitação avulsa (`@SofIA crie a NF 9999`)
- ✅ Sistema de fila no Discord (vários pedidos simultâneos processados em ordem)
- ✅ Alertas de erro via webhook do Discord
- ✅ Rejeição automática (tenta até 5 vezes antes de desistir)
- ✅ Persistência de sessão do navegador (reutiliza login entre execuções)

### O que o Sistema NÃO Faz
- ❌ Não emite boletos para notas já faturadas
- ❌ Não resolve rejeições da SEFAZ (esses precisam de correção manual)
- ❌ Não gerencia o cadastro de clientes/produtos no ERP
- ❌ Não tem interface web ou painel de controle

### Repositório no GitHub
> 🔗 Consulte a equipe responsável para obter o link do repositório privado.

---

## 🏗️ Arquitetura

### Tecnologias Utilizadas

| Camada | Tecnologia | Versão |
|--------|-----------|--------|
| Linguagem | Python | 3.x |
| Automação do Browser | Playwright (Chromium) | 1.42.0 |
| Bot Discord | discord.py | 2.3.2 |
| Leitura de Planilhas | pandas (xlsx) | 2.2.1 |
| Segredos | python-dotenv | 1.0.1 |
| Agendamento | macOS Crontab | nativo |

### Não há:
- Banco de dados relacional
- Back-end web (Flask, FastAPI, etc.)
- Vercel / Heroku / deploy em nuvem
- Front-end

O sistema roda **inteiramente na máquina local (Mac)** da Nevine.

### Fluxo Geral dos Dados

```
MODO AUTOMÁTICO (Cron a cada hora):
  Crontab (Mac)
      │
      └─► gerar_nfe_automatica.py
              │
              ├─► Google Sheets ─── lê os pedidos sem NFe das 3 planilhas
              │
              └─► Playwright (Chromium headless)
                      │
                      ├─► Login no ERP ADMSIS (erp.admsis.com)
                      ├─► Pesquisa o pedido
                      ├─► Clica em "Gerar NFe" → confirma
                      └─► Clica em "Gerar Boleto"
                              │
                              └─► Discord Webhook (avisa se houver erro)

MODO AVULSO (Bot Discord):
  Usuário no Discord
      │  (@SofIA crie a NF 9999)
      ▼
  discord_bot.py (SofIA#7305)
      │
      ├─► Coloca o pedido na Fila (asyncio.Queue)
      │
      └─► Worker da Fila
              │
              └─► processar_pedido_avulso()
                      │
                      └─► (mesmo fluxo ERP acima)
                              │
                              └─► Responde no Discord ✅ ou ❌
```

### Arquivos do Projeto

```
nfe/
├── .env                        # 🔐 Credenciais (NUNCA compartilhar)
├── .gitignore                  # Regras do Git
├── README.md                   # Este arquivo
├── discord_bot.py              # Bot Discord SofIA
├── gerar_nfe_automatica.py     # Motor principal da automação
├── search_orders.py            # Script utilitário de pesquisa
├── requirements.txt            # Dependências Python
├── nfe.code-workspace          # Config do VSCode
├── logs/
│   └── nfe_cron.log            # Histórico completo de execuções
├── docs/                       # Documentação detalhada
│   ├── instalacao.md
│   ├── configuracao.md
│   ├── seguranca.md
│   ├── integracoes.md
│   ├── cron.md
│   ├── operacao.md
│   └── regras-de-negocio.md
└── videos/                     # Gravações do robô (geradas pelo Playwright)
```
