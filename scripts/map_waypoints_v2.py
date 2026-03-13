import json
import os
import re
import difflib
from PIL import Image, ImageDraw, ImageFont
import yaml
from docx import Document

base_path = "/home/nontanan/Gensurv/NestleCat"
json_path = os.path.join(base_path, "gs_cat/src/x30_udp_bridge/path/wet_zone.json")
docx_path = os.path.join(base_path, "nestle_cat_waypoints_updated.docx")
yaml_path = os.path.join(base_path, "Nestle-full.yaml")
map_path = os.path.join(base_path, "Nestle-full")

# --- CONFIGURATION ---
SHOW_LABELS = True  # Set to False to hide waypoint labels on the map
DEBUG_MODE = True   # Set to True to only show DUPLICATE, STEM-MIS, and JSON-ONLY points

# --- MATCHING LOGIC ---

def get_parts(name):
    if not name: return "", "", ""
    name = name.lower().strip()
    if name == "charge" or name == "home":
        return "SPECIAL", "home", ""

    # Normalization
    name = name.replace('arcustics', 'acoustic').replace('acostic', 'acoustic').replace('vistal', 'visual')
    name = name.replace('thermal_thermal', 'thermal')
    name = re.sub(r'_(1nd|2nd|3rd|[0-9]+th)$', '', name)
    name = name.replace('_1_xxx', '')
    
    zone = "-"
    rest = name
    if name.startswith('wet12'):
        zone = "wet12"
        rest = name[5:].lstrip('_')
    elif name.startswith('wet3'):
        zone = "wet3"
        rest = name[4:].lstrip('_')
    
    stem = rest
    num_str = ""
    match = re.search(r'^(.*?)(\d+)$', rest)
    if match:
        stem, num_str = match.groups()
        num_str = f"{int(num_str):02d}"
    
    return zone, stem, num_str

def process_point(p):
    node_info = p.get("Node_info", "")
    if node_info is None: return None
    name = node_info.strip()
    if not name or name == "-" or "via" in name.lower() or "test" in name.lower():
        return None
    
    z, s, n = get_parts(name)
    return {
        'raw': name,
        'zone': z,
        'stem': s,
        'num': n,
        'id': f"{z}_{s}{n}",
        'pos': (p['PosX'], p['PosY']),
        'value': p.get('Value', '?')
    }

# 1. Load DOCX
doc = Document(docx_path)
docx_raw = []
for table in doc.tables:
    for row in table.rows[1:]:
        name = row.cells[1].text.strip()
        if name: docx_raw.append(name)

processed_docx = []
for r in docx_raw:
    z, s, n = get_parts(r)
    processed_docx.append({'raw': r, 'zone': z, 'stem': s, 'num': n, 'id': f"{z}_{s}{n}"})

# 2. Load primary JSON (wet_zone.json)
all_json_points = []
with open(json_path, 'r') as f:
    data = json.load(f)
    for p in data:
        item = process_point(p)
        if item: all_json_points.append(item)

# 3. Matching Logic (One-to-one to find baseline status)
id_to_status = {}
unmatched_docx = list(processed_docx)

# Sort by Value to ensure stable matching
all_json_points.sort(key=lambda x: x['value'])

# Stage 0 & 0.5: Exact
for p in all_json_points:
    if p['id'] in id_to_status: continue
    
    match = None
    if p['id'] == "SPECIAL_home":
        match = next((d for d in unmatched_docx if d['id'] == "SPECIAL_home"), None)
    
    if not match:
        # Exact Name Match
        match = next((d for d in unmatched_docx if d['raw'].lower().strip() == p['raw'].lower().strip()), None)
    
    if not match:
        # Normalized ID Match
        match = next((d for d in unmatched_docx if d['id'] == p['id']), None)
        
    if match:
        id_to_status[p['id']] = "MATCH"
        unmatched_docx.remove(match)

# Stage 2: STEM-MIS
for p in all_json_points:
    if p['id'] in id_to_status: continue
    if not p['num']: continue
    candidates = [d for d in unmatched_docx if p['zone'] == d['zone'] and p['num'] == d['num']]
    if len(candidates) == 1:
        id_to_status[p['id']] = "STEM-MIS"
        unmatched_docx.remove(candidates[0])

# --- MAP RENDERING ---

with open(yaml_path, 'r') as f:
    map_meta = yaml.safe_load(f)

origin = map_meta['origin']
resolution = map_meta['resolution']

img = Image.open(map_path).convert("RGB")
width, height = img.size
draw = ImageDraw.Draw(img)

try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 18)
except:
    font = None

def world_to_pixel(x, y):
    px = int((x - origin[0]) / resolution)
    py = int(height - 1 - (y - origin[1]) / resolution)
    return px, py

status_colors = {
    "MATCH": (0, 200, 0),        # Green
    "STEM-MIS": (255, 0, 0),      # Red
    "JSON-ONLY": (128, 128, 128), # Gray
    "DUPLICATE": (0, 0, 255),     # Blue
    "DUPLICATE_LIGHT": (135, 206, 250), # Light Blue
}

# Pre-calculate counts for Debug Mode
id_total_counts = {}
for p in all_json_points:
    id_total_counts[p['id']] = id_total_counts.get(p['id'], 0) + 1

id_occurrence_tracker = {}
duplicates_data = []

print(f"Plotting total {len(all_json_points)} JSON points from {os.path.basename(json_path)}...")

for p in all_json_points:
    px, py = world_to_pixel(p['pos'][0], p['pos'][1])
    
    occ = id_occurrence_tracker.get(p['id'], 0) + 1
    id_occurrence_tracker[p['id']] = occ
    
    status = id_to_status.get(p['id'], "JSON-ONLY")
    
    # abnormal if: it's a duplicate (any occurrence) OR it's not a perfect match
    is_not_match = (id_total_counts.get(p['id'], 0) > 1) or (status != "MATCH")
    
    if DEBUG_MODE and not is_not_match:
        # In debug mode, skip perfect matches (only plot issues/non-matches)
        continue

    # Determine Color
    if occ > 1:
        color = status_colors["DUPLICATE"] if occ % 2 == 0 else status_colors["DUPLICATE_LIGHT"]
        duplicates_data.append(p)
    else:
        color = status_colors.get(status, (128, 128, 128))

    # Marker
    r = 7
    draw.ellipse([px-r, py-r, px+r, py+r], fill=color, outline="black")
    
    # Label
    if SHOW_LABELS:
        label = f"{p['raw']}\n(V:{p['value']})"
        if occ > 1:
            label += f" D{occ}"
        
        if font:
            draw.text((px + 8, py - 20), label, fill="black", font=font)
        else:
            draw.text((px + 8, py - 20), label, fill="black")

output_path = os.path.join(base_path, "waypoint_map_v2.png")
img.save(output_path)
if DEBUG_MODE:
    print(f"Debug map (Non-matches only) saved to {output_path}")
else:
    print(f"Full map saved to {output_path}")

print("\n--- Duplicate Coordinate Analysis (within wet_zone.json) ---")
if not duplicates_data:
    print("No duplicates found.")
else:
    from collections import defaultdict
    grouped = defaultdict(list)
    for p in all_json_points:
        if id_total_counts[p['id']] > 1:
            grouped[p['id']].append(p)
    
    for id_val, points in grouped.items():
        print(f"\nID: {id_val}")
        for i, pt in enumerate(points):
            print(f"  {i+1}. Value: {pt['value']}, Pos: ({pt['pos'][0]:.4f}, {pt['pos'][1]:.4f})")
