import json

def update_return_path_wet3(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # 1. Get Yaw from via23
    via23_yaw = next((n['AngleYaw'] for n in data if n['Node_info'] == 'via23'), 0)
            
    # via_2h_00: insertion
    via_2h_00_node = {
        "Node_info": "via_2h_00",
        "MapID": 0, "Gait": 1, "NavMode": 0, "Speed": 0, "Terrain": 0,
        "PointInfo": 0, "ObsMode": 0, "Manner": 0, "Posture": 0,
        "PosX": -40.15, "PosY": 18.80, "PosZ": -0.1, "AngleYaw": via23_yaw,
        "Value": 0, "CamPTZ": [0.0, 0.0, 1.0]
    }
    
    # Find insertion point before via_2h_01
    insert_idx = -1
    for i, node in enumerate(data):
        if node['Node_info'] == 'via_2h_01':
            insert_idx = i
            break
            
    if insert_idx != -1:
        data.insert(insert_idx, via_2h_00_node)
    else:
        # If via_2h_01 not found (shouldn't happen), append
        data.append(via_2h_00_node)

    # 2. Update via_2h_02 and via_2h_03
    for node in data:
        if node['Node_info'] == 'via_2h_02':
            node['PosX'] = -20.75
            node['PosY'] = 3.15
        elif node['Node_info'] == 'via_2h_03':
            node['PosX'] = 12.75
            node['PosY'] = 4.55
        
    # 3. Re-index EVERYTHING
    for i, node in enumerate(data):
        node['Value'] = i
        
    with open(json_file, 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"Successfully updated via_2h points in {json_file}. Total nodes: {len(data)}")

if __name__ == "__main__":
    update_return_path_wet3('wet_zone_3.json')
