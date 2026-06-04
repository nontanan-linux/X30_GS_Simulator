import json
import csv
import sys
import os
import argparse

def convert_json_to_csv(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"Error: Input path '{input_path}' does not exist.")
        sys.exit(1)
        
    if os.path.isdir(input_path):
        # Determine output directory
        out_dir = output_path if output_path else input_path
        if not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
            
        json_files = [f for f in os.listdir(input_path) if f.endswith('.json')]
        if not json_files:
            print(f"No JSON files found in directory '{input_path}'.")
            return
            
        print(f"Found {len(json_files)} JSON files in directory '{input_path}'. Converting...")
        for filename in json_files:
            in_file = os.path.join(input_path, filename)
            out_file = os.path.join(out_dir, os.path.splitext(filename)[0] + ".csv")
            process_single_file(in_file, out_file)
    else:
        # It's a single file
        if not output_path:
            base, _ = os.path.splitext(input_path)
            output_path = base + ".csv"
        process_single_file(input_path, output_path)

def process_single_file(input_json_path, output_csv_path):
    with open(input_json_path, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON in '{input_json_path}': {e}")
            return
            
    if not isinstance(data, list):
        print(f"Error: JSON content in '{input_json_path}' is not a list of waypoints.")
        return
        
    headers = ["x", "y", "z", "yaw", "name"]
    rows = []
    
    for idx, wp in enumerate(data):
        x = wp.get("PosX", 0.0)
        y = wp.get("PosY", 0.0)
        z = wp.get("PosZ", 0.0)
        yaw = wp.get("AngleYaw", 0.0)
        name = wp.get("Node_info", f"point_{idx}")
        
        rows.append([x, y, z, yaw, name])
        
    output_dir = os.path.dirname(output_csv_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        
    with open(output_csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
        
    print(f"Successfully converted '{input_json_path}' to '{output_csv_path}' ({len(rows)} points).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert waypoint path in .json to .csv only with [x, y, z, yaw, name]")
    parser.add_argument("input_path", nargs="?", help="Path to the input JSON file or directory containing JSON files")
    parser.add_argument("output_path", nargs="?", help="Path to the output CSV file or directory")
    
    args = parser.parse_args()
    
    input_path = args.input_path
    output_path = args.output_path
    
    if not input_path:
        # Default fallback to the directory containing path files
        input_path = "resource/path"
        
    convert_json_to_csv(input_path, output_path)
