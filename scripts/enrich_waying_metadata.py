import json
import os

def enrich_waypoints(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    current_zone = "wet_zone"
    in_wet_range_1 = False
    in_wet_range_2 = False # via-2h-01 to ChargeIn
    
    new_data = []
    for wp in data:
        name = wp.get('Node_info', '')
        
        # Range 1: ChargeOut to via94
        if name == "ChargeOut":
            in_wet_range_1 = True
            current_zone = "wet_zone"
        
        # Trigger Dry: via95-SD2O
        if name == "via95-SD2O":
            in_wet_range_1 = False
            current_zone = "dry"
            
        # Range 3: via-2h-01 to ChargeIn
        if name == "via-2h-01":
            in_wet_range_2 = True
            current_zone = "wet_zone"
            
        # Determine Point Zone
        is_via = "via" in name.lower() or "charge" in name.lower()
        
        if in_wet_range_1 or in_wet_range_2:
            point_zone = "wet_zone"
        elif name == "via95-SD2O":
            point_zone = "dry"
        elif not is_via and '-' in name:
            # Inspection point: First word is Zone
            point_zone = name.split('-')[0]
            current_zone = point_zone # Update inheritance for following via points
        else:
            # Via point: Inherit from current series
            point_zone = current_zone

        # End Range triggers (after processing to include the point itself)
        if name == "via94":
            in_wet_range_1 = False
        if name == "ChargeIn":
            in_wet_range_2 = False

        # Reconstruct with specific order
        new_wp = {
            "Node_info": name,
            "MapName": "1st_floor",
            "Zone": point_zone
        }
        
        # Add all other keys except Node_info, MapName, Zone
        for key, value in wp.items():
            if key not in ["Node_info", "MapName", "Zone"]:
                new_wp[key] = value
                
        new_data.append(new_wp)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, indent=4)
    print(f"Successfully enriched {len(new_data)} waypoints in {file_path}")

if __name__ == "__main__":
    target_file = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/waypoints/dry_waypoints.json"
    enrich_waypoints(target_file)
