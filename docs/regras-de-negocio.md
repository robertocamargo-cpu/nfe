# 📋 Regras de Negócio

Esta seção documenta as decisões automáticas que o sistema toma — a "inteligência" da automação.

---

## 1. Qual Dia Processar (Regra das 08:50)

O sistema não processa sempre "o dia de hoje". A lógica é:

| Horário da execução | Aba processada |
|---------------------|----------------|
| Antes das 08:50 | Dia **atual** |
| 08:50 em diante | Dia **seguinte** |

**Exemplo prático:**
- Cron das 07:50 → abre a aba `10` (hoje, dia 10)
- Cron das 08:50 em diante → abre a aba `11` (amanhã, dia 11)

**Motivo:** As notas para entrega do dia seguinte precisam estar prontas ao final do expediente de hoje. Adiantar a geração garante que os documentos fiscais já estejam emitidos quando precisar.

**Código responsável:**
```python
def get_target_day():
    now = datetime.datetime.now()
    if now.hour < 8 or (now.hour == 8 and now.minute < 50):
        target_date = now
    else:
        target_date = now + datetime.timedelta(days=1)
    return target_date.strftime("%d")
```

---

## 2. Identificação de Pedidos Pendentes

Um pedido é considerado **pendente** (sem NFe) quando:

- A coluna de NFe está **vazia** (célula em branco), OU
- A célula contém `/2026` (só o complemento sem número de nota), OU
- A célula contém qualquer texto que **não comece com um número**

Um pedido é considerado **já faturado** quando:
- A coluna de NFe contém um número **antes da `/`** (ex: `1234/2026`, `5678/2027`)

**Código responsável:**
```python
def numero_antes_da_barra(texto):
    """True se houver digito(s) antes da primeira '/'."""
    antes = texto.strip().split("/")[0].strip()
    return bool(re.search(r"\d", antes))
```

**Exemplos:**
| Célula NFe | Pendente? |
|-----------|-----------|
| *(vazia)* | ✅ Sim — gerar NFe |
| `/2026` | ✅ Sim — gerar NFe |
| `1234/2026` | ❌ Não — já foi emitida |
| `9999` | ❌ Não — já tem número |

## 3. Extração do Número do Pedido

O número do pedido nas planilhas pode vir em formatos diferentes:

| Formato na planilha | Como o robô trata |
|--------------------|-------------------|
| `1585` | Usa direto: `1585` |
| `1585/2026` | Extrai apenas os dígitos: `1585` |
| `  1585  ` (com espaços) | Remove espaços: `1585` |

O robô **sempre usa apenas os dígitos** para pesquisar no ERP. O complemento `/2026` ou `/2027` é ignorado — pois a pesquisa do ERP não aceita a barra.

**Código responsável:**
```python
def extrair_pedido(texto):
    match = re.search(r"(\d+)", texto.strip())
    if match:
        return match.group(1)
    return None
```

---

## 4. Identificação de Abas por Mês

Para a Planilha de Transporte, o robô precisa encontrar a aba do mês atual. As abas podem ter vários formatos de nome:

| Mês | Nomes aceitos |
|-----|--------------|
| Janeiro | `JANEIRO`, `Janeiro`, `janeiro`, `JAN`, `01`, `1`, `JANEIRO/2026`, etc. |
| Agosto | `AGOSTO`, `Agosto`, `agosto`, `AGO`, `08`, `8`, `AGOSTO/2026`, etc. |

O sistema monta automaticamente todas as variações possíveis para o mês corrente.

---

## 5. Limite de Tentativas e Categorização de Erros

O robô diferencia dois tipos de falha:

**Falhas externas** (não adianta tentar de novo — requer intervenção humana):
- Rejeição da SEFAZ
- NFe denegada
- Problema de certificado digital
- Problema cadastral (CNPJ, inscrição estadual)
- Configuração fiscal errada (CFOP, NCM, tributação)
- Pedido já faturado

**Falhas internas** (transitórias — vale tentar de novo):
- Timeout de rede
- Browser fechado inesperadamente
- Falha ao carregar a tela do ERP
- Qualquer erro de `navigation failed`

Para **falhas internas**: tenta até **5 vezes**, com 5 segundos de espera entre tentativas.
Para **falhas externas**: para imediatamente, envia alerta no Discord e passa para o próximo pedido.

---

## 6. Regra Obrigatória de Boleto

A regra correta é: **gerar boleto quando ainda não existe, nunca gerar novamente quando já existe**.

O robô deve sempre seguir esta ordem dentro do ERP:
1. Abrir o pedido
2. Verificar sinais de boleto já emitido
3. Se boleto já existe, retornar `PULADO - Boleto ja emitido; nenhuma nova geracao feita`
4. Se boleto ainda não existe, gerar a NFe
5. Depois da autorização da NFe, verificar novamente se o boleto passou a constar no ERP
6. Se ainda não consta, clicar somente em botões explícitos de geração, como **Gerar Boleto** ou **Emitir Boleto**
7. Se não encontrar botão de boleto, retornar `VERIFICAR - NFe autorizada, mas boleto nao foi localizado/gerado`

