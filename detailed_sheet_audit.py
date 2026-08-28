import zipfile
import xml.etree.ElementTree as ET
import re
import collections
import audit_all_sheets


def detailed_audit():
    print("============================================================")
    print(" AUDITORIA COMPLETA DAS PLANILHAS DE VENDAS E FATURAMENTO")
    print("============================================================")

    # 1. Audit Transporte / GNRE
    with zipfile.ZipFile('/tmp/sheet_transporte_gnre.xlsx', 'r') as z:
        strings = audit_all_sheets.get_shared_strings(z)
        sheets_map = audit_all_sheets.get_sheets_map(z)

        print("\n--- PLANILHA TRANSPORTE & GNRE ---")
        for month in ['Julho', 'Agosto']:
            if month not in sheets_map:
                continue
            rows = audit_all_sheets.parse_sheet_rows(z, sheets_map[month], strings)
            
            # Contagem por data em Agosto/Julho
            by_date = collections.defaultdict(list)
            gnre_ok_by_date = collections.defaultdict(list)

            for r in rows[2:]:
                # Data costuma estar na Coluna B (ou C/H)
                dt = r.get('B', '').strip() or r.get('G', '').strip() or r.get('H', '').strip()
                pedido = r.get('C', '').strip()
                nf = r.get('J', '').strip() or r.get('I', '').strip()
                gnre_st = r.get('R', '').strip().upper() or r.get('Q', '').strip().upper()

                if pedido or nf:
                    by_date[dt].append((pedido, nf, gnre_st))
                    if gnre_st == 'OK':
                        gnre_ok_by_date[dt].append((pedido, nf))

            print(f"\n[Aba {month}] Resumo das datas com NF e GNRE OK:")
            total_nf_month = sum(len(v) for v in by_date.values())
            total_gnre_month = sum(len(v) for v in gnre_ok_by_date.values())
            print(f" Total de NFs/Pedidos na planilha em {month}: {total_nf_month}")
            print(f" Total de GNREs concluídas (OK) em {month}: {total_gnre_month}")

            for dt in sorted(by_date.keys()):
                if dt:
                    nfs_count = len(by_date[dt])
                    gnre_count = len(gnre_ok_by_date[dt])
                    print(f"   Data {dt:12}: {nfs_count:3d} Pedidos/NFs | GNREs OK: {gnre_count:2d}")

if __name__ == "__main__":
    detailed_audit()
