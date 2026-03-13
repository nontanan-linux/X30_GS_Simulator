import json
import os

files = [
    "gs_cat/src/x30_udp_bridge/path/wet123-1.json",
    "gs_cat/src/x30_udp_bridge/path/wet123-2.json",
    "gs_cat/src/x30_udp_bridge/path/wet123-3.json",
    "gs_cat/src/x30_udp_bridge/path/wet_zone.json"
]

base_path = "/home/nontanan/Gensurv/NestleCat"

data = {}
for f in files:
    full_path = os.path.join(base_path, f)
    with open(full_path, 'r') as jf:
        data[f] = json.load(jf)
        print(f"{f}: {len(data[f])} points")

wet123_1 = data[files[0]]
wet123_2 = data[files[1]]
wet123_3 = data[files[2]]
wet_zone = data[files[3]]

combined = wet123_1 + wet123_2 + wet123_3

print(f"Combined (1+2+3): {len(combined)} points")

if wet_zone == combined:
    print("wet_zone.json IS the combination of wet123-1, wet123-2, and wet123-3")
else:
    print("wet_zone.json IS NOT the combination of wet123-1, wet123-2, and wet123-3")

if wet_zone == wet123_1:
    print("wet_zone.json is IDENTICAL to wet123-1.json")
