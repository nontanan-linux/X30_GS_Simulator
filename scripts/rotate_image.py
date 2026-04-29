from PIL import Image
import os
import argparse

def rotate_image(input_path, output_path, degrees):
    """
    Rotates an image by the specified degrees and saves it.
    """
    if not os.path.exists(input_path):
        print(f"Error: Input image not found at '{input_path}'")
        return

    try:
        img = Image.open(input_path)
        rotated_img = img.rotate(degrees, expand=True) # expand=True to ensure the entire image is visible
        rotated_img.save(output_path)
        print(f"Successfully rotated '{input_path}' by {degrees} degrees and saved to '{output_path}'")
    except Exception as e:
        print(f"Error rotating image: {e}")

def main():
    parser = argparse.ArgumentParser(description="Rotate an image by a specified degree.")
    parser.add_argument("--input", "-i", required=True, help="Path to the input image file.")
    parser.add_argument("--output", "-o", default="rotated_image.png", help="Path to save the rotated image. (Default: rotated_image.png)")
    parser.add_argument("--degrees", "-d", type=int, default=90, help="Degrees to rotate clockwise. (Default: 90)")
    args = parser.parse_args()
    rotate_image(args.input, args.output, args.degrees)

if __name__ == "__main__":
    main()