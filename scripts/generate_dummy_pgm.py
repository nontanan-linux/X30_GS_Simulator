import os

def generate_pgm(filepath, width, height, max_val, pixel_value):
    """
    Generates a dummy PGM file (P2 ASCII format) with uniform pixel values.
    """
    print(f"Generating dummy PGM: {filepath} ({width}x{height}, value={pixel_value})...")
    try:
        with open(filepath, 'w') as f:
            f.write("P2\n")
            f.write(f"{width} {height}\n")
            f.write(f"{max_val}\n")
            
            pixels_per_line = 20 # For readability in the file
            pixel_data = [str(pixel_value)] * (width * height)
            
            for i in range(0, len(pixel_data), pixels_per_line):
                f.write(" ".join(pixel_data[i : i + pixels_per_line]) + "\n")
        print(f"Successfully generated {filepath}")
    except IOError as e:
        print(f"Error generating {filepath}: {e}")

if __name__ == "__main__":
    base_dir = "/home/nontanan/Gensurv/NestleCat"
    
    generate_pgm(os.path.join(base_dir, "DSS-multifloor-20260108-125209.pgm"), 500, 500, 255, 220)
    generate_pgm(os.path.join(base_dir, "jueying.pgm"), 500, 500, 255, 220)
    generate_pgm(os.path.join(base_dir, "jueying2.pgm"), 500, 500, 255, 220)

    print("\nAll dummy PGM files generated.")