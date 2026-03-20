import os
import argparse
from PIL import Image
from pillow_heif import register_heif_opener

# Register HEIF opener with Pillow
register_heif_opener()

def convert_heic_to_png(source_dir, target_dir=None):
    if target_dir and not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"Created target directory: {target_dir}")

    files = [f for f in os.listdir(source_dir) if f.lower().endswith('.heic')]
    print(f"Found {len(files)} HEIC files in {source_dir}")

    for filename in sorted(files):
        source_path = os.path.join(source_dir, filename)
        target_filename = os.path.splitext(filename)[0] + '.png'
        target_path = os.path.join(target_dir if target_dir else source_dir, target_filename)

        print(f"Converting {filename} -> {target_filename}...")
        try:
            image = Image.open(source_path)
            image.save(target_path, format="PNG")
        except Exception as e:
            print(f"Failed to convert {filename}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert HEIC images to PNG')
    parser.add_argument('--dir', type=str, default='resource/maps/Dry_zone', help='Source directory containing HEIC files')
    parser.add_argument('--out', type=str, default=None, help='Output directory (defaults to source directory)')
    args = parser.parse_args()

    # Get absolute path relative to project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '../'))
    
    source_path = os.path.join(project_root, args.dir)
    target_path = os.path.join(project_root, args.out) if args.out else source_path

    convert_heic_to_png(source_path, target_path)
