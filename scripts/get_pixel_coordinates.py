import cv2
import argparse
import json
import os
import csv

# Global list to store coordinates and the image for display
points = []
image_display = None

def mouse_callback(event, x, y, flags, param):
    """
    Mouse callback function to capture clicks, draw on the image, and store points.
    """
    global image_display
    if event == cv2.EVENT_LBUTTONDOWN:
        # Store the coordinate
        points.append({'x': x, 'y': y})
        
        # Print to console for immediate feedback
        print(f"Point added: ({x}, {y}). Total points: {len(points)}")
        
        # Draw a circle and number on the display image for visual feedback
        cv2.circle(image_display, (x, y), 5, (0, 255, 0), -1) # Green circle
        cv2.putText(image_display, str(len(points)), (x + 10, y + 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

def main():
    """
    Main function to load image, set up window, and handle user input.
    """
    global points, image_display

    parser = argparse.ArgumentParser(description="Record pixel coordinates from an image by clicking on it.")
    parser.add_argument("--image", "-i", required=True, help="Path to the input image file.")
    parser.add_argument("--output", "-o", default="coordinates.json", help="Path to the output file. Supports .json and .csv extensions. (Default: coordinates.json)")
    args = parser.parse_args()

    # Load the image
    image_path = args.image
    if not os.path.exists(image_path):
        print(f"Error: Image not found at '{image_path}'")
        return

    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image from '{image_path}'")
        return
        
    # Make a copy for drawing on, so the original is preserved
    image_display = image.copy()

    # Create a window
    window_name = "Coordinate Recorder | [s] save | [c] clear last | [q] quit"
    cv2.namedWindow(window_name)
    
    # Set the mouse callback function
    cv2.setMouseCallback(window_name, mouse_callback)

    print("\n--- Pixel Coordinate Recorder ---")
    print("Click on the image to record coordinates.")
    print("Press 's' to save the recorded points.")
    print("Press 'c' to clear the last added point.")
    print("Press 'q' or ESC to quit.")
    print("---------------------------------\n")

    while True:
        # Display the image
        cv2.imshow(window_name, image_display)
        key = cv2.waitKey(1) & 0xFF

        # Quit
        if key == ord('q') or key == 27: # 'q' or ESC
            break
            
        # Save
        if key == ord('s'):
            if not points:
                print("No points to save.")
                continue

            try:
                if args.output.lower().endswith('.csv'):
                    with open(args.output, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=['x', 'y'])
                        writer.writeheader()
                        writer.writerows(points)
                    print(f"Successfully saved {len(points)} points to {args.output} (CSV format)")
                else: # Default to JSON
                    with open(args.output, 'w') as f:
                        json.dump(points, f, indent=4)
                    print(f"Successfully saved {len(points)} points to {args.output} (JSON format)")
            except Exception as e:
                print(f"Error saving file: {e}")

        # Clear last point
        if key == ord('c'):
            if points:
                points.pop()
                print(f"Last point removed. Total points: {len(points)}")
                # Redraw the image from original to clear all drawings
                image_display = image.copy()
                # Re-draw existing points
                for i, p in enumerate(points):
                    cv2.circle(image_display, (p['x'], p['y']), 5, (0, 255, 0), -1)
                    cv2.putText(image_display, str(i+1), (p['x'] + 10, p['y'] + 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
            else:
                print("No points to clear.")

    cv2.destroyAllWindows()
    print("Application closed.")

if __name__ == "__main__":
    main()