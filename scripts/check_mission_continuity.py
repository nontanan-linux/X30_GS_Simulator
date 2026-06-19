import json
import os
import math
import argparse
import re

def calculate_distance(p1, p2):
    """Calculates Euclidean distance between two points."""
    return math.sqrt((p1['PosX'] - p2['PosX'])**2 + (p1['PosY'] - p2['PosY'])**2)

def format_val(val):
    if isinstance(val, int) or (isinstance(val, float) and val.is_integer()):
        return f"{int(val):02}"
    else:
        return f"{val:04.1f}"

def find_gaps(indices):
    float_indices = [float(x) for x in indices]
    int_parts = sorted(list(set(int(x) for x in float_indices)))
    if not int_parts:
        return []
    
    min_int = min(int_parts)
    max_int = max(int_parts)
    
    missing = []
    for i in range(min_int, max_int + 1):
        if i not in int_parts:
            missing.append(i)
            
    from collections import defaultdict
    decimals_by_int = defaultdict(list)
    for x in float_indices:
        int_part = int(x)
        dec_part = round((x - int_part) * 10)
        decimals_by_int[int_part].append(dec_part)
        
    for int_part, decs in decimals_by_int.items():
        decs = sorted(list(set(decs)))
        if not decs:
            continue
        if len(decs) > 1 or (len(decs) == 1 and decs[0] > 0):
            start_dec = 0 if 0 in decs else 1
            for d in range(start_dec, max(decs) + 1):
                if d not in decs:
                    if d == 0:
                        missing.append(int_part)
                    else:
                        missing.append(float(f"{int_part}.{d}"))
                        
    return sorted(missing)

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

def audit_internal_sequence(waypoints, filename):
    """
    Performs internal sequence audit for a single file.
    Checks for starting 01, numerical gaps, and ordering.
    """
    from collections import defaultdict
    category_map = defaultdict(list)
    
    for idx, wp in enumerate(waypoints, 1):
        node_info = wp.get('Node_info', '')
        # Use the central normalization logic
        base_name, seq_index = normalize_category(node_info)
        
        if base_name is not None:
            category_map[base_name].append({
                'seq': seq_index,
                'global': idx,
                'name': node_info
            })

    rows = []
    for base_name, data in category_map.items():
        indices = [d['seq'] for d in data]
        min_idx = min(indices)
        found_sorted = sorted(indices)
        last_pos = data[-1]['global']
        
        # Check for internal gaps
        missing = find_gaps(indices)
        is_ordered = (indices == found_sorted)
        
        status = "OK"
        if min_idx not in [0, 1]:
            status = f"CONT (Offset@{format_val(min_idx)})"
        
        if missing or not is_ordered:
            errs = []
            if missing:
                formatted_missing = [format_val(m) for m in missing]
                errs.append(f"Gap:{formatted_missing}")
            if not is_ordered:
                errs.append("Unordered")
            status = f"ERR ({', '.join(errs)})"
            
        rows.append([
            base_name.upper().rstrip("-"),
            len(data),
            f"{format_val(found_sorted[0])}-{format_val(found_sorted[-1])}",
            f"Pt {last_pos}",
            status
        ])
    
    if rows:
        headers = ["Category/Prefix", "Count", "Sequence", "Last Point #", "Status"]
        print_table(headers, rows, title=f"INSPECTION SEQUENCE AUDIT: {filename}")

def normalize_category(name):
    """
    Normalizes a waypoint name into a category key by removing 
    zone-specific prefixes (e.g., wet12, wet3, dry) and trailing digits.
    Also strips protocol-neutral modifiers like 'acoustic-' or 'visual-'.
    """
    name = name.lower().replace("_", "-")
    
    # Remove zone prefix (wet\d+-, dry\d*-, zone\d+-, or dry\d+-\d+-)
    name = re.sub(r'^(wet\d+|dry\d*(-\d+)*|zone\d+)[-_]', '', name)
    
    # Strip acoustic/visual modifiers to unify categories
    name = re.sub(r'^(acoustic|visual)-', '', name)
    
    # Priority for Protocol prefixes (most specific first)
    for k in ['via-2h-x', 'via-2h-', 'via-h2-', 'via-c2-', 'via-2c-']:
        if name.startswith(k):
             match = re.search(r'(\d+(?:\.\d+)?)', name[len(k):])
             if match:
                 val = match.group(1)
                 if '.' in val:
                     return k, float(val)
                 else:
                     return k, int(val)
    
    # General via points (picking the first sequence of digits)
    match = re.search(r'^([a-z-]+?)(\d+)', name)
    if match:
        prefix = match.group(1).rstrip("-").rstrip("_")
        number = int(match.group(2))
        return prefix, number
    return None, None

