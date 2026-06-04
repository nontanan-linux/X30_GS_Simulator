#!/usr/bin/env python3
import os
import csv
import argparse
import matplotlib.pyplot as plt

def generate_graph(csv_file, output_image):
    if not os.path.exists(csv_file):
        print(f"Error: File {csv_file} not found.")
        return

    x_data, y_data, z_data, ping_data = [], [], [], []
    
    print(f"Reading data from {csv_file}...")
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                x_data.append(float(row['x']))
                y_data.append(float(row['y']))
                z_data.append(float(row['z']))
                ping_data.append(float(row['ping']))
            except ValueError:
                continue

    if not x_data:
        print("Error: No valid data found in CSV.")
        return

    x_connected = [x_data[i] for i in range(len(ping_data)) if ping_data[i] != -1.0]
    y_connected = [y_data[i] for i in range(len(ping_data)) if ping_data[i] != -1.0]
    z_connected = [z_data[i] for i in range(len(ping_data)) if ping_data[i] != -1.0]
    ping_connected = [ping_data[i] for i in range(len(ping_data)) if ping_data[i] != -1.0]

    x_dropped = [x_data[i] for i in range(len(ping_data)) if ping_data[i] == -1.0]
    y_dropped = [y_data[i] for i in range(len(ping_data)) if ping_data[i] == -1.0]
    z_dropped = [z_data[i] for i in range(len(ping_data)) if ping_data[i] == -1.0]

    print(f"Found {len(x_connected)} connected points and {len(x_dropped)} dropped points.")
    print("Generating 2D plot...")
    
    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111)

    if x_connected:
        scatter = ax.scatter(x_connected, y_connected, c=ping_connected, 
                             cmap='jet', edgecolor='none', alpha=0.8, s=40, label='Connected Signal')
        cbar = fig.colorbar(scatter, ax=ax, pad=0.1)
        cbar.set_label('Network Latency (ms)', rotation=270, labelpad=15)

    if x_dropped:
        ax.scatter(x_dropped, y_dropped, color='red', marker='X', s=150, 
                   edgecolor='black', label='Absolute Dead Zone (Drop)')

    ax.set_title(f"Network Latency Map", fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel("Robot Position X (meters)", fontsize=10, labelpad=10)
    ax.set_ylabel("Robot Position Y (meters)", fontsize=10, labelpad=10)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper right')
    

    plt.savefig(output_image, bbox_inches='tight', dpi=150)
    print(f"2D plot graph image file saved successfully: {output_image}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate 3D Latency Graph from CSV")
    parser.add_argument('--input', type=str, default='/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/network/network_spatial_log_20260526_175257.csv', help='Input CSV file path')
    parser.add_argument('--output', type=str, default='/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/network/network_spatial_log_20260526_175257.png', help='Output PNG file path')
    args = parser.parse_args()
    
    generate_graph(args.input, args.output)