import urllib.request
import pandas as pd

url = "https://docs.google.com/spreadsheets/d/1pVnhOWvuGKn66CmXNhEZNTPpsiQMcBUpyrYtHMcmp-g/export?format=xlsx"
urllib.request.urlretrieve(url, "planilha.xlsx")

xls = pd.ExcelFile("planilha.xlsx")
pedidos_alvo = []

print("Buscando pedidos nas abas...")
for sheet_name in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name)
    # Procurando na coluna 'Pedido' ou em todo o dataframe se necessário
    # Convertendo tudo para string para buscar
    df_str = df.astype(str)
    
    for pedido in pedidos_alvo:
        mask = df_str.apply(lambda x: x.str.contains(pedido, na=False, case=False))
        if mask.any().any():
            print(f"\n--- Pedido {pedido} encontrado na aba: {sheet_name} ---")
            # Extrair as linhas onde foi encontrado
            rows = df[mask.any(axis=1)]
            # Pegar colunas importantes se existirem (Pedido, UF, Cliente, GNRE)
            cols_to_show = []
            for col in ['Pedido', 'UF', 'Cliente', 'Transportadora', 'GNRE', 'Nota Fiscal']:
                if col in df.columns:
                    cols_to_show.append(col)
            
            if cols_to_show:
                print(rows[cols_to_show].to_string())
            else:
                print(rows.to_string())
