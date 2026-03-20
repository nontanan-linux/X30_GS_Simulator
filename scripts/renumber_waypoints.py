import json
import re
import argparse
import os

def renumber_waypoints(input_file, output_file, prefixes, start_index, padding):
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading {input_file}: {e}")
        return

    current_index = start_index
    # prefixes is now a list
    # We want to match any of the prefixes.
    # Group 1: Prefix
    # Group 2: Optional separator and/or existing numbers
    # Group 3: Suffix (important descriptive modifiers like -low or -crawl)
    
    # We'll use a loop to check each point against each prefix.
    renumbered_count = 0
    for wp in data:
        node_info = wp.get('Node_info', '')
        
        matched_prefix = None
        for p in prefixes:
            if node_info.lower().startswith(p.lower()):
                matched_prefix = p
                break
        
        if matched_prefix:
            # Extract suffix: find where the prefix ends, then skip any separator/digits
            # Example: dry_vibration_05_low (prefix: dry_vibration)
            # Remaining: _05_low. We rstrip/_ the prefix first.
            
            remainder = node_info[len(matched_prefix):]
            # Strip leading -|_|\d+ from remainder to find the real suffix
            suffix = re.sub(r'^[-|_|0-9]+', '', remainder)
            
            # Determine separator: prefer '_' if present in prefix or node_info
            sep = "_" if "_" in matched_prefix or "_" in node_info else "-"
            
            # New name construction
            fmt = f"{{:0{padding}d}}"
            new_name = f"{matched_prefix.rstrip('_-')}{sep}{fmt.format(current_index)}{suffix}"
            wp['Node_info'] = new_name
            current_index += 1
            renumbered_count += 1

    if renumbered_count > 0:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print(f"Successfully renumbered {renumbered_count} waypoints in {output_file}")
            print(f"Prefixes: {prefixes} | Sequence: {start_index} to {current_index - 1}")
        except Exception as e:
            print(f"Error saving {output_file}: {e}")
    else:
        print(f"No waypoints found matching prefixes {prefixes} in {input_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Renumber waypoints in a JSON file.")
    parser.add_argument("input", help="Input JSON file")
    parser.add_argument("--prefix", required=True, help="Prefix(es) to match, comma separated (e.g. 'dry_vibration,dry3_vibration')")
    parser.add_argument("--start", type=int, default=1, help="Starting index (default: 1)")
    parser.add_argument("--padding", type=int, default=2, help="Padding for numbers (default: 2)")
    parser.add_argument("--out", help="Output JSON file (default: same as input)")

    args = parser.parse_args()
    output = args.out if args.out else args.input
    
    prefixes = [p.strip() for p in args.prefix.split(",")]
    renumber_waypoints(args.input, output, prefixes, args.start, args.padding)
