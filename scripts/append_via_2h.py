import json

def append_via_2h_points(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Template from the last node
    template = data[-1].copy()
    
    new_points = [
        {"Node_info": "via_2h_01", "u": 2033, "v": 1377, "yaw": -1.4682677},
        {"Node_info": "via_2h_02", "u": 2038, "v": 1549, "yaw": -0.6247373},
        {"Node_info": "via_2h_03", "u": 2164, "v": 1557, "yaw": -1.4682677},
        {"Node_info": "via_2h_04", "u": 2171, "v": 1896, "yaw": -1.4682677},
    ]
    
    # Map parameters
    res = 0.05
    ox = -67.25
    oy = -243.55
    height = 6475
    
    def p2w(u, v):
        return u * res + ox, (height - v) * res + oy

    for p in new_points:
        node = template.copy()
        node["Node_info"] = p["Node_info"]
        wx, wy = p2w(p["u"], p["v"])
        node["PosX"] = round(wx, 4)
        node["PosY"] = round(wy, 4)
        node["AngleYaw"] = round(p["yaw"], 7)
        node["PointInfo"] = 0 # It's a via point
        data.append(node)
        print(f"Appended {p['Node_info']} at ({wx}, {wy})")

    # Re-index
    for i, node in enumerate(data):
        node["Value"] = i
        
    with open(json_file, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Successfully updated {json_file} and re-indexed {len(data)} nodes.")

if __name__ == "__main__":
    append_via_2h_points('wet_zone_12.json')
