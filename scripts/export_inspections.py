import json
import csv
import os

def export_inspections(files, output_csv):
    headers = ['zone', 'name', 'floor (MapName)', 'Inspection Type']
    rows = []

    for filepath in files:
        if not os.path.exists(filepath):
            print(f"Warning: File not found: {filepath}")
            continue
            
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for wp in data:
            if wp.get('PointInfo') == 1:
                rows.append({
                    'zone': wp.get('Zone', wp.get('zone', '')),
                    'name': wp.get('Node_info', ''),
                    'floor (MapName)': wp.get('MapName', ''),
                    'Inspection Type': wp.get('Inspection', '')
                })

    # Define sort order
    priority = {
        'wet1-2': 1,
        'wet12': 1,
        'wet3': 2,
        'dry1-2': 3,
        'dry3': 4,
        'filling': 5,
        'filling1': 5,
        'filling3': 5
    }

    def sort_key(row):
        return priority.get(row['zone'].lower(), 99), row['zone'].lower(), row['name']

    rows.sort(key=sort_key)

    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Successfully exported {len(rows)} inspection points to {output_csv}")

if __name__ == "__main__":
    mission_files = [
        "resource/path/wet_zone_12-1x.json",
        "resource/path/wet_zone_3x.json",
        "resource/path/dry_zone.json",
        "resource/path/record-filling.json"
    ]
    output = "inspection_points.csv"
    export_inspections(mission_files, output)
