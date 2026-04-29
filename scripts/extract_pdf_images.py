import os
import json
import subprocess

# --- CONFIGURATION ---
PDF_PATH = '/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/docs/New-dry-full.pdf'
JSON_PATH = '/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/path/new-dry-full.json'
OUTPUT_DIR = '/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/docs/extracted_images'
# ---------------------

def extract_and_rename():
    # 1. Create directory
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created directory: {OUTPUT_DIR}")
    else:
        # Clean current contents
        for f in os.listdir(OUTPUT_DIR):
            os.remove(os.path.join(OUTPUT_DIR, f))

    # 2. Extract images using pdfimages (Raw extraction)
    print(f"Extracting raw images from {PDF_PATH}...")
    subprocess.run(['pdfimages', '-j', PDF_PATH, os.path.join(OUTPUT_DIR, 'img')])

    # 3. Handle conversion and cleanup
    # Sometimes pdfimages outputs .ppm or .pbm
    for f in os.listdir(OUTPUT_DIR):
        if f.endswith('.ppm') or f.endswith('.pbm'):
            old_path = os.path.join(OUTPUT_DIR, f)
            new_path_base = os.path.join(OUTPUT_DIR, os.path.splitext(f)[0])
            subprocess.run(['mogrify', '-format', 'jpg', old_path])
            os.remove(old_path)

    # 4. Rename based on JSON
    print(f"Renaming images based on {JSON_PATH}...")
    with open(JSON_PATH, 'r') as f:
        data = json.load(f)
    
    points = [p.get('Node_info') for p in data if p.get('PointInfo') == 1]
    
    # pdfimages usually names them img-000.jpg, img-001.jpg ...
    # Let's collect all generated jpegs
    all_jpegs = sorted([f for f in os.listdir(OUTPUT_DIR) if f.endswith('.jpg')])

    for i, name in enumerate(points):
        if i < len(all_jpegs):
            old_name = all_jpegs[i]
            old_path = os.path.join(OUTPUT_DIR, old_name)
            new_name = f'{i+1:03d}_{name}.jpg'
            new_path = os.path.join(OUTPUT_DIR, new_name)
            
            os.rename(old_path, new_path)
            print(f"Renamed: {old_name} -> {new_name}")
        else:
            print(f"Warning: No raw image found for point index {i} ({name})")

if __name__ == "__main__":
    extract_and_rename()
    print("Done! (Reverted to raw extraction to get all 70 images)")
