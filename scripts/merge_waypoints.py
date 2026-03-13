import json
import os

base_path = "/home/nontanan/Gensurv/NestleCat"
input_files = [
    "gs_cat/src/x30_udp_bridge/path/wet123-1.json",
    "gs_cat/src/x30_udp_bridge/path/wet123-2.json",
    "gs_cat/src/x30_udp_bridge/path/wet123-3.json"
]
output_file = "gs_cat/src/x30_udp_bridge/path/wet_zone.json"

combined_waypoints = []

for file_rel_path in input_files:
    file_path = os.path.join(base_path, file_rel_path)
    with open(file_path, 'r') as f:
        data = json.load(f)
        combined_waypoints.extend(data)

# Re-index Value field
for i, waypoint in enumerate(combined_waypoints):
    waypoint["Value"] = i + 1

# Save to wet_zone.json
output_path = os.path.join(base_path, output_file)
with open(output_path, 'w') as f:
    json.dump(combined_waypoints, f, indent=4)

print(f"Successfully merged {len(input_files)} files into {output_file}")
print(f"Total points: {len(combined_waypoints)}")
