# Automação NF-e Transporte (Automacao_NFe_Transporte)

O projeto **Automacao_NFe_Transporte** é um sistema de automação RPA (Robotic Process Automation) construído em Python. Seu objetivo principal é ler pedidos pendentes em planilhas online e emitir automaticamente as respectivas Notas Fiscais Eletrônicas (NF-e) e boletos em um sistema ERP.

## 🎯 Objetivo Principal
Cruzar dados de planilhas de controle financeiro/logístico no Google Sheets com o sistema ERP da empresa (ADMSIS). O robô identifica quais pedidos ainda não foram faturados e executa os cliques e digitações no sistema web do ERP para gerar as notas fiscais e os boletos de forma automática.

## ⚙️ Componentes e Funcionamento

### 1. Script Principal (`gerar_nfe_automatica.py`)
* **Leitura de Planilhas Google:** Ele se conecta a duas planilhas ("Planilha Principal" e "Planilha Transporte"). Usando lógicas de data, ele descobre qual é a aba alvo (ex: pelo dia atual ou pelo mês) e baixa os dados.
* **Triagem:** Lê as linhas da planilha para encontrar a coluna de "Pedidos" e a coluna de "Nota Fiscal". Se um pedido existir mas a coluna da nota fiscal estiver vazia (ou sem um número válido), ele adiciona este pedido a uma fila de pendências.
* **Automação de Navegador (Playwright):** Após listar os pendentes, o robô abre uma janela visível do navegador (Chromium):
   * Realiza login no ERP ADMSIS automaticamente (usando credenciais salvas em `.env`).
   * Acessa a tela de faturamento.
   * Para cada pedido pendente: pesquisa o número, abre os detalhes e clica nos botões **"Gerar NFE"** e **"Sim"** (para confirmar). Se for autorizado com sucesso, ele tenta também clicar no botão de gerar o **"Boleto"**.
* **Sessão e Auditoria:** Salva os cookies e sessão do navegador localmente na pasta `sessao_robo` (para evitar alertas de segurança do Google) e grava todas as interações da tela na pasta `videos/` para posterior auditoria de erros.

### 2. Script Utilitário (`search_orders.py`)
* É um script auxiliar que utiliza a biblioteca `pandas` para baixar a planilha inteira e procurar em todas as abas por números de pedidos específicos. Muito útil para tirar dúvidas rápidas sobre onde um pedido "foi parar" na planilha.

### 3. Arquivos de Configuração
* **`.env`**: Guarda as variáveis sensíveis do projeto (usuário e senha do ERP e do Google, além dos IDs das planilhas). Deve ser criado localmente.
* **`EXECUTAR_NFE.bat`**: Um atalho executável criado para facilitar a execução do robô principal com apenas dois cliques no Windows, sem precisar abrir manualmente o terminal.

## 🛠 Tecnologias e Bibliotecas Utilizadas
* **Python**: Linguagem base do projeto.
* **Playwright (`async_playwright`)**: Biblioteca de automação web utilizada para simular a navegação de um usuário humano no navegador de forma assíncrona.
* **Pandas / CSV**: Para a extração, leitura e manipulação das planilhas de dados.
* **Asyncio**: Para gerenciamento da execução assíncrona do fluxo.

## 🚀 Como Executar
1. Certifique-se de que o Python e as bibliotecas do `requirements.txt` estão instaladas (ex: `pip install playwright pandas`).
2. Instale os navegadores do Playwright usando `playwright install chromium`.
3. Verifique se o arquivo `.env` está preenchido corretamente com suas credenciais.
4. Execute rodando o arquivo `EXECUTAR_NFE.bat` ou pelo terminal executando `python gerar_nfe_automatica.py`.
