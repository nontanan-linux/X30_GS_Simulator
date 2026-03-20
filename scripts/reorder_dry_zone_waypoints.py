import json
import re

def reorder_waypoints(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        waypoints = json.load(f)

    # Base indices
    indices = {
        'via': 84,
        'leaked': 14,
        'thermal': 37,
        'vibration': 29,
        'loto': 6,
        'gauge': 1
    }

    def get_new_node_info(old_info, indices):
        # Identify zone prefix (e.g. wet1-2-, dry-, dry3-)
        prefix_match = re.match(r'^((?:wet|dry|zone)\d*(?:-\d+)?)[-_]', old_info, re.I)
        zone_prefix = prefix_match.group(1) if prefix_match else ""
        
        # Handle protocol points (via-h2-*, via-2h-*)
        if re.search(r'via-h2-|via-2h-', old_info, re.I):
            return old_info
            
        # Handle via points including via-bf-* and viaX.Y
        if re.search(r'via\d+(\.\d+)?|via-bf-', old_info, re.I):
            idx = indices['via']
            indices['via'] += 1
            # Preserve suffixes like -shuttle01-open or -bf-loto10 suffix parts
            # If it's via-bf-loto10, we just want it to be via<idx>
            # If it's via91-shuttle01-open, we want via<idx>-shuttle01-open
            suffix = ""
            if '-' in old_info:
                parts = old_info.split('-')
                if 'via' in parts[0] or (parts[0] == 'via' and parts[1] == 'bf'):
                    # Find where the suffix starts
                    if parts[0] == 'via' and parts[1] == 'bf':
                         # for via-bf-loto10, handle it specially
                         suffix = "" # Just turn it into viaXX
                    else:
                         # for via91-shuttle01-open
                         suffix = "-" + "-".join(parts[1:])
            return f"via{idx}{suffix}"

        # Handle inspection points
        types = ['leaked', 'thermal', 'vibration', 'loto', 'gauge']
        for t in types:
            if t in old_info.lower():
                idx = indices[t]
                indices[t] += 1
                
                # Check for modifiers like -low or -crawl
                modifier = ""
                if "-low" in old_info.lower():
                    modifier = "-low"
                elif "-crawl" in old_info.lower():
                    modifier = "-crawl"
                
                # Reconstruct name: <zone>-<type>-<idx><modifier>
                # Use current zone prefix if available, else literal "dry" or "dry3"
                if not zone_prefix:
                    # Try to extract zone from old_info if it wasn't captured correctly
                    if old_info.startswith('dry3'): zone_prefix = "dry3"
                    elif old_info.startswith('dry'): zone_prefix = "dry"
                    else: zone_prefix = "dry" # Default
                
                return f"{zone_prefix}-{t}-{idx:02}{modifier}"
        
        return old_info

    for i, wp in enumerate(waypoints):
        old_info = wp.get('Node_info', '')
        if old_info not in ["ChargeOut", "ChargeIn"]:
            wp['Node_info'] = get_new_node_info(old_info, indices)
        
        # Strictly sequential Value
        wp['Value'] = i

    # Save to a temporary file first
    output_path = file_path + ".new"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(waypoints, f, indent=4)
    
    return output_path

if __name__ == "__main__":
    path = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/waypoints/dry_zone.json"
    new_file = reorder_waypoints(path)
    print(f"Reordered waypoints saved to {new_file}")
