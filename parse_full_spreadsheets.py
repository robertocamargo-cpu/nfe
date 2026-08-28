import zipfile
import xml.etree.ElementTree as ET
import datetime
import collections
import re
import audit_all_sheets


def excel_date_to_str(val_str):
    if not val_str:
        return ""
    val_str = str(val_str).strip()
    if "/" in val_str:
        return val_str
    try:
        val = float(val_str)
        if val > 40000 and val < 50000:
            dt = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=val)
            return dt.strftime("%Y-%m-%d")
    except:
        pass
    return val_str


def parse_and_summarize():
    print("============================================================")
    print(" ANÁLISE COMPLETA DAS PLANILHAS COMPARTILHADAS DA EMPRESA")
    print("============================================================")

    # 1. TRANSPORTE & GNRE
    transporte_records = []
    with zipfile.ZipFile('/tmp/sheet_transporte_gnre.xlsx', 'r') as z:
        strings = audit_all_sheets.get_shared_strings(z)
        sheets_map = audit_all_sheets.get_sheets_map(z)
        for month in ['Julho', 'Agosto']:
            if month in sheets_map:
                rows = audit_all_sheets.parse_sheet_rows(z, sheets_map[month], strings)
                for r in rows[2:]:
                    raw_dt = r.get('B', '').strip() or r.get('G', '').strip()
                    dt_converted = excel_date_to_str(raw_dt)
                    pedido = r.get('C', '').strip()
                    nf = r.get('J', '').strip() or r.get('I', '').strip()
                    gnre_st = r.get('R', '').strip().upper() or r.get('Q', '').strip().upper()
                    if pedido or nf:
                        transporte_records.append({
                            "mes_aba": month,
                            "data_raw": raw_dt,
                            "data_iso": dt_converted,
                            "pedido": pedido,
                            "nf": nf,
                            "gnre_ok": (gnre_st == 'OK')
                        })

    # 2. PRINCIPAL
    principal_records = []
    with zipfile.ZipFile('/tmp/sheet_principal.xlsx', 'r') as z:
        strings = audit_all_sheets.get_shared_strings(z)
        sheets_map = audit_all_sheets.get_sheets_map(z)
        for day in [f"{i:02d}" for i in range(1, 32)]:
            if day in sheets_map:
                rows = audit_all_sheets.parse_sheet_rows(z, sheets_map[day], strings)
                for r in rows[2:]:
                    # Procura nota fiscal
                    raw_dt = r.get('B', '').strip() or r.get('A', '').strip()
                    pedido = r.get('C', '').strip()
                    nf = r.get('H', '').strip() or r.get('I', '').strip() or r.get('J', '').strip()
                    if pedido or nf:
                        principal_records.append({
                            "dia_aba": day,
                            "pedido": pedido,
                            "nf": nf
                        })

    print(f"Total de registros encontrados em Transporte/GNRE: {len(transporte_records)}")
    print(f"Total de registros encontrados em Principal: {len(principal_records)}")

    # Agrupar por datas reais em Agosto
    gnre_by_date = collections.defaultdict(int)
    nf_by_date = collections.defaultdict(int)

    for rec in transporte_records:
        d = rec['data_iso']
        if rec['gnre_ok']:
            gnre_by_date[d] += 1
        if rec['nf']:
            nf_by_date[d] += 1

    print("\n--- GNREs CONFIRMADAS NA PLANILHA POR DATA REAL ---")
    for d in sorted(gnre_by_date.keys()):
        print(f" Data {d:12}: {gnre_by_date[d]} GNREs geradas/marcadas OK")

if __name__ == "__main__":
    parse_and_summarize()
