import json
import os
import re
import difflib
from PIL import Image, ImageDraw
import yaml
from docx import Document

base_path = "/home/nontanan/Gensurv/NestleCat"
json_path = os.path.join(base_path, "gs_cat/src/x30_udp_bridge/path/wet_zone.json")
docx_path = os.path.join(base_path, "nestle_cat_waypoints_updated.docx")
yaml_path = os.path.join(base_path, "Nestle-full.yaml")
map_path = os.path.join(base_path, "Nestle-full")

# --- MATCHING LOGIC (from compare_waypoints_v2.py) ---

def get_parts(name):
    if not name: return "", "", ""
    name = name.lower().strip()
    if name == "charge" or name == "home":
        return "SPECIAL", "home", ""

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

def process_list(raw_list):
    processed = []
    for r in raw_list:
        z, s, n = get_parts(r)
        processed.append({'raw': r, 'zone': z, 'stem': s, 'num': n, 'id': f"{z}_{s}{n}"})
    return processed

# 1. Load data
with open(json_path, 'r') as f:
    json_all_data = json.load(f)

# Filter JSON points (exclude via, test, unnamed)
json_filtered_data = []
for p in json_all_data:
    node_info = p.get("Node_info", "")
    if node_info is None: continue
    name = node_info.strip()
    if not name or name == "-" or "via" in name.lower() or "test" in name.lower():
        continue
    json_filtered_data.append(p)

json_points = []
for p in json_filtered_data:
    r = p["Node_info"]
    z, s, n = get_parts(r)
    json_points.append({'raw': r, 'zone': z, 'stem': s, 'num': n, 'id': f"{z}_{s}{n}", 'pos': (p['PosX'], p['PosY'])})

doc = Document(docx_path)
docx_raw = []
for table in doc.tables:
    for row in table.rows[1:]:
        name = row.cells[1].text.strip()
        if name: docx_raw.append(name)

docx_points = process_list(docx_raw)

# 2. Matching
matches = []
unmatched_json = list(json_points)
unmatched_docx = list(docx_points)

# Stage 0: Special EXACT
to_remove_j = []
for j in unmatched_json:
    if j['id'] == "SPECIAL_home":
        for d in unmatched_docx:
            if d['id'] == "SPECIAL_home":
                matches.append((j, d, "MATCH"))
                to_remove_j.append(j)
                unmatched_docx.remove(d)
                break
for j in to_remove_j: unmatched_json.remove(j)

# Stage 0.5: Exact RAW Match
to_remove_j = []
for j in unmatched_json:
    for d in unmatched_docx:
        if j['raw'].lower().strip() == d['raw'].lower().strip():
            matches.append((j, d, "MATCH"))
            to_remove_j.append(j)
            unmatched_docx.remove(d)
            break
for j in to_remove_j: unmatched_json.remove(j)

# Stage 1: Exact ID
to_remove_j = []
for j in unmatched_json:
    for d in unmatched_docx:
        if j['id'] == d['id']:
            matches.append((j, d, "MATCH"))
            to_remove_j.append(j)
            unmatched_docx.remove(d)
            break
for j in to_remove_j: unmatched_json.remove(j)

# Stage 2: Zone + Num Match (STEM-MIS)
to_remove_j = []
for j in unmatched_json:
    if not j['num']: continue
    candidates = [d for d in unmatched_docx if j['zone'] == d['zone'] and j['num'] == d['num']]
    if len(candidates) == 1:
        d = candidates[0]
        matches.append((j, d, "STEM-MIS"))
        to_remove_j.append(j)
        unmatched_docx.remove(d)
for j in to_remove_j: unmatched_json.remove(j)

# Store results for mapping
point_status_map = [] # List of (x, y, color)
status_colors = {
    "MATCH": "green",
    "STEM-MIS": "red",
    "ZONE-MIS": "red", # Treating zone mismatch as red too
    "SIMILAR": "red",
    "DUPLICATE": "blue",
    "JSON-ONLY": "gray"
}

for j, d, status in matches:
    point_status_map.append((j['pos'][0], j['pos'][1], status_colors.get(status, "gray")))

for j in unmatched_json:
    already_matched = [m for m in matches if m[0] and m[0]['id'] == j['id']]
    if already_matched:
        point_status_map.append((j['pos'][0], j['pos'][1], status_colors["DUPLICATE"]))
    else:
        point_status_map.append((j['pos'][0], j['pos'][1], status_colors["JSON-ONLY"]))

# --- MAP RENDERING ---

with open(yaml_path, 'r') as f:
    map_meta = yaml.safe_load(f)

origin = map_meta['origin'] # [x, y, yaw]
resolution = map_meta['resolution']

# Load Image
img = Image.open(map_path)
img = img.convert("RGB")
width, height = img.size
draw = ImageDraw.Draw(img)

def world_to_pixel(x, y):
    px = int((x - origin[0]) / resolution)
    py = int(height - 1 - (y - origin[1]) / resolution)
    return px, py

print(f"Drawing {len(point_status_map)} points on map {width}x{height}...")

# Draw points
for x, y, color in point_status_map:
    px, py = world_to_pixel(x, y)
    if 0 <= px < width and 0 <= py < height:
        r = 10 # Marker radius
        draw.ellipse([px-r, py-r, px+r, py+r], fill=color, outline="black")

output_path = os.path.join(base_path, "waypoint_map.png")
img.save(output_path)
print(f"Map saved to {output_path}")
