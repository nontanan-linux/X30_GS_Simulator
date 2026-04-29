import os
from PIL import Image, ImageChops
import json

def trim_white(img):
    bg = Image.new(img.mode, img.size, img.getpixel((0,0)))
    diff = ImageChops.difference(img, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return img.crop(bbox)
    return img

def tight_crop_photo(img):
    w, h = img.size
    # 1. Remove the top part where the handwritten label usually is
    # Using 15% instead of 20% to be safer against cutting into the photo
    label_height = int(h * 0.15)
    img_no_label = img.crop((0, label_height, w, h))
    
    # 2. Trim white space from the remaining part
    # Convert to grayscale and apply a threshold to distinguish photo from white background
    gray = img_no_label.convert('L')
    # Threshold: anything brighter than 248 is considered background
    bw = gray.point(lambda x: 255 if x > 248 else 0, 'L')
    
    # Invert so content is white (255) and background is black (0)
    inv = ImageChops.invert(bw)
    bbox = inv.getbbox()
    
    if bbox:
        # Add a 2 pixel padding as requested by the user
        padding = 2
        left, top, right, bottom = bbox
        left = max(0, left - padding)
        top = max(0, top - padding)
        right = min(img_no_label.size[0], right + padding)
        bottom = min(img_no_label.size[1], bottom + padding)
        return img_no_label.crop((left, top, right, bottom))
    
    return img_no_label

def process_pdf_pages(input_dir, output_dir, reference_json):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    with open(reference_json, 'r') as f:
        data = json.load(f)
    point_names = [wp['Node_info'] for wp in data if wp.get('PointInfo') == 1]
    
    extracted_images = []
    pages = sorted([f for f in os.listdir(input_dir) if f.startswith('page-') and f.endswith('.png')])
    
    for page_file in pages:
        img = Image.open(os.path.join(input_dir, page_file))
        w, h = img.size
        
        quads = [
            (0, 0, w//2, h//2),      # TL
            (w//2, 0, w, h//2),      # TR
            (0, h//2, w//2, h),      # BL
            (w//2, h//2, w, h)       # BR
        ]
        
        for left, top, right, bottom in quads:
            crop = img.crop((left, top, right, bottom))
            gray = crop.convert('L')
            avg_brightness = sum(gray.getdata()) / (gray.size[0] * gray.size[1])
            
            if avg_brightness < 250:
                # RE-CROP TIGHTLY
                tight = tight_crop_photo(crop)
                extracted_images.append(tight)
                
    print(f"Extracted {len(extracted_images)} non-blank images (Expected {len(point_names)})")
    
    mapping = []
    for i, img_obj in enumerate(extracted_images):
        if i < len(point_names):
            name = point_names[i]
            filename = f"{name}.png"
            img_obj.save(os.path.join(output_dir, filename))
            mapping.append({'name': name, 'file': filename})
            
    return mapping

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--json", required=True)
    parser.add_argument("--mapping", required=True)
    args = parser.parse_args()

    mapping = process_pdf_pages(args.input, args.output, args.json)
    with open(args.mapping, 'w') as f:
        json.dump(mapping, f, indent=4)
