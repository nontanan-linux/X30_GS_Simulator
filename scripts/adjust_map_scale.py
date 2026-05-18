import cv2
import numpy as np
import os
import json
import math
from PIL import Image

class CoordinateSystem:
    """Handles all coordinate transformations between world, pixel, and rotated frames."""
    
    @staticmethod
    def world_to_pixel(x, y, origin, resolution, height):
        """Converts world (x, y) to original image pixel (u, v)."""
        u = (x - origin[0]) / resolution
        v_bottom = (y - origin[1]) / resolution
        v_top = height - 1 - v_bottom
        return u, v_top

    @staticmethod
    def transform_pixel_to_rotated(u, v, old_size, new_size, angle_deg):
        """Transforms pixel (u, v) from original image to rotated image space."""
        angle_rad = math.radians(angle_deg)
        
        # Centers for rotation
        cx_old, cy_old = (old_size[0] - 1) / 2.0, (old_size[1] - 1) / 2.0
        cx_new, cy_new = (new_size[0] - 1) / 2.0, (new_size[1] - 1) / 2.0
        
        # Relative to old center
        du, dv = u - cx_old, v - cy_old
        
        # Rotation in v-down system (CCW)
        du_rot = du * math.cos(angle_rad) + dv * math.sin(angle_rad)
        dv_rot = -du * math.sin(angle_rad) + dv * math.cos(angle_rad)
        
        return du_rot + cx_new, dv_rot + cy_new

class MapEditor:
    """Handles image-level operations like rotation and scaling."""
    
    @staticmethod
    def rotate(input_path, degrees, fill_color=255):
        """Rotates map and returns the new path and image size."""
        if not os.path.exists(input_path): return None, None, None
        
        name, ext = os.path.splitext(input_path)
        output_path = f"{name}_rotated{ext}"
        
        print(f"Rotating map by {degrees} degrees...")
        with Image.open(input_path) as img:
            rotated_img = img.rotate(degrees, expand=True, fillcolor=fill_color)
            rotated_img.save(output_path)
            return output_path, img.size, rotated_img.size

