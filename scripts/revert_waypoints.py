import json
import re

def revert_to_hyphenated():
    backup_file = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/waypoints/dry_waypoints-back.json"
    target_file = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/waypoints/dry_waypoints.json"
    
    with open(backup_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Re-apply hyphenation (Action 1)
    changed_count = 0
    for wp in data:
        if 'Node_info' in wp:
            old_name = wp['Node_info']
            if '_' in old_name:
                new_name = old_name.replace('_', '-')
                wp['Node_info'] = new_name
                changed_count += 1
                
    with open(target_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    
    print(f"Successfully reverted to hyphenated state. Updated {changed_count} waypoints.")

if __name__ == "__main__":
    revert_to_hyphenated()
