import json

def add_more_via_points(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # 1. Get Yaw from Via3
    via3_yaw = 0
    for node in data:
        if node['Node_info'] == 'Via3':
            via3_yaw = node['AngleYaw']
            break
            
    # 2. Coordinates
    # pixel 1286, 1007 -> PosX=-2.95, PosY=29.85
    # pixel 1183, 994 -> PosX=-8.10, PosY=30.50
    
    via16_node = {
        "Node_info": "via16",
        "MapID": 0,
        "Gait": 0,
        "NavMode": 0,
        "Speed": 0,
        "Terrain": 0,
        "PointInfo": 0,
        "ObsMode": 0,
        "Manner": 0,
        "Posture": 0,
        "PosX": -2.95,
        "PosY": 29.85,
        "PosZ": -0.1,
        "AngleYaw": via3_yaw,
        "Value": 0,
        "CamPTZ": [0.0, 0.0, 1.0]
    }
    
    via17_node = {
        "Node_info": "via17",
        "MapID": 0,
        "Gait": 0,
        "NavMode": 0,
        "Speed": 0,
        "Terrain": 0,
        "PointInfo": 0,
        "ObsMode": 0,
        "Manner": 0,
        "Posture": 0,
        "PosX": -8.10,
        "PosY": 30.50,
        "PosZ": -0.1,
        "AngleYaw": via3_yaw,
        "Value": 0,
        "CamPTZ": [0.0, 0.0, 1.0]
    }
    
    # 3. Find insertion point before via12
    insert_idx = -1
    for i, node in enumerate(data):
        if node['Node_info'] == 'via12':
            insert_idx = i
            break
            
    if insert_idx != -1:
        data.insert(insert_idx, via16_node)
        data.insert(insert_idx + 1, via17_node)
    else:
        print("via12 not found. Appending to end.")
        data.append(via16_node)
        data.append(via17_node)
        
    # 4. Re-index
    for i, node in enumerate(data):
        node['Value'] = i
        
    with open(json_file, 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"Successfully added via16 and via17 before via12 in {json_file}. Total nodes: {len(data)}")

if __name__ == "__main__":
    add_more_via_points('wet_zone_3.json')
