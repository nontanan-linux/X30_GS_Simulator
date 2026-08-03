#!/usr/bin/env python3
"""
manage_nodes_csv.py
Script to manage and update nodes.csv, ensuring fix_yaw attribute is present for all nodes.
"""

import csv
import os
import argparse

def process_nodes_csv(csv_path, default_fix_yaw=1, overwrite_existing=False, backup=True):
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} does not exist.")
        return False

    if backup:
        bak_path = csv_path + ".bak"
        with open(csv_path, 'r', encoding='utf-8') as src, open(bak_path, 'w', encoding='utf-8') as dst:
            dst.write(src.read())
        print(f"Created backup at {bak_path}")

    rows = []
    updated_count = 0
    via_count = 0
    inspection_count = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue

            node_id = row[0] if len(row) > 0 else ""
            node_name = row[1] if len(row) > 1 else ""
            node_type = row[4] if len(row) > 4 else ""

            # Check node classification
            full_str = f"{node_id} {node_name} {node_type}".lower()
            if 'via' in full_str:
                via_count += 1
            else:
                inspection_count += 1

            # Ensure row has enough columns up to index 7 (fix_yaw)
            # Column 0: ID
            # Column 1: Name
            # Column 2: Group
            # Column 3: Pose
            # Column 4: Type
            # Column 5: MapID
            # Column 6: Zone
            # Column 7: FixYaw (1 for True, 0 for False)
            while len(row) < 8:
                row.append("0")

            if overwrite_existing or str(row[7]).strip() == "":
                row[7] = str(default_fix_yaw)
                updated_count += 1

            rows.append(row)

    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        for row in rows:
            writer.writerow(row)

    print(f"Successfully processed {len(rows)} nodes in {csv_path}:")
    print(f"  - Via nodes: {via_count}")
    print(f"  - Inspection nodes: {inspection_count}")
    print(f"  - Nodes set with fix_yaw = {default_fix_yaw}: {updated_count}")
    return True

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_csv = os.path.normpath(os.path.join(script_dir, '../resource/nodes.csv'))

    parser = argparse.ArgumentParser(description="Manage and update nodes.csv with fix_yaw attributes")
    parser.add_argument('--csv', type=str, default=default_csv, help='Path to nodes.csv')
    parser.add_argument('--fix_yaw', type=int, choices=[0, 1], default=1, help='Default fix_yaw value (1=True, 0=False)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing fix_yaw values')
    parser.add_argument('--no_backup', action='store_true', help='Do not create .bak backup file')

    args = parser.parse_args()
    process_nodes_csv(
        csv_path=args.csv,
        default_fix_yaw=args.fix_yaw,
        overwrite_existing=args.overwrite,
        backup=not args.no_backup
    )

if __name__ == '__main__':
    main()
