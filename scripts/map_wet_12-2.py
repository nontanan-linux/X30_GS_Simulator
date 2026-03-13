import json
import yaml
import PIL.Image
import PIL.ImageDraw
import os
import argparse
import math

# Configuration
MAP_YAML = 'Nestle-full.yaml'
# MAP_IMAGE = 'Nestle-full'
MAP_IMAGE ='picture/edit/Nestle-full-edit02.pgm'
JSON_FILE = 'wet_zone_12-2.json'
OUTPUT_IMAGE = 'visualize_wet_12-2.png'
def draw_rviz_arrow(draw, u, v, yaw, color, length=25):
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
    draw.line([(u, v), (base_u, base_v)], fill=color, width=3)
    # Draw arrow head
    draw.polygon([(tip_u, tip_v), (p1_u, p1_v), (p2_u, p2_v)], fill=color)

def main():
    parser = argparse.ArgumentParser(description='Visualize waypoints on map')
    parser.add_argument('--show-names', type=lambda x: (str(x).lower() == 'true'), default=True, help='Show waypoint labels (default: True)')
    parser.add_argument('--name-style', type=str, choices=['full', 'number'], default='number', help='Label style: full or number (default: number)')
    parser.add_argument('--only-via', action='store_true', help='Show only via points (plus charge)')
    parser.add_argument('--only-inspection', action='store_true', help='Show only inspection points (plus charge)')
    args = parser.parse_args()

    # 1. Load Map YAML
    print(f"Loading {MAP_YAML}...")
    with open(MAP_YAML, 'r') as f:
        config = yaml.safe_load(f)
    
    resolution = config['resolution']
    origin_x, origin_y, _ = config['origin']

    # 2. Load Waypoints
    print(f"Loading {JSON_FILE}...")
    with open(JSON_FILE, 'r') as f:
        waypoints = json.load(f)

    # 3. Load Map Image
    print(f"Loading {MAP_IMAGE}...")
    img = PIL.Image.open(MAP_IMAGE).convert('RGB')
    draw = PIL.ImageDraw.Draw(img)
    width, height = img.size

    # Function to convert world to pixel
    def world_to_pixel(x, y):
        u = (x - origin_x) / resolution
        v = height - (y - origin_y) / resolution
        return u, v

    # 4. Draw Waypoints
    print(f"Drawing waypoints and paths...")
    print(f"Options: show_names={args.show_names}, only_via={args.only_via}, only_inspection={args.only_inspection}")
    
    prev_pos = None
    
    # Colors
    COLOR_VIA = (173, 216, 230)      # Light Blue
    COLOR_INSP = (255, 165, 0)       # Orange
    COLOR_CHARGE = (147, 112, 219)   # Purple (Charge)
    COLOR_PINK = (255, 105, 180)     # Pink (2nd Floor)
    COLOR_LINE = (200, 200, 200)     # Light Grey
    COLOR_RETURN = (0, 255, 0)       # Green

    # Find the index of the last inspection point (not via, not charge)
    last_insp_idx = -1
    for i, node in enumerate(waypoints):
        name = str(node.get('Node_info', '')).lower()
        if 'test' in name: continue
        if 'via' not in name and 'charge' not in name:
            last_insp_idx = i

    # If no 'charge' node is found, start drawing from the first node
    has_charge = any('charge' in str(node.get('Node_info', '')).lower() for node in waypoints)
    start_drawing = not has_charge
    
    drawn_text_bboxes = []
    
    def check_overlap(box1, box2):
        # box is [xmin, ymin, xmax, ymax]
        return not (box1[2] < box2[0] or box1[0] > box2[2] or box1[3] < box2[1] or box1[1] > box2[3])

    def push_apart(x, y, text):
        box = draw.textbbox((x, y), text)
        pad = 2
        box = [box[0]-pad, box[1]-pad, box[2]+pad, box[3]+pad]
        
        for _ in range(15): # Max attempts
            overlap = False
            for prev_box in drawn_text_bboxes:
                if check_overlap(box, prev_box):
                    overlap = True
                    # Push down and right slightly
                    y += 12
                    box = draw.textbbox((x, y), text)
                    box = [box[0]-pad, box[1]-pad, box[2]+pad, box[3]+pad]
                    break
            if not overlap:
                break
        drawn_text_bboxes.append(box)
        return x, y
        
    for i, node in enumerate(waypoints):
        name_orig = str(node.get('Node_info', ''))
        name = name_orig.lower()
        if 'test' in name:
            continue
        
        if 'charge' in name:
            start_drawing = True
            
        if not start_drawing:
            continue

        # Classification
        keywords = ['acoustic', 'visual', 'thermal', 'loto', 'leaked', 'vibration', 'asset']
        is_inspection = any(kw in name for kw in keywords)
        p_info = node.get('PointInfo', 0)
        is_charge = 'charge' in name
        
        # Determine specific type and base color
        map_id = node.get('MapID', 0)
        
        if 'via' in name:
            pt_type = 'via'
            color = COLOR_VIA
        elif is_charge:
            pt_type = 'charge'
            color = COLOR_CHARGE
        elif is_inspection or p_info == 1:
            pt_type = 'inspection'
            color = COLOR_INSP
        else:
            pt_type = 'inspection'
            color = COLOR_INSP

        # Rule: 2nd Floor (MapID != 0) is PINK
        if map_id != 0:
            color = COLOR_PINK

        # Determine line color
        current_line_color = COLOR_LINE
        if last_insp_idx != -1 and i > last_insp_idx:
            current_line_color = COLOR_RETURN
            # Also change point color if it's a via point
            if pt_type == 'via' and map_id == 0:
                color = COLOR_RETURN

        # Special case: Last inspection position is RED (User asked for red before? 
        # Actually in previous request user said "last inspection positionให้เป็นสีแดง")
        # I'll keep red for the last inspection point but user might want a new color?
        # User said "จุด charge ให้เป็นสีม่วง", "MapID=0 คือชั่น 1 ให้เป็นสีชมพู"
        # I'll keep (255, 0, 0) for the last inspection unless told otherwise.
        if i == last_insp_idx:
            color = (255, 0, 0) # Clear Red

        x, y = node['PosX'], node['PosY']
        yaw = node.get('AngleYaw', 0)
        u, v = world_to_pixel(x, y)
        
        arrow_len = 25

        # Draw line from previous point
        if prev_pos:
            draw.line([prev_pos, (u, v)], fill=current_line_color, width=1)
        
        # Draw Rviz-style arrow
        draw_rviz_arrow(draw, u, v, yaw, color, length=arrow_len)

        # Draw labels based on visibility flags
        if args.show_names and name_orig:
            should_show_label = True
            if args.only_via and pt_type not in ['via', 'charge']:
                should_show_label = False
            if args.only_inspection and pt_type not in ['inspection', 'charge']:
                should_show_label = False
            
            if should_show_label:
                # Text color matches the goal type or index
                label_color = (255, 255, 0) # Default Yellow for labels
                if i > last_insp_idx:
                    label_color = COLOR_RETURN

                if args.name_style == 'number':
                    # Show Task No. (Value + 1) instead of full name
                    task_no = node.get('Value', i) + 1
                    label_text = str(task_no)
                else:
                    # Extract only the inspection name (e.g., 'thermal01' from 'wet12_visual_thermal01')
                    if name_orig.startswith('wet12_') or name_orig.startswith('wet3_'):
                        label_text = name_orig.split('_')[-1]
                    else:
                        label_text = name_orig
                    
                final_x, final_y = push_apart(u + 10, v + 10, label_text)    
                draw.text((final_x, final_y), label_text, fill=label_color)

        prev_pos = (u, v)

    # 5. Save output
    img.save(OUTPUT_IMAGE)
    print(f"Visualization saved to {OUTPUT_IMAGE}")

if __name__ == "__main__":
    main()
