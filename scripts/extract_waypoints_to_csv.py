import json
import csv
import os

def extract_waypoints(json_files, output_csv):
    headers = ["Zone", "Point Name", "Floor", "Inspection Type"]
    data_rows = []
    
    for json_file in json_files:
        if not os.path.exists(json_file):
            print(f"Warning: {json_file} not found.")
            continue
            
        with open(json_file, 'r') as f:
            data = json.load(f)
            
        for wp in data:
            # We only care about inspection points (PointInfo: 1)
            if wp.get("PointInfo") == 1:
                name = wp.get("Node_info", "")
                
                # Determine Inspection Type from name prefix
                # (e.g. dry-leaked-1 -> Leakage, dry3-thermal-44 -> Thermal)
                ins_type = "Unknown"
                name_lower = name.lower()
                if "thermal" in name_lower: ins_type = "Thermal"
                elif "leakage" in name_lower or "leaked" in name_lower: ins_type = "Leakage"
                elif "gauge" in name_lower: ins_type = "Gauge"
                elif "loto" in name_lower: ins_type = "LOTO"
                elif "vibration" in name_lower: ins_type = "Vibration"
                elif "asset" in name_lower: ins_type = "Asset"
                
                data_rows.append([
                    wp.get("Zone", "Dry Zone"),
                    name,
                    wp.get("MapName", "Unknown"),
                    ins_type
                ])
                
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data_rows)
        
    print(f"Exported {len(data_rows)} waypoints to {output_csv}")

if __name__ == "__main__":
    files = ["resource/path/dry_zone.json", "resource/path/dry_zone_2nd.json"]
    output = "resource/docs/dry_zone_inspection_points.csv"
    extract_waypoints(files, output)
