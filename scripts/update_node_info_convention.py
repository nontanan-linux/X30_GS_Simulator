import json
import os

def convert_underscores_to_hyphens(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    changed_count = 0
    for wp in data:
        if 'Node_info' in wp:
            old_name = wp['Node_info']
            if '_' in old_name:
                new_name = old_name.replace('_', '-')
                wp['Node_info'] = new_name
                changed_count += 1
                # print(f"Renamed: {old_name} -> {new_name}")
    
    if changed_count > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print(f"Successfully updated {changed_count} waypoints in {file_path}")
    else:
        print(f"No underscores found in Node_info values of {file_path}")

if __name__ == "__main__":
    target_file = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/waypoints/dry_waypoints.json"
    convert_underscores_to_hyphens(target_file)
