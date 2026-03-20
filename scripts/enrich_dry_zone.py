import json
import os
import re

def enrich_dry_zone(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    current_zone = "wet_zone"
    
    # Counters for re-sequencing
    via_counter = 84
    # Global counters for categories across prefixes (dry, dry3)
    category_current = {"leaked": 14, "thermal": 37, "vibration": 29, "loto": 6, "gauge": 1}
    
    new_data = []
    for wp in data:
        name = wp.get('Node_info', '').replace('_', '-')
        
        # Determine Zone (simple inheritance / trigger)
        if name == "via95-SD2O":
            current_zone = "dry"
            
        is_via = "via" in name.lower() or "charge" in name.lower()
        
        # Re-numbering Logic
        new_name = name
        if is_via:
            if name.lower().startswith("via") and any(char.isdigit() for char in name) and not "-" in name:
                # Regular via point (e.g., via84, via100)
                new_name = f"via{via_counter}"
                via_counter += 1
            point_zone = current_zone
        else:
            # Inspection point
            # Match prefix-category-index (e.g., dry-leaked-14) or prefix-category (e.g., dry-vibration)
            match = re.search(r'^([a-z0-9]+)-([a-z]+)', name.lower())
            if match:
                prefix = match.group(1)
                category = match.group(2)
                
                # Check for suffix (e.g., low, 2nd)
                suffix = ""
                suffix_match = re.search(r'\d+([a-z-]+)$', name.lower())
                if suffix_match:
                    suffix = suffix_match.group(1)
                
                idx = category_current.get(category, 1)
                new_name = f"{prefix}-{category}-{idx:02d}{suffix}" if idx < 10 and category in ["loto", "gauge"] else f"{prefix}-{category}-{idx}{suffix}"
                
                # Special case: loto and gauge usually have leading zeros if < 10
                if category == "loto" or category == "gauge":
                     new_name = f"{prefix}-{category}-{idx:02d}{suffix}"
                else:
                     new_name = f"{prefix}-{category}-{idx}{suffix}"

                category_current[category] = idx + 1
                
                point_zone = prefix
                current_zone = point_zone # Update inheritance
            else:
                point_zone = current_zone

        # Trigger logic overrides
        if name == "via95-SD2O":
            point_zone = "dry"

        # Reconstruct with specific order
        new_wp = {
            "Node_info": new_name,
            "MapName": "1st_floor",
            "Zone": point_zone
        }
        
        for key, value in wp.items():
            if key not in ["Node_info", "MapName", "Zone"]:
                new_wp[key] = value
                
        new_data.append(new_wp)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, indent=4)
    print(f"Successfully re-organized and enriched {len(new_data)} waypoints in {file_path}")

if __name__ == "__main__":
    target_file = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/dry_zone.json"
    enrich_dry_zone(target_file)
