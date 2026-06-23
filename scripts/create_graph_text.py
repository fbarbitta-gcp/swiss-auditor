import csv
import json
import argparse
import os

def create_graph_text(csv_path, output_json, output_md):
    graph = {}
    
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    try:
        f = open(csv_path, 'r', encoding='utf-8')
        f.readline()
        f.seek(0)
        encoding = 'utf-8'
    except UnicodeDecodeError:
        encoding = 'latin-1'
    finally:
        if 'f' in locals():
            f.close()

    print(f"Using encoding: {encoding}")

    cosmetic_keywords = [
        'shamp', 'shampoo', 'capilar', 'cabello', 'peinar', 
        'acondicionador', 'enjuague', 'balsamo', 'b ls.'
    ]
    cosmetic_brands = ['biferdil', 'ecohair']

    with open(csv_path, 'r', encoding=encoding) as f:
        reader = csv.DictReader(f)
        for row in reader:
            drug = row.get('droga_principal', '').strip() if row.get('droga_principal') else "UNKNOWN_DRUG"
            brand = row.get('nombre_comercial', '').strip() if row.get('nombre_comercial') else "UNKNOWN_BRAND"
            pres = row.get('presentacion', '').strip() if row.get('presentacion') else "UNKNOWN_PRESENTATION"
            
            # Filtration
            brand_lower = brand.lower()
            pres_lower = pres.lower()
            is_cosmetic = any(k in brand_lower or k in pres_lower for k in cosmetic_keywords) or \
                          any(b in brand_lower for b in cosmetic_brands)
            if is_cosmetic:
                continue

            if drug not in graph:
                graph[drug] = {
                    'nombres_comerciales': set(),
                    'presentaciones': set()
                }
            graph[drug]['nombres_comerciales'].add(brand)
            graph[drug]['presentaciones'].add(pres)

    # Convert sets to sorted lists
    structured_graph = {}
    for drug, data in graph.items():
        structured_graph[drug] = {
            'nombres_comerciales': sorted(list(data['nombres_comerciales'])),
            'presentaciones': sorted(list(data['presentaciones']))
        }

    # Save as JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(structured_graph, f, ensure_ascii=False, indent=2)
    print(f"Saved JSON to {output_json}")

    # Save as Markdown
    with open(output_md, 'w', encoding='utf-8') as f:
        for drug, data in structured_graph.items():
            f.write(f"## {drug}\n")
            f.write("- **Nombres Comerciales**:\n")
            for b in sorted(data['nombres_comerciales']):
                f.write(f"  - {b}\n")
            f.write("- **Presentaciones**:\n")
            for p in sorted(data['presentaciones']):
                f.write(f"  - {p}\n")
            f.write("\n")
    print(f"Saved Markdown to {output_md}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create text graph from CSV for LLM context.")
    parser.add_argument("--csv", default="tests/data_grafo.csv", help="Input CSV file")
    parser.add_argument("--json", default="tests/data_grafo_structured.json", help="Output JSON file")
    parser.add_argument("--md", default="agents/resources/data_grafo_structured.md", help="Output Markdown file")
    args = parser.parse_args()

    create_graph_text(args.csv, args.json, args.md)