Esta regra existe por dois motivos:
- Evitar duplicidade quando o ERP já gerou ou já registrou boleto para o pedido
- Evitar o erro oposto, como aconteceu com o pedido `3310` em `12/08/2026`, quando a NFe foi autorizada mas o boleto não foi acionado por uma proteção excessiva

Nunca substitua essa regra por "não clicar em boleto". A automação deve clicar em boleto quando ele ainda não existe e houver botão claro de geração.

Sinais usados para considerar boleto já emitido incluem:
- `boleto emitido`, `boleto gerado`, `boleto registrado`
- `2ª via do boleto` ou `segunda via do boleto`
- `linha digitável` com número
- `nosso número` com número
- ações de consulta/reemissão como `imprimir boleto`, `visualizar boleto`, `baixar boleto`, `reimprimir boleto`

---

## 7. Comportamento do Bot Discord

### Comandos reconhecidos
O bot responde quando mencionado com `@SofIA` e a mensagem contiver:
- Palavras: `crie`, `gere`, `faça`, `faca`, `gerar`, `emitir`
- E também: `nf`, `nfe`, `nota`
- E um número de pedido em qualquer lugar da mensagem

### Extração do número do pedido
- Pega o **primeiro número** encontrado na mensagem após as palavras-chave
- `@SofIA crie a NF 1585` → pedido `1585`
- `@SofIA gere a nfe 1585/2026` → pedido `1585` (ano ignorado)
- `@SofIA faca nota fiscal 1585` → pedido `1585`

### Fila de Processamento
- 1 pedido processado por vez (não sobrecarrega o ERP)
- Novos pedidos recebem confirmação com posição na fila
- Todos os pedidos da fila são processados em ordem de chegada

### Comando de parada de emergência
- `@SofIA parar` → encerra o processo imediatamente (`os._exit(1)`)
- Só é aceito no canal NFe configurado e por usuários autorizados
- Útil se o robô travar ou o browser não responder
- Após o parar, é necessário reiniciar o `discord_bot.py` manualmente

### Canais com finalidades exclusivas

A SofIA está preparada para atuar em múltiplos canais do servidor, cada um com uma responsabilidade diferente. Ela **nunca mistura** as funções entre canais.

Ao receber uma mensagem com `@SofIA`, o bot verifica **em qual canal** a mensagem foi enviada e decide o que fazer:

| Canal | Configuração | Finalidade |
|-------|--------------|-----------|
| Canal NFe | `DISCORD_NFE_CHANNEL_ID` | Emissão de Notas Fiscais Eletrônicas |
| Canal GNRE | configurado no projeto GNRE | Fora do escopo deste repositório |

| Situação | Resposta da SofIA |
|----------|------------------|
| `@SofIA crie a nf 9999` no canal NFe | ✅ Processa normalmente |
| Citar `@OutroUsuario` na conversa | 🔇 Ignora silenciosamente (a conversa não envolve a SofIA) |
| `@SofIA crie a nf 9999` em canal desconhecido | 🔇 Ignora silenciosamente |
| `@SofIA gnre ...` no canal NFe | ⚠️ Avisa que este canal é só para NFe |
| `@SofIA parar` no canal NFe | 🛑 Executa parada de emergência |
| `@SofIA parar` fora do canal NFe | 🔇 Ignora silenciosamente |

Para manter outro projeto, como GNRE, aplique o mesmo conceito no repositório correspondente:

1. Adicione a variável de ambiente no `.env`:
   ```
   DISCORD_GNRE_CHANNEL_ID=SEU_ID_AQUI
   ```
2. Mantenha a lógica de GNRE no projeto GNRE, sem importar nem acionar o motor de NFe.
3. Documente comandos, permissões e relatórios separadamente para não misturar objetivos.

---

## 8. Prioridade entre Planilhas

As planilhas são processadas nesta ordem:
1. **Planilha Principal** — pedidos do dia corrente (ou amanhã)
2. **Planilha Transporte** — pedidos do mês atual
3. **Planilha Valdex** — pedidos do dia corrente (ou amanhã)

Todos os pedidos pendentes das 3 planilhas são coletados primeiro e depois processados em sequência no ERP.

---

## 9. Exemplos com Dados Fictícios

**Cenário 1 — Execução às 07:50 do dia 10/08:**
- Abre aba `10` das planilhas Principal e Valdex
- Abre aba `AGOSTO` da planilha Transporte
- Encontra pedidos `1585` e `1590` sem NFe na Principal
- Encontra pedido `2001` sem NFe na Transporte
- Processa: `1585` → OK, `1590` → SEFAZ rejeitou (avisa Discord), `2001` → OK

**Cenário 2 — Discord às 14:30:**
- Roberto envia: `@SofIA crie a NF 9999`
- SofIA coloca `9999` na fila e confirma
- Abre ERP, pesquisa `9999`, verifica se já existe boleto, gera a NFe e gera o boleto se ele ainda não existir
- Responde: `✅ Sucesso! O pedido 9999 foi processado.`

**Cenário 3 — ERP com instabilidade:**
- Cron às 11:50 — ERP retorna timeout na tentativa 1
- Espera 5s → tenta de novo (tentativa 2) → ainda timeout
- Espera 5s → tenta de novo (tentativa 3) → OK
- Continua com os próximos pedidos normalmente