def get_inspection_sequences(waypoints):
    """
    Extracts the highest and lowest sequence numbers for each normalized category.
    """
    max_indices = {} # cat_key -> max_num
    min_indices = {} # cat_key -> min_num

    for wp in waypoints:
        node_info = wp.get('Node_info', '')
        cat_key, idx = normalize_category(node_info)
        
        if cat_key:
            if cat_key not in min_indices:
                min_indices[cat_key] = idx
            min_indices[cat_key] = min(min_indices[cat_key], idx)
            
            if cat_key not in max_indices:
                max_indices[cat_key] = idx
            max_indices[cat_key] = max(max_indices[cat_key], idx)
            
    return max_indices, min_indices

def check_continuity(file_sequence):
    """Checks continuity between a sequence of waypoint JSON files."""
    summary_headers = ["Category", "Total Count"]
    summary_rows = []
    
    total_wps = 0
    via_count = 0
    ins_count = 0
    cat_summary = {} # Generalized cat -> count
    
    serial_headers = ["Transition", "Category", "Prev Max", "Next Min", "Status"]
    serial_rows = []
    
    dist_cats = set() # To track which categories to show in distribution
    file_counts = {} # filename -> {cat -> count}
    
    all_data = []
    for filepath in file_sequence:
        if not os.path.exists(filepath):
            print(f"Error: File not found {filepath}")
            continue
        with open(filepath, 'r', encoding='utf-8') as f:
            all_data.append({'path': filepath, 'data': json.load(f)})

    if len(all_data) < 2:
        print("Need at least 2 valid files to check continuity.")
        return

    # --- Global Mission Stats & Internal Sequence Audit ---
    for f_info in all_data:
        wps = f_info['data']
        fname = os.path.basename(f_info['path'])
        total_wps += len(wps)
        audit_internal_sequence(wps, fname)
        
        file_counts[fname] = {}
        
        for wp in wps:
            info = wp.get('Node_info', '')
            cat, _ = normalize_category(info)
            point_info = wp.get('PointInfo', 0)
            
            if point_info == 1:
                ins_count += 1
                if cat:
                    cat_summary[cat] = cat_summary.get(cat, 0) + 1
                    dist_cats.add(cat)
                    file_counts[fname][cat] = file_counts[fname].get(cat, 0) + 1
            else:
                via_count += 1
                # Track VIA counts per file for the distribution table
                file_counts[fname]['__VIA__'] = file_counts[fname].get('__VIA__', 0) + 1

    for i in range(len(all_data) - 1):
        f1 = all_data[i]
        f2 = all_data[i+1]
        trans_name = f"{os.path.basename(f1['path'])} -> {os.path.basename(f2['path'])}"
        
        # (Spatial continuity check removed per user request)

        # 2. Serial (Inspection/Via) Continuity
        max1, _ = get_inspection_sequences(f1['data'])
        _, min2 = get_inspection_sequences(f2['data'])

        # Categories that are expected to RESET to 00 in every file (Protocol)
        # We check if the prefix contains these keywords
        protocol_keywords = ['via-h2-', 'via-2h-', 'via-2h-x']

        # Check all categories found in the previous file
        for cat in max1.keys():
            if cat in ['via-c2-', 'via-2c-']:
                continue
            prev_max = max1[cat]
            next_start = min2.get(cat)

            if next_start is not None:
                # Logic: If it's a protocol, it should start at 00 or 01. 
                # Otherwise, it should continue from prev_max + 1.
                is_protocol = any(cat.startswith(k) for k in protocol_keywords)
                
                if is_protocol:
                    status = "OK" if next_start in [0, 1] else f"ERR (Exp 00/01)"
                else:
                    status = "OK" if next_start == prev_max + 1 else f"ERR (Exp {prev_max+1:02})"
                
                serial_rows.append([
                    trans_name,
                    cat.upper().rstrip("-"),
                    format_val(prev_max),
                    format_val(next_start),
                    status
                ])
            else:
                # Category might have ended in previous file
                pass

        # Also check categories that started NEW in the next file (if needed for report completeness)
        for cat in min2.keys():
            if cat in ['via-c2-', 'via-2c-']:
                continue
            if cat not in max1:
                next_start = min2[cat]
                serial_rows.append([
                    trans_name,
                    cat.upper().rstrip("-"),
                    "--",
                    format_val(next_start),
                    "NEW"
                ])

    # 3. Structural Integrity Audit (Header/Footer Protocols)
    struct_headers = ["File", "Header (ChargeOut->via-h2-02)", "Footer (via-2h-x0->ChargeIn)", "Status"]
    struct_rows = []
    
    for f_info in all_data:
        wps = f_info['data']
        node_names = [wp.get('Node_info', '') for wp in wps]
        
        # Header check (ChargeOut and via-h2-02 or equivalent in first 10)
        first_10 = node_names[:10]
        has_charge_out = any("ChargeOut" in name for name in first_10)
        has_via_start = any(any(v in name for v in ["via-h2-02", "via-c2-00", "via-c2-02", "via-219"]) for name in first_10)
        header_status = "OK" if (has_charge_out and has_via_start) else "MISSING"
        if not has_charge_out: header_status += " (No ChargeOut)"
        if not has_via_start: header_status += " (No via start)"
        
        # Footer check (via-2h-x0 and ChargeIn or equivalent in last 10)
        has_any_charge_in = any("ChargeIn" in name for name in node_names)
        if has_any_charge_in:
            last_10 = node_names[-10:]
            has_charge_in = any("ChargeIn" in name for name in last_10)
            has_via_end = any(any(v in name for v in ["via-2h-x0", "via-2c-13", "via-278", "via-211"]) for name in last_10)
            footer_status = "OK" if (has_charge_in and has_via_end) else "MISSING"
            if not has_charge_in: footer_status += " (No ChargeIn)"
            if not has_via_end: footer_status += " (No via end)"
        else:
            footer_status = "N/A (No ChargeIn)"
            
        status = "OK" if (header_status == "OK" and (not has_any_charge_in or footer_status == "OK")) else "FAIL"
        
        struct_rows.append([
            os.path.basename(f_info['path']),
            header_status,
            footer_status,
            status
        ])

    summary_rows.append(["Total Waypoints", total_wps])
    summary_rows.append(["Total Via Points", via_count])
    summary_rows.append(["Total Inspection Points", ins_count])
    
    # Optional: Breakdown of top-level inspections
    for cat, count in sorted(cat_summary.items()):
        if not cat.startswith('via'):
             summary_rows.append([f"  > {cat.upper().rstrip('-')}", count])

    print_table(struct_headers, struct_rows, title="MISSION STRUCTURAL INTEGRITY (Header/Footer Protocol)")
    print_table(summary_headers, summary_rows, title="MISSION WAYPOINT SUMMARY")
    
    # 4. Inspection Distribution Table
    sorted_dist_cats = sorted(list(dist_cats))
    dist_headers = ["File"] + [c.upper().rstrip("-") for c in sorted_dist_cats] + ["INSPECTION TOTAL", "VIA TOTAL", "TOTAL WAYPOINTS"]
    dist_rows = []
    for f_info in all_data:
        wps = f_info['data']
        fname = os.path.basename(f_info['path'])
        row = [fname]
        ins_total = 0
        for cat in sorted_dist_cats:
            count = file_counts[fname].get(cat, 0)
            row.append(count if count > 0 else "-")
            ins_total += count
        
        via_total = file_counts[fname].get('__VIA__', 0)
        row.append(ins_total)
        row.append(via_total)
        row.append(len(wps))
        dist_rows.append(row)
    
    print_table(dist_headers, dist_rows, title="MISSION INSPECTION DISTRIBUTION (Per-File Breakdown)")

    if serial_rows:
        print_table(serial_headers, serial_rows, title="MISSION SERIAL CONTINUITY (Inspection/Via Numbering)")
    else:
        print("\nNo cross-file inspection sequences found to audit.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check continuity between waypoint JSON files.")
    parser.add_argument("files", nargs="*", help="List of JSON files in sequence.")
    
    args = parser.parse_args()
    
    # Resolve project root dynamically (one level up from scripts directory)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    default_files = [
        os.path.join(project_root, "resource/path/final_dry_full.json"),
        os.path.join(project_root, "resource/path/final_packing.json"),
        os.path.join(project_root, "resource/path/final_filling.json"),
        # os.path.join(project_root, "resource/path/wet_zone_12-1x.json"),
        # os.path.join(project_root, "resource/path/wet_zone_12-2x.json"),
        # os.path.join(project_root, "resource/path/wet_zone_3x.json"),
        # os.path.join(project_root, "resource/path/dry_zone.json"),
        # os.path.join(project_root, "resource/path/dry_zone_2nd.json"),
        # os.path.join(project_root, "resource/path/record-filling.json")
    ]
    
    files_to_check = args.files if args.files else default_files
    check_continuity(files_to_check)
