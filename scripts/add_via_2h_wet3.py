import json

def add_via_2h_points_wet3(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # 1. Get Yaw from via25
    via25_yaw = next((n['AngleYaw'] for n in data if n['Node_info'] == 'via25'), 0)
            
    # New nodes
    # via_2h_01: PosX=-14.00, PosY=0.55
    # via_2h_02: PosX=-8.90, PosY=4.00
    # via_2h_03: PosX=10.65, PosY=4.70
    
    new_nodes = [
        {
            "Node_info": "via_2h_01",
            "MapID": 0, "Gait": 0, "NavMode": 0, "Speed": 0, "Terrain": 0,
            "PointInfo": 0, "ObsMode": 0, "Manner": 0, "Posture": 0,
            "PosX": -14.00, "PosY": 0.55, "PosZ": -0.1, "AngleYaw": via25_yaw,
            "Value": 0, "CamPTZ": [0.0, 0.0, 1.0]
        },
        {
            "Node_info": "via_2h_02",
            "MapID": 0, "Gait": 1, "NavMode": 0, "Speed": 0, "Terrain": 0,
            "PointInfo": 0, "ObsMode": 0, "Manner": 0, "Posture": 0,
            "PosX": -8.90, "PosY": 4.00, "PosZ": -0.1, "AngleYaw": via25_yaw,
            "Value": 0, "CamPTZ": [0.0, 0.0, 1.0]
        },
        {
            "Node_info": "via_2h_03",
            "MapID": 0, "Gait": 1, "NavMode": 0, "Speed": 0, "Terrain": 0,
            "PointInfo": 0, "ObsMode": 0, "Manner": 0, "Posture": 0,
            "PosX": 10.65, "PosY": 4.70, "PosZ": -0.1, "AngleYaw": via25_yaw,
            "Value": 0, "CamPTZ": [0.0, 0.0, 1.0]
        }
    ]
    
    # Appending at the end
    data.extend(new_nodes)
        
    # 4. Re-index EVERYTHING
    for i, node in enumerate(data):
        node['Value'] = i
        
    with open(json_file, 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"Successfully added via_2h_01-03 to {json_file}. Total nodes: {len(data)}")

if __name__ == "__main__":
    add_via_2h_points_wet3('wet_zone_3.json')
