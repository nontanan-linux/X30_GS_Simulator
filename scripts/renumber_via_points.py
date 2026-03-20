import json
import re
import argparse
import os

def renumber_waypoints(input_file, output_file, prefix, start_index):
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading {input_file}: {e}")
        return

    current_index = start_index
    # Regex to catch prefix followed by digits (mission via points)
    # We avoid matching protocol markers like via-h2- by requiring digits immediately after the prefix.
    pattern = re.compile(f"^({re.escape(prefix)})([0-9]+)(.*)$", re.IGNORECASE)

    renumbered_count = 0
    for wp in data:
        node_info = wp.get('Node_info', '')
        
        match = pattern.match(node_info)
        if match:
            # We preserve the prefix and the suffix (group 1 and 3)
            # and replace the number (group 2) with the new sequence.
            new_name = f"{match.group(1)}{current_index:02d}{match.group(3)}"
            wp['Node_info'] = new_name
            current_index += 1
            renumbered_count += 1

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print(f"Successfully renumbered {renumbered_count} waypoints in {output_file}")
        print(f"Sequence: {start_index} to {current_index - 1}")
    except Exception as e:
        print(f"Error saving {output_file}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Renumber mission via waypoints in a JSON file.")
    parser.add_argument("input", help="Input JSON file")
    parser.add_argument("--prefix", default="via", help="Prefix to match (default: via)")
    parser.add_argument("--start", type=int, default=1, help="Starting index (default: 1)")
    parser.add_argument("--out", help="Output JSON file (default: same as input)")

    args = parser.parse_args()
    output = args.out if args.out else args.input
    
    renumber_waypoints(args.input, output, args.prefix, args.start)
