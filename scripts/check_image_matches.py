import os
import json
import re

def check_image_matches():
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
    
    print(f"Total Waypoints to match: {len(waypoints)}")
    print(f"Total Images available: {len(images)}")
    print("-" * 50)
    
    unmatched_waypoints = []
    matches = {}
    
    for wp in waypoints:
        # Extract the core part (category-index-suffix)
        # e.g., dry-leaked-14 -> leaked-14
        # e.g., dry3-leaked-27 -> leaked-27
        # e.g., dry-vibration-33 -> vibration-33
        
        core_match = re.search(r'-(.*)$', wp)
        if not core_match:
            unmatched_waypoints.append(wp)
            continue
            
        core = core_match.group(1)
        
        # Look for this core in images
        found = False
        for img in images:
            # Normalize image name: remove IMG_XXXX, remove extension, remove double dashes
            clean_img = img.replace('--', '-').lower()
            
            # Simple check: if core is in clean_img
            if core.lower() in clean_img:
                matches[wp] = img
                found = True
                break
            
            # Additional check for cases like leaked15 (no hyphen)
            core_no_hyphen = core.replace('-', '').lower()
            if core_no_hyphen in clean_img.replace('-', ''):
                matches[wp] = img
                found = True
                break
                
        if not found:
            unmatched_waypoints.append(wp)
            
    if unmatched_waypoints:
        print(f"MISSING IMAGES for {len(unmatched_waypoints)} waypoints:")
        for wp in unmatched_waypoints:
            print(f"  [MISSING] {wp}")
    else:
        print("SUCCESS: All waypoints matched with an image!")
        
    # Also check if any images are not used
    used_images = set(matches.values())
    unused_images = [img for img in images if img not in used_images and img.endswith('.png')]
    
    print("-" * 50)
    if unused_images:
        print(f"UNUSED IMAGES in directory ({len(unused_images)} total):")
        for img in unused_images:
            # Ignore base IMG files without categories if they are just placeholders
            if any(cat in img for cat in ["leaked", "thermal", "vibration", "loto", "gauge"]):
                print(f"  [UNUSED] {img}")
            else:
                print(f"  [DOUBTFUL] {img} (No category in name)")

if __name__ == "__main__":
    check_image_matches()
