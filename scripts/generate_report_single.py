import json
import os

file_path = "/home/robinz/Gensurv/NestleCat/X30_GS_Simulator/resource/path/final_dry_first_floor_test.json"

inspection_types = ["asset", "gauge", "loto", "thermal", "leakage", "vibration"]
# Use all zones found in this file that are not empty
target_zones = ["dry1-2", "dry3", "wet1-2", "wet1", "packing-area"] 

def get_inspection_type(node):
    node_info = node.get("Node_info", "").lower()
    insp = node.get("Inspection", "").lower()
    
    if insp == "sit" or "sit" in node_info: return "sit"
    if "loto" in node_info: return "loto"
    if "asset" in insp: return "asset"
    if "gauge" in insp: return "gauge"
    if "thermal" in insp: return "thermal"
    if "leakage" in insp: return "leakage"
    if "vibration" in insp: return "vibration"
    if "asset" in node_info: return "asset"
    if "gauge" in node_info: return "gauge"
    if "thermal" in node_info: return "thermal"
    if "leak" in node_info: return "leakage"
    if "vib" in node_info: return "vibration"
    return None

results = {z: {t: 0 for t in inspection_types} for z in target_zones}
points_details = []

try:
    with open(file_path, "r") as fh:
        data = json.load(fh)
        for p in data:
            zone = p.get("Zone", "")
            itype = get_inspection_type(p)
            if itype and itype in inspection_types:
                if zone in target_zones:
                    results[zone][itype] += 1
                points_details.append({
                    "node_info": p.get("Node_info", "-"),
                    "zone": zone,
                    "type": itype
                })
except FileNotFoundError:
    pass

html_content = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{
    margin: 0.5in;
}}
body {{
    font-family: Arial, sans-serif;
}}
table {{
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 20px;
}}
th, td {{
    border: 1px solid black;
    padding: 8px;
    text-align: center;
}}
th {{
    background-color: #f2f2f2;
}}
</style>
</head>
<body>

<h1>สรุปจุด Inspection (final_dry_first_floor_test.json)</h1>

<h2>1. ตารางสรุปจำนวนจุด inspection ของแต่ละ zone</h2>
<table>
    <tr>
        <th>Zone</th>
"""
for t in inspection_types:
    html_content += f"<th>{t.capitalize()}</th>"
html_content += "<th>Total</th></tr>"

grand_total = 0
total_by_type = {t: 0 for t in inspection_types}

for z in target_zones:
    # only show zones that have points
    zone_total = sum(results[z][t] for t in inspection_types)
    if zone_total > 0:
        html_content += f"<tr><td>{z}</td>"
        for t in inspection_types:
            html_content += f"<td>{results[z][t]}</td>"
            total_by_type[t] += results[z][t]
        html_content += f"<td><b>{zone_total}</b></td></tr>"
        grand_total += zone_total

html_content += "<tr><td><b>Total</b></td>"
for t in inspection_types:
    html_content += f"<td><b>{total_by_type[t]}</b></td>"
html_content += f"<td><b>{grand_total}</b></td></tr>"

html_content += """
</table>

<h2>2. รายละเอียดจุด Inspection ทั้งหมด</h2>
<table>
    <tr>
        <th>ลำดับ</th>
        <th>Node Info</th>
        <th>Zone</th>
        <th>ประเภท Inspection</th>
    </tr>
"""

for i, pt in enumerate(points_details, 1):
    html_content += f"""
    <tr>
        <td>{i}</td>
        <td>{pt['node_info']}</td>
        <td>{pt['zone']}</td>
        <td>{pt['type'].capitalize()}</td>
    </tr>
    """

html_content += """
</table>
</body>
</html>
"""

with open("/home/robinz/Gensurv/NestleCat/X30_GS_Simulator/dry_first_floor_report.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("HTML generated.")
