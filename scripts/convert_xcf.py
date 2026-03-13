import subprocess
import os
from PIL import Image

def convert_xcf_to_png(xcf_path, png_path):
    print(f"Converting {xcf_path} to PNG using GIMP...")
    
    # GIMP batch command to load XCF, merge layers, and save as PNG
    gimp_command = [
        "gimp",
        "-i",  # Run without user interface
        "-b",
        f'(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{xcf_path}" "{xcf_path}"))) (drawable (car (gimp-image-merge-visible-layers image CLIP-TO-IMAGE)))) (gimp-file-save RUN-NONINTERACTIVE image drawable "{png_path}" "{png_path}") (gimp-image-delete image))',
        "-b",
        "(gimp-quit 0)"
    ]
    
    try:
        result = subprocess.run(gimp_command, check=True, capture_output=True, text=True)
        print("GIMP conversion successful.")
    except subprocess.CalledProcessError as e:
        print(f"GIMP conversion failed: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        return False
    return True

def rotate_image(image_path):
    print(f"Rotating {image_path} 90 degrees left...")
    try:
        img = Image.open(image_path)
        # Rotate 90 degrees left (counter-clockwise)
        rotated_img = img.rotate(90, expand=True)
        rotated_img.save(image_path)
        print("Rotation successful.")
    except Exception as e:
        print(f"Error rotating image: {e}")
        return False
    return True

if __name__ == "__main__":
    xcf_file = "/home/nontanan/Gensurv/NestleCat/picture/edit/Nestle-full-edit02.xcf"
    png_file = "/home/nontanan/Gensurv/NestleCat/picture/edit/Nestle-full-edit02.png"
    
    if os.path.exists(xcf_file):
        if convert_xcf_to_png(xcf_file, png_file):
            rotate_image(png_file)
    else:
        print(f"Error: {xcf_file} not found.")
