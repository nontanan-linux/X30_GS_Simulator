import json
import re
import os

def get_max_indices(filepaths):
    """Scan multiple files to find the absolute maximum index for each category."""
    categories = ['thermal', 'leakage', 'leaked', 'vibration', 'gauge', 'asset', 'loto']
    max_indices = {cat: 0 for cat in categories}
    
    # pattern to match [optional-prefix-]category-[optional-prefix]number
    # e.g., leakage-1, dry3-loto-07, thermal-10
    pattern = re.compile(r'(?:.*-)?([a-zA-Z]+)-(?:.*-)?(\d+)')

    for filepath in filepaths:
        if not os.path.exists(filepath):
            print(f"Warning: {filepath} not found for index scanning.")
            continue

        with open(filepath, 'r') as f:
            data = json.load(f)

        for node in data:
            name = node.get('Node_info', '')
            match = pattern.search(name)
            if match:
                cat = match.group(1).lower()
                num = int(match.group(2))
                
                if cat in max_indices:
                    if num > max_indices[cat]:
                        max_indices[cat] = num
                
                # Special cases for normalization
                if cat == 'leaked' or cat == 'leakage':
                    if num > max_indices['leakage']:
                        max_indices['leakage'] = num

    return max_indices

def reindex_inspection_points(source_files, target_file, thermal=None, leakage=None, vibration=None, gauge=None, asset=None, loto=None):
    base_indices = get_max_indices(source_files)
    print(f"Global Base indices from {source_files}: {base_indices}")

    if not os.path.exists(target_file):
        print(f"Error: {target_file} not found.")
        return

    with open(target_file, 'r') as f:
        data = json.load(f)

    categories = ['thermal', 'leakage', 'leaked', 'vibration', 'gauge', 'asset', 'loto']
    overrides = {
        'thermal': thermal,
        'leakage': leakage,
        'leaked': leakage,
        'vibration': vibration,
        'gauge': gauge,
        'asset': asset,
        'loto': loto
    }
    counters = {}
    for cat in categories:
        val = overrides.get(cat)
        if val is not None:
            counters[cat] = val - 1
        else:
            counters[cat] = base_indices.get(cat, 0)
    
    # Match standard and non-standard (prefixed) names
    pattern = re.compile(r'(?:.*-)?([a-zA-Z]+)-(?:.*-)?(\d+)')

    for node in data:
        name = node.get('Node_info', '')
        
        # Check if the name matches an inspection pattern
        match = pattern.search(name)
        if match:
            cat = match.group(1).lower()
            if cat in categories:
                # Increment and rename
                counters[cat] += 1
                new_name = f"{cat}-{counters[cat]}"
                if name != new_name:
                    print(f"Renaming: {name} -> {new_name}")
                node['Node_info'] = new_name

    with open(target_file, 'w') as f:
        json.dump(data, f, indent=4)
    
    print(f"Finished re-indexing {target_file}")

if __name__ == "__main__":
    # The sequence of files to look back at
    # sources = [
    # "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/path/final_dry_full.json"
    # ]
    sources = [
    "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/path/final_packing.json"
    ]
    target = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/path/final_filling.json"
    reindex_inspection_points(sources, target, loto=6, gauge=11, asset=16)
