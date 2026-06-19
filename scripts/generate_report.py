import json
import os

files = [
    "/home/robinz/Gensurv/NestleCat/X30_GS_Simulator/resource/path/final_dry_first_floor_test.json",
    "/home/robinz/Gensurv/NestleCat/X30_GS_Simulator/resource/path/final_dry_second_floor.json",
    "/home/robinz/Gensurv/NestleCat/X30_GS_Simulator/resource/path/final_packing.json",
    "/home/robinz/Gensurv/NestleCat/X30_GS_Simulator/resource/path/final_filling.json"
]

target_zones = ["dry1-2", "dry3", "packing3", "filling2", "filling3"]
inspection_types = ["asset", "gauge", "loto", "thermal", "leakage", "vibration"]

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

for f in files:
    try:
        with open(f, "r") as fh:
            data = json.load(fh)
            for p in data:
                zone = p.get("Zone", "")
                if zone not in target_zones: continue
                itype = get_inspection_type(p)
                if itype and itype in inspection_types:
                    results[zone][itype] += 1
    except FileNotFoundError:
        pass

total_by_type = {t: sum(results[z][t] for z in target_zones) for t in inspection_types}
grand_total = sum(total_by_type.values())

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

<h1>สรุปจุด Inspection</h1>

<h2>ตารางสรุปจำนวนจุด inspection ของแต่ละ zone (ไม่นับ sit)</h2>
<table>
    <tr>
        <th>Zone</th>
"""
for t in inspection_types:
    html_content += f"<th>{t.capitalize()}</th>"
html_content += "<th>Total</th></tr>"

for z in target_zones:
    html_content += f"<tr><td>{z}</td>"
    zone_total = sum(results[z][t] for t in inspection_types)
    for t in inspection_types:
        html_content += f"<td>{results[z][t]}</td>"
    html_content += f"<td><b>{zone_total}</b></td></tr>"

html_content += "<tr><td><b>Total</b></td>"
for t in inspection_types:
    html_content += f"<td><b>{total_by_type[t]}</b></td>"
html_content += f"<td><b>{grand_total}</b></td></tr>"

html_content += """
</table>
</body>
</html>
"""

with open("/home/robinz/Gensurv/NestleCat/X30_GS_Simulator/inspection_report.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("HTML generated.")
