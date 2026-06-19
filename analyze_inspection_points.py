import json
import csv
import os

def analyze_inspection_points():
    # Define file paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.join(script_dir, "resource/path")
    files = [
        "dry_zone.json",
        "wet_zone_3x.json",
        "record-filling.json",
        "wet_zone_12-1x.json"
    ]
    
    output_file = os.path.join(script_dir, "inspection_points.csv")
    
    summary = {}
    csv_data = []
    
    for filename in files:
        file_path = os.path.join(base_path, filename)
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue
            
        print(f"Processing {filename}...")
        summary[filename] = {"included": 0, "included_low": 0, "excluded": 0, "excluded_nodes": []}
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            for point in data:
                if point.get("PointInfo") == 1:
                    node_info = point.get("Node_info", "N/A")
                    is_low = "low" in node_info.lower()
                    
                    if "_low" not in node_info:
                        row = {
                            "Node_info": node_info,
                            "zone": point.get("Zone", "N/A"),
                            "Map": point.get("MapName", "N/A"),
                            "Inspection Type": point.get("Inspection", "N/A")
                        }
                        csv_data.append(row)
                        summary[filename]["included"] += 1
                        if is_low:
                            summary[filename]["included_low"] += 1
                    else:
                        summary[filename]["excluded"] += 1
                        summary[filename]["excluded_nodes"].append(node_info)
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    # Print Summary
    print("\n" + "="*50)
    print("ANALYSIS SUMMARY")
    print("="*50)
    for filename, stats in summary.items():
        print(f"File: {filename}")
        print(f"  - Inspection points found (Included): {stats['included']}")
        if stats['included_low'] > 0:
            print(f"    - of which are '-low' points: {stats['included_low']}")
        print(f"  - Inspection points cut (_low): {stats['excluded']}")
        if stats['excluded_nodes']:
            print(f"    - Excluded nodes: {', '.join(stats['excluded_nodes'])}")
        print("-" * 30)

    # Write to CSV
    if csv_data:
        keys = ["Node_info", "zone", "Map", "Inspection Type"]
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(csv_data)
            print(f"Successfully exported {len(csv_data)} points to {output_file}")
        except Exception as e:
            print(f"Error writing to CSV: {e}")
    else:
        print("No inspection points found.")

if __name__ == "__main__":
    analyze_inspection_points()
