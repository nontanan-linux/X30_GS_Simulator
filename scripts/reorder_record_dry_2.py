import json
import re

def reorder_waypoints(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        waypoints = json.load(f)

    # Base indices starting from 1 for this file
    indices = {
        'via': 1,
        'leaked': 1,
        'thermal': 1,
        'vibration': 1,
        'loto': 1,
        'gauge': 1,
        'asset': 1
    }

    def get_new_node_info(old_info, indices, zone):
        # Handle all via variations
        if old_info.lower().startswith('via'):
            idx = indices['via']
            indices['via'] += 1
            
            # Extract suffix after 'via' (if any)
            suffix = ""
            match = re.match(r'^via\d*(.*)', old_info, re.I)
            if match:
                suffix = match.group(1)
            
            return f"via{idx}{suffix}"

        # Handle inspection points
        types = ['leaked', 'thermal', 'vibration', 'loto', 'gauge', 'asset']
        for t in types:
            if t in old_info.lower():
                idx = indices[t]
                indices[t] += 1
                
                # Check for modifiers/suffixes (e.g., -low, -MI23, -MI47)
                modifier = ""
                # Search for anything after the base type name and optional digits
                match = re.search(rf'{t}\d*(.*)', old_info, re.I)
                if match:
                    modifier = match.group(1)
                
                # Zone from wp
                z = zone.lower().replace("_", "-") if zone else "dry"
                
                return f"{z}-{t}-{idx:02}{modifier}"
        
        return old_info

    for i, wp in enumerate(waypoints):
        old_info = wp.get('Node_info', '')
        zone = wp.get('Zone', '')
        
        # Charges stay same
        if old_info not in ["ChargeOut", "ChargeIn"]:
            wp['Node_info'] = get_new_node_info(old_info, indices, zone)
        
        # Strictly sequential Value
        wp['Value'] = i

    # Save to a temporary file first
    output_path = file_path + ".new"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(waypoints, f, indent=4)
    
    return output_path

if __name__ == "__main__":
    path = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/waypoints/record_dry-2.json"
    new_file = reorder_waypoints(path)
    print(f"Reordered waypoints saved to {new_file}")
