import json
import networkx as nx
import matplotlib.pyplot as plt
import os
from collections import defaultdict
import math
import argparse

def create_directed_graph_from_waypoints(json_file_path, output_image_path):
    """
    Creates and visualizes a directed graph from a JSON file containing waypoint data.
    Nodes are waypoints, and edges represent the sequence of movement.
    Nodes are positioned using their PosX and PosY coordinates.
    """
    # 1. Load waypoints from JSON
    try:
        with open(json_file_path, 'r') as f:
            waypoints_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_file_path}")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_file_path}")
        return

    G = nx.DiGraph()
    node_colors_list = []
    node_display_labels = {}

    # Define color palette for different waypoint types
    COLOR_CHARGE = '#9370DB'     # MediumPurple
    COLOR_VIA = '#ADD8E6'        # LightBlue
    COLOR_INSPECTION = '#FFA500' # Orange
    COLOR_DEFAULT = '#808080'    # Grey (for any unclassified nodes)

    # Keywords for identifying inspection points
    inspection_keywords = ['acoustic', 'visual', 'thermal', 'loto', 'leaked', 'vibration', 'asset']

    prev_node_id = None
    for i, wp in enumerate(waypoints_data):
        node_info = wp.get('Node_info', f"Waypoint_{i}")
        
        # Create a unique ID for the node using Node_info and its index in the list.
        unique_node_id = f"{node_info}_{i}"

        # Add node to graph
        G.add_node(unique_node_id, data=wp) 

        # Determine node color based on its type
        current_color = COLOR_DEFAULT
        name_lower = node_info.lower()
        if 'charge' in name_lower:
            current_color = COLOR_CHARGE
        elif 'via' in name_lower:
            current_color = COLOR_VIA
        elif any(kw in name_lower for kw in inspection_keywords) or wp.get('PointInfo', 0) == 1:
            current_color = COLOR_INSPECTION
        
        # Store color for later use
        node_colors_list.append(current_color)

        # Determine display label
        if current_color == COLOR_INSPECTION:
            display_label = node_info.split('_')[-1]
        else:
            display_label = node_info
        node_display_labels[unique_node_id] = display_label

        # Add directed edge from the previous node to the current node
        if prev_node_id is not None:
            G.add_edge(prev_node_id, unique_node_id)
        
        prev_node_id = unique_node_id

    # 2. Calculate Slanted-Column Positions from JSON (v6)
    pos = {}
    scaling_factor = 80.0 # High-resolution scaling
    
    # Large thresholds for clear separation of 10pt font label boxes
    threshold_x = 250.0 
    threshold_y = 70.0  
    
    # Slanted column shifts: mostly vertical for alignment, slightly horizontal for "stack" feel
    step_x = 10.0 
    step_y = 80.0

    placed_positions = [] # List of final (x, y) coordinates

    for i, wp in enumerate(waypoints_data):
        node_info = wp.get('Node_info', f"Waypoint_{i}")
        unique_node_id = f"{node_info}_{i}"
        
        # Base scaled coordinates from JSON
        x = wp.get('PosX', 0.0) * scaling_factor
        y = wp.get('PosY', 0.0) * scaling_factor
        
        # Slanted-Column logic: deterministic vertical-primary shift for overlaps
        collision = True
        while collision:
            collision = False
            for px, py in placed_positions:
                # Rectangular check to ensure no box overlap
                if abs(x - px) < threshold_x and abs(y - py) < threshold_y:
                    # Shift primarily upward to create an aligned stack
                    x += step_x
                    y += step_y
                    collision = True
                    break
        
        pos[unique_node_id] = (x, y)
        placed_positions.append((x, y))

    # 3. Visualize the graph
    plt.figure(figsize=(25, 15))
    
    # 4. Draw edges: straight lines, dark gray, decent thickness
    nx.draw_networkx_edges(G, pos, 
                           edgelist=G.edges(), 
                           arrowstyle='-|>', 
                           arrowsize=20, 
                           edge_color='#555555', # Dark gray
                           width=1.2, 
                           alpha=0.8,
                           min_source_margin=60, # Clearance for label boxes
                           min_target_margin=60) # Clearance for label boxes

    # 5. Draw label boxes as the nodes (no circles)
    for node_id, (x, y) in pos.items():
        label = node_display_labels.get(node_id, "")
        
        plt.text(x, y, label, 
                 fontsize=10, 
                 fontweight='bold', 
                 ha='center', 
                 va='center',
                 bbox=dict(boxstyle='round,pad=0.3', 
                           fc='white', 
                           ec='#333333', 
                           lw=1.5, 
                           alpha=1.0))

    plt.title(f"Slanted-Column Waypoint Graph (V6) (Scale: {scaling_factor}x)", size=16)
    plt.axis('off')
    plt.tight_layout()
    
    # Ensure the output directory exists
    output_dir = os.path.dirname(output_image_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    fig = plt.gcf()
    def on_close(event):
        fig.savefig(output_image_path, dpi=300)
        print(f"Graph visualization saved to {output_image_path}")

    fig.canvas.mpl_connect('close_event', on_close)
    print("Showing graph visualization. The image will be saved when you close the window.")
    plt.show()

# --- Example Usage ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create and visualize a directed graph from a waypoint JSON file.")
    parser.add_argument("--input", "-i", type=str, help="Path to the waypoint JSON file.")
    parser.add_argument("--output", "-o", type=str, help="Path where the output graph image will be saved.")
    
    args = parser.parse_args()

    # Default paths if arguments are not provided
    json_file = args.input if args.input else "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/waypoints/wet_zone_12-1x.json"
    output_image = args.output if args.output else "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/scripts/waypoint_graph_wet_zone_12-1x.png"

    create_directed_graph_from_waypoints(json_file, output_image)