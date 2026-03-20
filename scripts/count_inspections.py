import json
import argparse
import os
import re
from collections import defaultdict

def print_table(headers, rows, title=None):
    """Prints a styled grid table using basic strings."""
    if title:
        print(f"\n{title}")
        
    # Determine column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))
    
    # Build the separator line
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    
    # Print header
    print(sep)
    header_str = "|" + "|".join(f" {headers[i]:<{widths[i]}} " for i in range(len(headers))) + "|"
    print(header_str)
    print(sep.replace("-", "="))
    
    # Print rows
    for row in rows:
        row_str = "|" + "|".join(f" {str(row[i]):<{widths[i]}} " for i in range(len(row))) + "|"
        print(row_str)
    
    print(sep)

def count_inspection_points(json_file_path):
    """
    Counts and audits inspection points in a waypoint JSON file.
    Gathers points by type and checks for numerical sequence order.
    """
    if not os.path.exists(json_file_path):
        print(f"Error: File not found at {json_file_path}")
        return

    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            waypoints = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_file_path}")
        return

    total_count = len(waypoints)
    via_count = 0
    charge_count = 0
    inspection_points = []
    
    # Sequence Audit: Group by pattern (e.g., wet12_visual_loto01 -> wet12_visual_loto)
    # Pattern: everything up to the trailing digits
    # category_map stores (index_in_sequence, global_position)
    category_map = defaultdict(list)

    for idx, wp in enumerate(waypoints, 1):
        node_info = wp.get('Node_info', 'Unknown')
        name_lower = node_info.lower()

        if 'via' in name_lower:
            via_count += 1
        elif 'charge' in name_lower:
            charge_count += 1
        else:
            # Replace underscores with hyphens for consistent naming in the report
            node_info_display = node_info.replace("_", "-")
            inspection_points.append(node_info_display)
            
            # Extract category and index (e.g., "thermal05" -> "thermal", 5)
            match = re.search(r'^(.*?)(\d+)(?!.*\d)', node_info_display)
            if match:
                base_name = match.group(1)
                try:
                    seq_index = int(match.group(2))
                    # Store both the sequence number and its global position in the file
                    category_map[base_name].append({
                        'seq': seq_index,
                        'global': idx,
                        'name': node_info_display
                    })
                except ValueError:
                    pass

    # --- 1. General Summary Table ---
    summary_headers = ["Category", "Count"]
    summary_rows = [
        ["Total Waypoints", total_count],
        ["Via Points", via_count],
        ["Charge Points", charge_count],
        ["INSPECTION TOTAL", len(inspection_points)]
    ]
    print_table(summary_headers, summary_rows, title=f"WAYPOINT ANALYTICS: {os.path.basename(json_file_path)}")

    # --- 2. Sequence Audit Table ---
    audit_headers = ["Category/Prefix", "Count", "Sequence", "Last Point #", "Status"]
    audit_rows = []
    has_errors = False
    
    for base_name, data in category_map.items():
        if not data:
            continue
            
        indices = [d['seq'] for d in data]
        min_idx = min(indices)
        max_idx = max(indices)
        found_sorted = sorted(indices)
        last_pos = data[-1]['global']
        
        # Check for actual internal gaps in the existing sequence
        # We check if the sequence present is consecutive
        actual_range = list(range(min_idx, min_idx + len(indices)))
        missing_internally = [i for i in actual_range if i not in indices]
        
        # Check for out-of-order in JSON
        is_json_ordered = (indices == found_sorted)
        
        status = "OK"
        info = []
        if min_idx != 1:
            info.append(f"Offset@{min_idx}")
            
        if missing_internally or not is_json_ordered:
            has_errors = True
            error_msg = []
            if missing_internally: error_msg.append(f"Gap:{missing_internally}")
            if not is_json_ordered: error_msg.append("Unordered")
            status = f"ERR ({', '.join(error_msg)})"
        elif info:
            status = f"CONT ({', '.join(info)})" # Indicate continuation
            
        audit_rows.append([
            base_name, 
            len(data), 
            f"{found_sorted[0]:02}-{found_sorted[-1]:02}", 
            f"Pt {last_pos}", 
            status
        ])

    if audit_rows:
        print_table(audit_headers, audit_rows, title="INSPECTION SEQUENCE AUDIT")
        if not has_errors:
            print("\n>> SUCCESS: All inspection sequences are perfect and well-ordered!")
    else:
        print("\nNo numbered inspection sequences identified.")
    
    # --- 3. Detailed List (Optional Pretty Table if useful, but maybe simple list is better for 27 items) ---
    if inspection_points:
        print("\nDETAILED INSPECTION LIST:")
        for i, name in enumerate(inspection_points, 1):
            print(f"  {i:2}. {name}")
    print("-" * 80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Count inspection points in a waypoint JSON file.")
    parser.add_argument("--input", "-i", type=str, help="Path to the waypoint JSON file.")
    
    args = parser.parse_args()

    # Default path if arguments are not provided
    default_json = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/waypoints/dry_waypoints.json"
    json_file = args.input if args.input else default_json

    count_inspection_points(json_file)
