import os
from PIL import Image, ImageChops

def refine_crop(image_path, mode):
    """
    mode: 'top', 'bottom', 'both'
    """
    if not os.path.exists(image_path):
        # Try finding with suffix like -low
        base, ext = os.path.splitext(image_path)
        if os.path.exists(base + "-low" + ext):
            image_path = base + "-low" + ext
        elif os.path.exists(base + "-1" + ext): # handle possible duplicates
             image_path = base + "-1" + ext
        else:
            print(f"File not found: {image_path}")
            return

    img = Image.open(image_path)
    w, h = img.size
    
    # 1. Hard crop to get rid of remnants of labels
    cut_top = 75 if 'top' in mode or 'both' in mode else 0
    cut_bottom = 45 if 'bottom' in mode or 'both' in mode else 0
    
    img = img.crop((0, cut_top, w, h - cut_bottom))
    
    # 2. Automated white space trimming for remaining area
    gray = img.convert('L')
    bw = gray.point(lambda x: 255 if x > 240 else 0, 'L')
    inv = ImageChops.invert(bw)
    bbox = inv.getbbox()
    
    if bbox:
        # Add tiny 2px padding for "Best Cut" standard
        padding = 2
        left, top, right, bottom = bbox
        left = max(0, left - padding)
        top = max(0, top - padding)
        right = min(img.size[0], right + padding)
        bottom = min(img.size[1], bottom + padding)
        
        final_img = img.crop((left, top, right, bottom))
        final_img.save(image_path)
        print(f"Refined {os.path.basename(image_path)} (Mode: {mode})")

if __name__ == "__main__":
    # Normalized lists from user request
    top_more = [
        "asset-12", "gauge-19", "gauge20", "gauge21", "gauge22", "gauge23", 
        "loto-22", "loto-23", "loto-26", "loto21", "thermal-77", "thermal-78", 
        "thermal-79", "thermal-80", "thermal-83", "vibration-71", "vibration-75", 
        "dry-leaked-15", "dry-leaked-16", "dry-leaked-25", "dry-vibration-35", 
        "dry3-gauge-01", "dry3-gauge-07", "dry3-leaked-35", "dry3-leaked-36", 
        "dry3-leaked-38", "dry3-loto-07", "dry3-loto-10", "dry3-loto-13", "dry3-thermal-44"
    ]
    both_more = [
        "leaked-68", "loto20", "thermal-81", "thermal-85", "thermal-87", 
        "vibration-69", "vibration-73", "dry-leaked-18", "dry-leaked-20-low", 
        "dry-leaked-21", "dry-vibration-33-low", "dry3-leaked-29", "dry3-leaked-30"
    ]
    bottom_more = [
        "loto19", "dry-leaked-24-low", "dry-thermal-37", "dry-vibration-34-low"
    ]

    filling_dir = "resource/docs/processed_filling"
    dry_dir = "resource/docs/processed_inspections"

    # Process all lists in both directories (one will match)
    for name in top_more:
        refine_crop(os.path.join(filling_dir, name + ".png"), 'top')
        refine_crop(os.path.join(dry_dir, name + ".png"), 'top')
    
    for name in both_more:
        refine_crop(os.path.join(filling_dir, name + ".png"), 'both')
        refine_crop(os.path.join(dry_dir, name + ".png"), 'both')
        
    for name in bottom_more:
        refine_crop(os.path.join(filling_dir, name + ".png"), 'bottom')
        refine_crop(os.path.join(dry_dir, name + ".png"), 'bottom')

    filling_dir = "resource/docs/processed_filling"
    dry_dir = "resource/docs/processed_inspections"

    for f in top_more_filling: refine_crop(os.path.join(filling_dir, f), 'top')
    for f in both_more_filling: refine_crop(os.path.join(filling_dir, f), 'both')
    for f in bottom_more_filling: refine_crop(os.path.join(filling_dir, f), 'bottom')

    for f in top_more_dry: refine_crop(os.path.join(dry_dir, f), 'top')
    for f in both_more_dry: refine_crop(os.path.join(dry_dir, f), 'both')
    for f in bottom_more_dry: refine_crop(os.path.join(dry_dir, f), 'bottom')
