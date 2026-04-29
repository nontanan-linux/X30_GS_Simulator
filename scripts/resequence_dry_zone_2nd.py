import json
import re
import os

def normalize_category(name):
    """
    Normalizes a waypoint name into a category key by removing 
    zone-specific prefixes and stripping protocol-neutral modifiers.
    Returns (category_key, original_index)
    """
    name_orig = name
    name = name.lower().replace("_", "-")
    
    # Remove zone prefix
    name = re.sub(r'^(wet\d+|dry\d*(-\d+)*|zone\d+)[-_]', '', name)
    
    # Strip acoustic/visual modifiers
    name = re.sub(r'^(acoustic|visual)-', '', name)
    
    # Priority for Protocol prefixes (most specific first)
    for k in ['via-2h-x', 'via-2h-', 'via-h2-']:
        if name.startswith(k):
             match = re.search(r'(\d+)', name[len(k):])
             if match:
                 return k, int(match.group(1))
             else:
                 return k, 0 # Fallback for protocol without digits
    
    # Special case for 'via' without digits
    if name == 'via' or name.startswith('via-'):
        match = re.search(r'(\d+)', name)
        if match:
            return 'via', int(match.group(1))
        else:
            return 'via', 0

    # General categories (picking the first sequence of digits)
    match = re.search(r'^([a-z-]+?)(\d+)', name)
    if match:
        prefix = match.group(1).rstrip("-").rstrip("_")
        number = int(match.group(2))
        return prefix, number
    return None, None

def resequence_file(filepath, offsets):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Counters for each category, starting at the offset
    counters = {k: v for k, v in offsets.items()}
    # Protocol categories start at 0
    protocol_cats = ['via-2h-x', 'via-2h-', 'via-h2-']
    for p in protocol_cats:
        counters[p] = 0

    for wp in data:
        info = wp.get('Node_info', '')
        cat, old_idx = normalize_category(info)
        
        if cat:
            new_idx = counters[cat]
            counters[cat] += 1
            
            zone = wp.get('Zone', '')
            if zone:
                zone = zone.replace('_', '-')
            
            if cat.startswith('via'):
                if cat == 'via-h2-':
                    wp['Node_info'] = f"{cat}{new_idx:02}"
                elif cat == 'via-2h-x':
                    wp['Node_info'] = f"{cat}{new_idx}"
                elif cat == 'via-2h-':
                    wp['Node_info'] = f"{cat}{new_idx:02}"
                else:
                    # General via points: via158
                    suffix = ""
                    # Preserve manual suffixes like -shuttle01-open
                    match = re.search(r'\d+(.*)', info)
                    if match:
                        suffix = match.group(1)
                    
                    wp['Node_info'] = f"via{new_idx}{suffix}"
            else:
                # Inspection points
                prefix = ""
                if "visual" in info: prefix = "visual-"
                elif "acoustic" in info: prefix = "acoustic-"
                
                suffix = ""
                if "-low" in info: suffix = "-low"
                elif "-mi" in info:
                    match = re.search(r'(-mi\d+)', info, re.I)
                    if match: suffix = match.group(1)
                elif "-MI" in info.upper():
                    match = re.search(r'(-MI\d+.*)', info, re.I)
                    if match: suffix = match.group(1)
                
                if zone:
                    wp['Node_info'] = f"{zone}-{prefix}{cat}-{new_idx:02}{suffix}"
                else:
                    wp['Node_info'] = f"{prefix}{cat}-{new_idx:02}{suffix}"

    # Also update global 'Value' field if it's meant to be sequential (excluding header/footer maybe?)
    # Based on the file, Value seems to be 0 for ChargeOut, then 1, 2, 3...
    for i, wp in enumerate(data):
        wp['Value'] = i

    return data

if __name__ == "__main__":
    filepath = "resource/path/dry_zone_2nd.json"
    
    # Offsets derived from dry_zone.json max values
    offsets = {
        'via': 158,
        'leaked': 39,
        'thermal': 48,
        'loto': 14,
        'gauge': 9,
        'vibration': 42,
        'asset': 12 # Based on audit results showing Next Min 12 for record-filling
    }
    
    new_data = resequence_file(filepath, offsets)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, indent=4, ensure_ascii=False)
    
    print(f"Successfully re-sequenced {filepath}")
