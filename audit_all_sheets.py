import zipfile
import xml.etree.ElementTree as ET
import collections
import re


def get_shared_strings(z):
    strings = []
    if 'xl/sharedStrings.xml' in z.namelist():
        root = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for elem in root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
            # Text can be in <t> or nested in <r><t>
            text_parts = []
            for t_elem in elem.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t'):
                if t_elem.text:
                    text_parts.append(t_elem.text)
            strings.append("".join(text_parts))
    return strings


def get_sheets_map(z):
    wb_root = ET.fromstring(z.read('xl/workbook.xml'))
    sheets = []
    for elem in wb_root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet'):
        name = elem.attrib.get('name')
        rId = elem.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        sheets.append((name, rId))

    rels_root = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    rel_map = {}
    for elem in rels_root.iter('{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
        rel_map[elem.attrib.get('Id')] = elem.attrib.get('Target')

    res = {}
    for name, rId in sheets:
        target = rel_map.get(rId)
        if target:
            res[name] = 'xl/' + target if not target.startswith('xl/') else target
    return res


def parse_sheet_rows(z, sheet_path, strings):
    if sheet_path not in z.namelist():
        return []
    root = ET.fromstring(z.read(sheet_path))
    rows = []
    for row_elem in root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
        row_cells = {}
        for c_elem in row_elem.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
            ref = c_elem.attrib.get('r', '') # e.g. A1, B2
            t = c_elem.attrib.get('t', '')
            val_elem = c_elem.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
            val = val_elem.text if val_elem is not None else ''

            if t == 's' and val.isdigit():
                idx = int(val)
                val = strings[idx] if idx < len(strings) else ''

            col_letters = "".join(re.findall(r'[A-Z]', ref))
            row_cells[col_letters] = val
        rows.append(row_cells)
    return rows


def audit():
    print("============================================================")
    print(" AUDITORIA PROFUNDA DE PLANILHAS (NFE, BOLETOS, GNRE)")
    print("============================================================")

    # 1. Audit Transporte / GNRE
    with zipfile.ZipFile('/tmp/sheet_transporte_gnre.xlsx', 'r') as z:
        strings = get_shared_strings(z)
        sheets_map = get_sheets_map(z)

        print("\n--- PLANILHA TRANSPORTE / GNRE ---")
        for month_tab in ['Julho', 'Agosto']:
            if month_tab in sheets_map:
                rows = parse_sheet_rows(z, sheets_map[month_tab], strings)
                print(f"\nAba {month_tab}: {len(rows)} linhas no total")
                
                # Exibir cabeçalho
                if rows:
                    print("  Exemplo Linha 1/2:", list(rows[0].values())[:10])
                
                # Contar pedidos, NFes, GNRE status
                ok_gnre = 0
                com_nf = 0
                for r in rows[2:]:
                    # Coluna NF e Pedido e Status GNRE
                    values_str = " | ".join(r.values()).upper()
                    if "OK" in r.get('R', '').upper() or "OK" in r.get('Q', '').upper():
                        ok_gnre += 1
                    if any(k in r for k in ['J', 'K', 'I']) and any(c.isdigit() for c in r.get('J', '') + r.get('K', '')):
                        com_nf += 1
                print(f"  Aba {month_tab} -> Linhas com NF: ~{com_nf} | GNREs marcadas OK: {ok_gnre}")

    # 2. Audit Planilha Principal
    with zipfile.ZipFile('/tmp/sheet_principal.xlsx', 'r') as z:
        strings = get_shared_strings(z)
        sheets_map = get_sheets_map(z)
        print("\n--- PLANILHA PRINCIPAL ---")
        total_p_nf = 0
        for day in [f"{i:02d}" for i in range(1, 32)]:
            if day in sheets_map:
                rows = parse_sheet_rows(z, sheets_map[day], strings)
                count = 0
                for r in rows[2:]:
                    # Checar coluna H / I / J para NF
                    v_concat = "".join(str(v or '') for v in r.values())
                    if re.search(r'NF\s*\d+|\b\d{4,6}\b', v_concat):
                        count += 1
                total_p_nf += count
        print(f"Total de linhas com indicativo de NF na Planilha Principal (Abas 01 a 31): ~{total_p_nf}")

if __name__ == "__main__":
    audit()