class MapVisualizer:
    """Handles drawing waypoints, paths, and markers on maps."""
    
    def __init__(self, floor_colors=None):
        self.floor_colors = floor_colors or [
            [(250, 206, 135), (0, 165, 255)],  # Flr 0: Via, Inspect
            [(150, 255, 150), (0, 200, 0)],    # Flr 1: Via, Inspect
            [(200, 200, 255), (0, 0, 255)],    # Flr 2: Via, Inspect
            [(255, 200, 255), (200, 0, 200)],  # Flr 3: Via, Inspect
        ]

    def get_node_style(self, node):
        """Determines color and type for a node."""
        name = node.get('Node_info', '').lower()
        p_info = node.get('PointInfo', 0)
        node_mid = node.get('MapID', 0)
        
        keywords = ['acoustic', 'visual', 'thermal', 'loto', 'leaked', 'vibration', 'asset', 'charge']
        is_inspection = (any(kw in name for kw in keywords) and 'via' not in name) or p_info == 1
        
        palette = self.floor_colors[node_mid % len(self.floor_colors)]
        return palette[1] if is_inspection else palette[0]

    def draw_marker(self, img, u, v, yaw, color, scale=1.0, is_robot=False):
        """Draws the waypoint circle and orientation arrow."""
        if is_robot:
            # Special style for the robot (larger and brighter)
            cv2.circle(img, (int(u), int(v)), int(12 * scale), (255, 255, 255), -1) # White glow
            cv2.circle(img, (int(u), int(v)), int(8 * scale), (0, 0, 255), -1)     # Red center
        
        arrow_len = 20 * scale
        end_u = int(u + arrow_len * math.cos(yaw))
        end_v = int(v - arrow_len * math.sin(yaw))
        
        thickness = 3 if is_robot else 2
        cv2.arrowedLine(img, (int(u), int(v)), (end_u, end_v), color, int(thickness * scale), tipLength=0.4)

    def draw_path(self, img, waypoints, coord_fn, color=(200, 200, 200)):
        """Draws lines between sequential waypoints."""
        for i in range(len(waypoints) - 1):
            p1, p2 = waypoints[i], waypoints[i+1]
            u1, v1 = coord_fn(p1['PosX'], p1['PosY'])
            u2, v2 = coord_fn(p2['PosX'], p2['PosY'])
            cv2.line(img, (int(u1), int(v1)), (int(u2), int(v2)), color, 2)

    def render_on_occupancy(self, map_path, waypoints, yaml_data, angle_deg, old_size):
        """Renders simulate_path style visualization on PGM/PNG occupancy maps."""
        img = cv2.imread(map_path)
        if img is None: return
        
        new_size = (img.shape[1], img.shape[0])
        origin, res = yaml_data['origin'], yaml_data['resolution']
        angle_rad = math.radians(angle_deg)

        def to_rot_pixel(x, y):
            u, v = CoordinateSystem.world_to_pixel(x, y, origin, res, old_size[1])
            return CoordinateSystem.transform_pixel_to_rotated(u, v, old_size, new_size, angle_deg)

        self.draw_path(img, waypoints, to_rot_pixel)

        for node in waypoints:
            u, v = to_rot_pixel(node['PosX'], node['PosY'])
            color = self.get_node_style(node)
            yaw = node.get('AngleYaw', 0) + angle_rad
            self.draw_marker(img, u, v, yaw, color)

        # Mark Origin
        u0, v0 = to_rot_pixel(0, 0)
        cv2.circle(img, (int(u0), int(v0)), 10, (0, 255, 0), -1)
        
        name, _ = os.path.splitext(map_path)
        output_path = f"{name}_style.webp"
        cv2.imwrite(output_path, img, [cv2.IMWRITE_WEBP_QUALITY, 90])
        print(f"Occupancy visualization saved to: {output_path}")

    def render_on_layout(self, layout_path, waypoints, origin_pixel, resolution, angle_deg, robot_pos=None):
        """Renders visualization on high-res layout (supports robot_pos=[x, y, yaw])."""
        img = cv2.imread(layout_path)
        if img is None: return
        
        u0, v0 = origin_pixel
        angle_rad = math.radians(angle_deg)

        def to_layout_pixel(x, y):
            xr = x * math.cos(angle_rad) - y * math.sin(angle_rad)
            yr = x * math.sin(angle_rad) + y * math.cos(angle_rad)
            return u0 + xr / resolution, v0 - yr / resolution

        self.draw_path(img, waypoints, to_layout_pixel)

        # Draw Waypoints
        for node in waypoints:
            u, v = to_layout_pixel(node['PosX'], node['PosY'])
            color = self.get_node_style(node)
            yaw = node.get('AngleYaw', 0) + angle_rad
            self.draw_marker(img, u, v, yaw, color)

        # Draw Current Robot Position if provided
        if robot_pos:
            rx, ry, ryaw = robot_pos
            ru, rv = to_layout_pixel(rx, ry)
            self.draw_marker(img, ru, rv, ryaw + angle_rad, (0, 0, 255), scale=1.5, is_robot=True)
            print(f"Robot marked at world ({rx}, {ry}) -> pixel ({int(ru)}, {int(rv)})")

        cv2.circle(img, (int(u0), int(v0)), 15, (0, 255, 0), -1)
        
        name, _ = os.path.splitext(layout_path)
        # output_path = f"{name}_style.webp"
        output_path = f"{name}_style.png"
        # Save as WebP with high quality
        cv2.imwrite(output_path, img, [cv2.IMWRITE_WEBP_QUALITY, 90])
        print(f"Layout visualization saved to: {output_path}")

def load_json(path):
    if not os.path.exists(path): return []
    with open(path, 'r') as f: return json.load(f)

def main():
    # Paths
    base_dir = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/maps/map1-nestle/"
    input_map = os.path.join(base_dir, "jueying.pgm")
    layout_map = os.path.join(base_dir, "Neatle-map-Layout.webp")
    combine_map = os.path.join(base_dir, "Nestle_map_combine.jpg")
    json_path = "/home/nontanan/Gensurv/NestleCat/X30_GS_Simulator/resource/path/new-dry-full.json"
    
    # Parameters
    yaml_data = {'resolution': 0.05, 'origin': [-67.25, -243.55, 0.0]}
    layout_params = {'origin_pixel': (1960, 1530), 'resolution': 0.05}
    rotation_angle = 88
    
    # Example Robot Position [X, Y, Yaw]
    current_robot_pos = [10.0, -5.0, 0.0]

    # 1. Rotate Map
    editor = MapEditor()
    rotated_path, old_size, new_size = editor.rotate(input_map, rotation_angle)
    
    if rotated_path:
        # 2. Load Data
        waypoints = load_json(json_path)
        
        # 3. Visualize
        viz = MapVisualizer()
        viz.render_on_occupancy(rotated_path, waypoints, yaml_data, rotation_angle, old_size)
        
        # Visualize on Layout Maps (Layout with Robot Pos, Combine standard)
        if os.path.exists(layout_map):
            viz.render_on_layout(layout_map, waypoints, 
                                layout_params['origin_pixel'], 
                                layout_params['resolution'], 
                                rotation_angle,)
                                # robot_pos=current_robot_pos)
        
        if os.path.exists(combine_map):
            viz.render_on_layout(combine_map, waypoints, 
                                layout_params['origin_pixel'], 
                                layout_params['resolution'], 
                                rotation_angle)

if __name__ == "__main__":
    main()
