import os
import json
import re

def check_sequence():
    json_path = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/dry_zone.json"
    img_dir = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/maps/Dry_zone/"
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    waypoints = []
    for wp in data:
        name = wp.get('Node_info', '')
        if name.startswith('dry'):
            waypoints.append(name)
            
    images = os.listdir(img_dir)
    
    print(f"Total Waypoints to check: {len(waypoints)}")
    print("-" * 60)
    
    last_img_num = -1
    last_wp = None
    last_img = None
    
    results = []
    
    for wp in waypoints:
        core_match = re.search(r'-(.*)$', wp)
        if not core_match:
            results.append((wp, "ERROR: Invalid waypoint name format", None))
            continue
            
        core = core_match.group(1).lower()
        found_img = None
        
        # Matching logic same as check_image_matches.py
        for img in images:
            clean_img = img.replace('--', '-').lower()
            if core in clean_img or core.replace('-', '') in clean_img.replace('-', ''):
                found_img = img
                break
        
        if found_img:
            # Extract IMG number
            num_match = re.search(r'IMG_(\d+)', found_img)
            img_num = int(num_match.group(1)) if num_match else -1
            
            error_msg = ""
            if img_num != -1:
                if img_num < last_img_num:
                    error_msg = f"!!! SEQUENCE ERROR: IMG_{img_num} is smaller than previous IMG_{last_img_num}"
                last_img_num = img_num
            
            results.append((wp, found_img, error_msg))
            last_wp = wp
            last_img = found_img
        else:
            results.append((wp, "MISSING IMAGE", None))

    # Print results
    print(f"{'Waypoint':<30} | {'Image File':<40} | {'Status'}")
    print("-" * 100)
    for wp, img, status in results:
        status_str = status if status else "OK"
        print(f"{wp:<30} | {img:<40} | {status_str}")

if __name__ == "__main__":
    check_sequence()
