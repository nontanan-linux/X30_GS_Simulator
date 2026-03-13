import json
import networkx as nx
import matplotlib.pyplot as plt
import os
from collections import defaultdict
import math

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
    node_raw_positions = {} # Store original (PosX, PosY)
    node_colors_list = []
    node_display_labels = {}
    
    # To handle overlapping nodes: group nodes by their exact (PosX, PosY)
    nodes_at_same_raw_position = defaultdict(list) # Key: (PosX, PosY) tuple, Value: list of (unique_node_id, original_index)

    # Define color palette for different waypoint types
    COLOR_CHARGE = '#9370DB'  # MediumPurple
    COLOR_VIA = '#ADD8E6'     # LightBlue
    COLOR_INSPECTION = '#FFA500' # Orange
    COLOR_DEFAULT = '#808080' # Grey (for any unclassified nodes)

    # Keywords for identifying inspection points (case-insensitive)
    inspection_keywords = ['acoustic', 'visual', 'thermal', 'loto', 'leaked', 'vibration', 'asset']

    prev_node_id = None
    for i, wp in enumerate(waypoints_data):
        node_info = wp.get('Node_info', f"Waypoint_{i}")
        pos_x = wp.get('PosX')
        pos_y = wp.get('PosY')
        
        # Create a unique ID for the node using Node_info and its index in the list.
        # This ensures uniqueness even if Node_info or Value fields are duplicated.
        unique_node_id = f"{node_info}_{i}"

        # Add node to graph, storing full waypoint data as an attribute
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
        
        # Store color for later use with nx.draw_networkx_nodes
        node_colors_list.append(current_color)

        # Determine display label: shorten inspection point names
        if current_color == COLOR_INSPECTION:
            # Extract the last part after an underscore, e.g., "thermal01" from "wet12_visual_thermal01"
            display_label = node_info.split('_')[-1]
        else:
            display_label = node_info
        node_display_labels[unique_node_id] = display_label

        # Store original position and group nodes by it for overlap detection
        if pos_x is not None and pos_y is not None:
            node_raw_positions[unique_node_id] = (pos_x, pos_y)
            nodes_at_same_raw_position[(pos_x, pos_y)].append((unique_node_id, i))
        else:
            print(f"Warning: Waypoint '{node_info}' (index {i}) missing PosX or PosY. Assigning (0,0) as placeholder.")
            node_raw_positions[unique_node_id] = (0, 0) # Placeholder
            nodes_at_same_raw_position[(0, 0)].append((unique_node_id, i))

        # Add directed edge from the previous node to the current node
        if prev_node_id is not None:
            G.add_edge(prev_node_id, unique_node_id)
        
        prev_node_id = unique_node_id

    # Calculate node size based on max label length for square nodes
    font_size = 8 # Base font size
    char_width_ratio = 0.6 # Approximate width of a character relative to font size
    char_height_ratio = 1.2 # Approximate height of a character relative to font size
    padding_factor = 1.1 # Reduced padding around the text within the node for a tighter fit

    max_label_len = 0
    for label in node_display_labels.values():
        max_label_len = max(max_label_len, len(label))

    # Calculate the required side length for the square node to fit the text
    # The side length should accommodate the maximum of the estimated width and height of the text, plus padding.
    node_side_length_pts = max(max_label_len * char_width_ratio * font_size, char_height_ratio * font_size) * padding_factor

    # Node side should be large enough for the text plus padding
    # networkx node_size is area, so it's side_length^2
    calculated_node_size = node_side_length_pts ** 2
    
    node_size_to_use = calculated_node_size # Use the calculated size directly, no minimum to allow smaller nodes

    # 2. Adjust positions for overlapping nodes
    node_final_positions = {}
    # Small distance to offset nodes in world units (adjust as needed)
    offset_distance = 0.5 
    
    for (raw_x, raw_y), group in nodes_at_same_raw_position.items():
        if len(group) > 1:
            # Apply a circular offset for overlapping nodes
            for j, (node_id, original_index) in enumerate(group):
                angle = 2 * math.pi * j / len(group)
                offset_x = offset_distance * math.cos(angle)
                offset_y = offset_distance * math.sin(angle)
                node_final_positions[node_id] = (raw_x + offset_x, raw_y + offset_y)
        else:
            node_id, _ = group[0]
            node_final_positions[node_id] = (raw_x, raw_y)

    # 3. Visualize the graph
    plt.figure(figsize=(18, 14)) # Adjust figure size for better visibility

    # Use the actual (PosX, PosY) for node positions.
    # If some nodes lack valid coordinates or if the graph is very dense,
    # a different layout algorithm (e.g., nx.spring_layout) might be more suitable.
    # For sequential paths with meaningful coordinates, direct positioning is usually best, with overlap adjustment.
    pos = node_final_positions

    # Draw nodes, edges, and labels
    nx.draw_networkx_nodes(G, pos, node_color=node_colors_list, node_size=node_size_to_use, alpha=0.9, linewidths=1, edgecolors='black', node_shape='s') # Changed node_shape to 's'
    nx.draw_networkx_edges(G, pos, edgelist=G.edges(), arrowstyle='->', arrowsize=20, edge_color='darkgray', width=1.5, alpha=0.7)
    nx.draw_networkx_labels(G, pos, labels=node_display_labels, font_size=font_size, font_color='black', font_weight='bold')

    plt.title(f"Directed Graph of Waypoints from {os.path.basename(json_file_path)}", size=16)
    plt.axis('off') # Hide axes for a cleaner graph visualization
    plt.tight_layout() # Adjust layout to prevent labels overlapping
    
    # Ensure the output directory exists
    output_dir = os.path.dirname(output_image_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    plt.savefig(output_image_path, dpi=300) # Save with higher DPI for better quality
    print(f"Graph visualization saved to {output_image_path}")

# --- Example Usage ---
if __name__ == "__main__":
    json_file = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/waypoints/wet_zone_12-1x.json"
    output_image = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/scripts/waypoint_graph_wet_zone_12-1x.png"

    create_directed_graph_from_waypoints(json_file, output_image)