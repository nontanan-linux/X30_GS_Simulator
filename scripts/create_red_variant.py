from PIL import Image, ImageFilter
import numpy as np
import os

def create_red_rotated_variant(input_path, output_path, target_size, rotation_angle):
    print(f"Loading image from {input_path}...")
    img = Image.open(input_path).convert('L')
    
    # Phase 1: High-Contrast and Line Thickening
    print("Performing high-contrast conversion and line thickening...")
    threshold = 50
    data = np.array(img)
    binary_data = np.where(data < threshold, 0, 255).astype(np.uint8)
    
    img_binary = Image.fromarray(binary_data)
    img_thickened = img_binary.filter(ImageFilter.MinFilter(size=3))
    
    # Phase 2: Rotation
    print(f"Rotating image by {rotation_angle} degrees...")
    # expand=False to keep original image boundaries/dimensions for centering
    # fillcolor=255 to keep background white
    img_rotated = img_thickened.rotate(rotation_angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=255)
    
    # Phase 3: Resizing
    print(f"Resizing to {target_size}...")
    img_resized = img_rotated.resize(target_size, Image.Resampling.LANCZOS)
    
    # Phase 4: Final Binarization
    print("Applying final binarization...")
    data_resized = np.array(img_resized)
    # Binary mask for lines
    is_line = data_resized < 200
    
    # Phase 5: Colorizing
    print("Colorizing lines to a brighter red for GIMP compatibility...")
    # Create an RGB image starting with white background
    final_data = np.ones((target_size[1], target_size[0], 3), dtype=np.uint8) * 255
    # Set line pixels to a clearer red [210, 0, 0] instead of very dark [139, 0, 0]
    final_data[is_line] = [210, 0, 0]
    
    # Save result explicitly as RGB
    final_img = Image.fromarray(final_data, 'RGB')
    final_img.save(output_path)
    print(f"Saved red rotated variant to {output_path}")

if __name__ == "__main__":
    input_file = "/home/nontanan/Gensurv/NestleCat/picture/edit/Nestle-full-edit02.png"
    output_file = "/home/nontanan/Gensurv/NestleCat/picture/edit/Nestle-full-edit02_972_red.png"
    target_size = (972, 445)
    rotation_angle = 1.75
    
    if os.path.exists(input_file):
        create_red_rotated_variant(input_file, output_file, target_size, rotation_angle)
    else:
        print(f"Error: {input_file} not found.")
