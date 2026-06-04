import json
import re
import os

def reindex_via_points(filepath, start_index=219):
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return

    with open(filepath, 'r') as f:
        data = json.load(f)

    counter = start_index
    # Regex to capture: 'via', optional '-', then digits, then anything else
    # We want to catch 'via92-shuttle' and 'via-84'
    pattern = re.compile(r'^via-?(\d*)(.*)$')

    for node in data:
        name = node.get('Node_info', '')
        
        # Check if it's a via point
        if name.startswith('via'):
            # Skip exceptions
            if name.startswith('via-h2-') or name.startswith('via-2h-') or name.startswith('via-2c-') or name.startswith('via-c2'):
                continue
            
            match = pattern.match(name)
            if match:
                # We ignore the old digit part and just take the suffix
                suffix = match.group(2)
                
                # Construct new name: via-<counter><suffix>
                new_name = f"via-{counter}{suffix}"
                
                print(f"Renaming: {name} -> {new_name}")
                node['Node_info'] = new_name
                counter += 1

    # Re-index the 'Value' key for all nodes to be sequential
    for i, node in enumerate(data):
        node['Value'] = i

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)
    
    print(f"Finished. Re-indexed {counter - start_index} via points.")
    print(f"Re-sequenced 'Value' for all {len(data)} points.")

if __name__ == "__main__":
    target_file = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/path/final_filling.json"
    # The starting number for re-indexing 'via' points.
    # This does NOT affect the 'Value' key, which is always re-sequenced from 0.
    via_start_number = 279
    reindex_via_points(target_file, start_index=via_start_number)
