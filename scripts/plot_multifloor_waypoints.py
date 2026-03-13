import json
import yaml
import PIL.Image
import PIL.ImageDraw
import os
import math
from collections import defaultdict

# --- Configuration ---
INPUT_JSON_FILE = "/home/nontanan/Gensurv/NestleCat/gs_cat/30ea21af_dssmulti.json"

# Define map configurations for each MapID
# Ensure these paths are correct for your environment
MAP_CONFIGS = {
    0: [ # For MapID 0, plot on DSS-multifloor (removed extra [])
        {
            "yaml": "/home/nontanan/Gensurv/NestleCat/DSS-multifloor-20260108-125209/jueying.yaml",
            "image": "/home/nontanan/Gensurv/NestleCat/DSS-multifloor-20260108-125209/jueying.pgm",
            "output": "/home/nontanan/Gensurv/NestleCat/output_mapid_0_DSS-multifloor.png"
        }
    ],
    1: # For MapID 1, plot on both jueying and jueying2
        [{
            "yaml": "/home/nontanan/Gensurv/NestleCat/DSS-multifloor-20260108-125209/jueying.yaml",
            "image": "/home/nontanan/Gensurv/NestleCat/DSS-multifloor-20260108-125209/jueying.pgm",
            "output": "/home/nontanan/Gensurv/NestleCat/output_mapid_1_jueying.png"
        },
        {
            "yaml": "/home/nontanan/Gensurv/NestleCat/DSS-multifloor-20260108-125209/jueying2.yaml",
            "image": "/home/nontanan/Gensurv/NestleCat/DSS-multifloor-20260108-125209/jueying2.pgm",
            "output": "/home/nontanan/Gensurv/NestleCat/output_mapid_1_jueying2.png" # Distinct output name
        }]
}

# --- Drawing Helper Function ---
def draw_rviz_arrow(draw, u, v, yaw, color, length=25, width=3):
    """
    Draws an Rviz-style arrow on the PIL ImageDraw object.
    u, v: pixel coordinates of the arrow's base.
    yaw: orientation in radians.
    color: RGB tuple.
    length: total length of the arrow.
    width: line width for the shaft.
    """
    # Tip of the arrow
    tip_u = u + length * math.cos(yaw)
    tip_v = v - length * math.sin(yaw)  # PIL coordinates (y grows down)

    # Base of the arrow head (drawn back from tip)
    head_len = length * 0.4
    head_width = length * 0.25
    
    # Back along the axis
    base_u = tip_u - head_len * math.cos(yaw)
    base_v = tip_v + head_len * math.sin(yaw)
    
    # Points perpendicular to axis at base
    p1_u = base_u + head_width * math.sin(yaw)
    p1_v = base_v + head_width * math.cos(yaw)
    
    p2_u = base_u - head_width * math.sin(yaw)
    p2_v = base_v - head_width * math.cos(yaw)
    
    # Draw arrow shaft
    draw.line([(u, v), (base_u, base_v)], fill=color, width=width)
    # Draw arrow head
    draw.polygon([(tip_u, tip_v), (p1_u, p1_v), (p2_u, p2_v)], fill=color)

# --- Main Script ---
def main():
    # 1. Load Waypoints from JSON
    print(f"Loading waypoints from {INPUT_JSON_FILE}...")
    try:
        with open(INPUT_JSON_FILE, 'r') as f:
            all_waypoints = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input JSON file not found at {INPUT_JSON_FILE}")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {INPUT_JSON_FILE}")
        return

    # Group waypoints by MapID
    waypoints_by_mapid = defaultdict(list)
    for wp in all_waypoints:
        map_id = wp.get('MapID', 0)  # Default to 0 if MapID is missing
        waypoints_by_mapid[map_id].append(wp)

    # 2. Process each MapID group
    for map_id, waypoints in waypoints_by_mapid.items():
        if map_id not in MAP_CONFIGS:
            print(f"Warning: No map configuration found for MapID {map_id}. Skipping.")
            continue

        # Iterate through all configurations defined for this MapID
        for idx, config in enumerate(MAP_CONFIGS[map_id]):
            map_yaml_path = config["yaml"]
            map_image_path = config["image"]
            output_image_path = config["output"]

            print(f"\n--- Processing MapID {map_id} on map: {os.path.basename(map_image_path)} ---")
            print(f"Loading map YAML: {map_yaml_path}...")
            try:
                with open(map_yaml_path, 'r') as f:
                    map_meta = yaml.safe_load(f)
            except FileNotFoundError:
                print(f"Error: Map YAML file not found at {map_yaml_path}. Skipping this map configuration.")
                continue

            print(f"Loading map image: {map_image_path}...")
            try:
                img = PIL.Image.open(map_image_path).convert("RGB")
            except FileNotFoundError:
                print(f"Error: Map image file not found at {map_image_path}. Skipping this map configuration.")
                continue

            draw = PIL.ImageDraw.Draw(img)
            width, height = img.size
            origin = map_meta['origin']
            resolution = map_meta['resolution']

            # Function to convert world to pixel coordinates for the current map
            def world_to_pixel(x, y):
                px = int((x - origin[0]) / resolution)
                py = int(height - 1 - (y - origin[1]) / resolution) # Invert Y-axis for PIL
                return px, py

            print(f"Plotting {len(waypoints)} waypoints on MapID {map_id} for {os.path.basename(map_image_path)}...")
            for wp in waypoints:
                x, y = wp['PosX'], wp['PosY']
                yaw = wp.get('AngleYaw', 0.0)
                node_info = wp.get('Node_info', f"ID:{wp.get('Value', '?')}")

                px, py = world_to_pixel(x, y)

                # Draw arrow (Green for visibility)
                arrow_color = (0, 255, 0)
                draw_rviz_arrow(draw, px, py, yaw, arrow_color, length=20, width=2)

                # Draw label
                label_color = (255, 255, 255) # White text
                try:
                    font = PIL.ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
                except IOError:
                    font = PIL.ImageFont.load_default()
                
                draw.text((px + 10, py - 10), node_info, fill=label_color, font=font)

            # Save the output image
            img.save(output_image_path)
            print(f"Visualization for MapID {map_id} saved to {output_image_path}")

    print("\nScript finished.")

if __name__ == "__main__":
    main()