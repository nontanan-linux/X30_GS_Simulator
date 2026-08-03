#!/usr/bin/env python3
"""
X30 GS Path Simulator (simulate_path.py) - NiceGUI Web Application

Exact visual and functional parity with simulate_path_back.py:
1. Gaps Fix: Zero padding/margin on body and .nicegui-content so Layer 1 top bar touches screen edges.
2. Local File Import/Export: Interactive web file uploader (ui.upload) for local map/JSON files + browser downloader (ui.download).
3. Map Resolution & Scaling: Canvas screen resolution warpAffine (cw, ch) so map fills viewport nicely with smooth mouse drag panning and wheel zooming.
4. Right Navbar (Sidebar Drawer): Direct copy of simulate_path_back.py properties:
   - Width 450px, #b71836 Red background, #000000 Black text.
   - Title: "Waypoint Information" (20px bold black text).
   - Search row: Entry (250px, 3px #00264d border, #b71836 bg) + Search button (80px, #00264d bg).
   - 2px Black separator line.
   - Mode 1 (Info View): Textbox (#b71836 bg, #000000 text, 2px #00264d border), neighbors, and white photo frame (#FFFFFF bg, 2px #00264d border).
   - Mode 2 (Editor View): Form fields (PosX, PosY, PosZ, AngleYaw, Node Info, Map ID, Map Name, Zone), dropdowns, and #00264d Save Point button (height 50px).
"""

import os
import sys
import json
import yaml
import cv2
import numpy as np
import math
import time
import copy
import base64
import asyncio
import argparse
import re
import platform
from pathlib import Path
from PIL import Image

import importlib
import node_manager
importlib.reload(node_manager)
from node_manager import NodeManager

try:
    from nicegui import ui, app, events
    HAS_NICEGUI = True
except ImportError:
    HAS_NICEGUI = False


class SimulatorEngine:
    """Core simulation data model and calculation engine matching simulate_path_back.py."""
    def __init__(self, map_folder="", waypoints_file="", speed=5):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.robot_config = {'length_m': 1.0, 'width_m': 0.46}
        self.map_config = {'use_default': False, 'default_path': ''}
        self.sim_speed = float(speed)
        self.host_ip = "127.0.0.1"
        self.sim_progress_dist = 0.0
        
        # Load robot & map config
        config_path = os.path.join(self.script_dir, '../config/robot_config.yaml')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    cfg = yaml.safe_load(f)
                    if cfg:
                        if 'robot' in cfg: self.robot_config.update(cfg['robot'])
                        if 'map' in cfg: self.map_config.update(cfg['map'])
            except Exception as e:
                print(f"Error loading robot_config.yaml: {e}")

        # Load robot image asset
        robot_img_rel = self.robot_config.get('image_path', '../resource/gs_cat_robot.png')
        robot_img_path = os.path.normpath(os.path.join(self.script_dir, robot_img_rel))
        if os.path.exists(robot_img_path):
            self.robot_img_raw = cv2.imread(robot_img_path, cv2.IMREAD_UNCHANGED)
        else:
            print(f"Warning: Robot image {robot_img_path} not found.")
            self.robot_img_raw = None

        # Load Gensurv Logo to Base64 for guaranteed display
        logo_path = os.path.normpath(os.path.join(self.script_dir, '../resource/gensurv-logo.jpg'))
        self.logo_b64 = ""
        if os.path.exists(logo_path):
            try:
                with open(logo_path, 'rb') as lf:
                    self.logo_b64 = f"data:image/jpeg;base64,{base64.b64encode(lf.read()).decode('utf-8')}"
            except Exception as e:
                print(f"Logo load error: {e}")

        # Canvas Resolution Target (Screen viewport size)
        self.canvas_w = 1200
        self.canvas_h = 800

        # Maps & State Storage
        self.maps = {}
        self.base_maps = {}
        self.current_map_id = 0
        self.path_nodes = []
        self.map_folder = map_folder
        self.waypoints_file = waypoints_file
        self.node_manager = NodeManager()

        self.display_mode = "Occ Map" # Occ Map, Layout, Combine
        self.display_params = {
            'Occ Map': {'res': None, 'ox': None, 'oy': None, 'angle': 0},
            'Layout': {'u0': 1960, 'v0': 1530, 'res': 0.05, 'angle': 88},
            'Combine': {'u0': 1960, 'v0': 1530, 'res': 0.05, 'angle': 88}
        }

        # View State (Pan and Zoom)
        self.view_state = {
            'zoom': 1.0,
            'offset_x': 0.0,
            'offset_y': 0.0,
            'default_zoom': 1.0,
            'default_offset_x': 0.0,
            'default_offset_y': 0.0,
            'follow_robot': False
        }

        # Drag state for panning
        self.is_dragging = False
        self.drag_start_x = 0.0
        self.drag_start_y = 0.0

        self.selected_wp_idx = None
        self.selected_edge_idx = None
        self.insert_idx = None
        self.edit_mode = "none" # "none", "insert", "insert_line", "edit_point"
        self.goal_pose_mode = 0 # 0: off, 1: select pos, 2: select yaw
        self.temp_goal = None
        self.sidebar_visible = True
        self.sidebar_mode = "info" # "info" or "editor"

        # Simulation states
        self.sim_running = False
        self.sim_paused = False
        self.sim_stop_flag = False
        self.status_text = "Ready. Please load a Map Directory and a Waypoints JSON."
        self.robot_pose = None # {u, v, yaw, step}
        self.sim_step_index = 0
        
        # TakeScreen directory
        self.takescreen_dir = os.path.join(self.script_dir, '../TakeScreen')
        if not os.path.exists(self.takescreen_dir):
            os.makedirs(self.takescreen_dir)

        # Attribute Enums & Mappings (Exact match with simulate_path_back.py)
        self.gait_map = {"Walking": 0, "Off-Road": 1, "Slope": 2, "Perceptual Stair": 4, "Multi-Frame Stair": 6, "Multi-Frame 45 Stair": 7}
        self.nav_mode_map = {"Straight": 0, "Auto": 1}
        self.speed_map = {"Normal": 0, "Low": 1, "High": 2}
        self.terrain_map = {"Solid": 0, "Grid": 1, "Multi-Frame": 3}
        self.point_info_map = {"Transition": 0, "Task": 1, "Standing": 2, "Charge": 3}
        self.obs_mode_map = {"Enable": 0, "Disable": 1}
        self.manner_map = {"Forward": 0, "Backward": 1}
        self.posture_map = {"Normal": 0, "Crawl": 1}

        self.gait_rev_map = {v: k for k, v in self.gait_map.items()}
        self.nav_mode_rev_map = {v: k for k, v in self.nav_mode_map.items()}
        self.speed_rev_map = {v: k for k, v in self.speed_map.items()}
        self.terrain_rev_map = {v: k for k, v in self.terrain_map.items()}
        self.point_info_rev_map = {v: k for k, v in self.point_info_map.items()}
        self.obs_mode_rev_map = {v: k for k, v in self.obs_mode_map.items()}
        self.manner_rev_map = {v: k for k, v in self.manner_map.items()}
        self.posture_rev_map = {v: k for k, v in self.posture_map.items()}

        # Load splash image
        splash_path = os.path.join(self.script_dir, '../resource/maps/picture/edit/Nestle_layout_00.png')
        if os.path.exists(splash_path):
            self.splash_img = cv2.imread(splash_path, cv2.IMREAD_COLOR)
        else:
            self.splash_img = np.zeros((800, 1200, 3), dtype=np.uint8)

        # Load initial map and waypoints if supplied
        if self.map_folder:
            self.load_map_folder(self.map_folder)
        elif self.map_config.get('use_default', False):
            dpath = self.map_config.get('default_path', '')
            if dpath:
                full_dpath = os.path.normpath(os.path.join(self.script_dir, '..', dpath))
                if os.path.exists(full_dpath):
                    self.load_map_folder(full_dpath)

        if self.waypoints_file and os.path.exists(self.waypoints_file):
            self.load_waypoints_from_file(self.waypoints_file)

    def get_target_canvas_size(self):
        if not self.maps or self.current_map_id not in self.maps:
            return 1200, 800
        if getattr(self, 'canvas_w', 0) > 0 and getattr(self, 'canvas_h', 0) > 0:
            return self.canvas_w, self.canvas_h
        m = self.maps[self.current_map_id]
        return m['width'], m['height']

    def auto_fit_map_view(self, cw=None, ch=None):
        """Calculates initial_zoom and offsets to center map cleanly matching simulate_path_back.py."""
        if self.current_map_id in self.maps:
            m = self.maps[self.current_map_id]
            mw, mh = m['width'], m['height']
            if cw is None or ch is None:
                cw, ch = self.get_target_canvas_size()
            self.canvas_w = cw
            self.canvas_h = ch
            initial_zoom = min(cw / mw, ch / mh)
            self.view_state['zoom'] = initial_zoom
            self.view_state['offset_x'] = (cw - mw * initial_zoom) / 2
            self.view_state['offset_y'] = (ch - mh * initial_zoom) / 2
            self.view_state['default_zoom'] = initial_zoom
            self.view_state['default_offset_x'] = self.view_state['offset_x']
            self.view_state['default_offset_y'] = self.view_state['offset_y']

    def load_map_folder(self, folder):
        self.map_folder = folder
        self.maps = {}
        if not folder: return
        
        if 'Nestle-full' in folder:
            try:
                yaml_path = os.path.join(self.script_dir, '../resource/maps/Nestle-full.yaml')
                with open(yaml_path, 'r') as f: config = yaml.safe_load(f)
                img_path = os.path.join(self.script_dir, '../resource/maps/picture/edit/Nestle-full-edit02.pgm')
                if not os.path.exists(img_path):
                    img_path = os.path.join(self.script_dir, '../resource/maps/Nestle-full.pgm')
                img = cv2.imread(img_path, cv2.IMREAD_COLOR)
                self.maps[0] = {
                    'image': img,
                    'resolution': config['resolution'],
                    'origin': config['origin'],
                    'height': img.shape[0],
                    'width': img.shape[1]
                }
            except Exception as e:
                print("Failed to load default Nestle-full map:", e)
        else:
            for map_id, suffix in [(0, ''), (1, '2'), (2, '3'), (3, '4')]:
                yaml_path = os.path.join(folder, f'jueying{suffix}.yaml')
                img_path = os.path.join(folder, f'jueying{suffix}.pgm')
                if os.path.exists(yaml_path) and os.path.exists(img_path):
                    try:
                        with open(yaml_path, 'r') as f: config = yaml.safe_load(f)
                        img = cv2.imread(img_path, cv2.IMREAD_COLOR)
                        self.maps[map_id] = {
                            'image': img,
                            'resolution': config['resolution'],
                            'origin': config['origin'],
                            'height': img.shape[0],
                            'width': img.shape[1],
                            'layout_image': None,
                            'combine_image': None
                        }
                        for f in os.listdir(folder):
                            f_lower = f.lower()
                            full_path = os.path.join(folder, f)
                            if any(ext in f_lower for ext in ['.png', '.webp', '.jpg', '.jpeg']):
                                if 'layout' in f_lower:
                                    self.maps[map_id]['layout_image'] = cv2.imread(full_path, cv2.IMREAD_COLOR)
                                elif 'combine' in f_lower:
                                    self.maps[map_id]['combine_image'] = cv2.imread(full_path, cv2.IMREAD_COLOR)
                    except Exception as e:
                        print(f"Error loading {yaml_path}: {e}")

            if 1 in self.maps and 2 not in self.maps:
                self.maps[2] = self.maps[1]

        if self.maps:
            self.current_map_id = 0 if 0 in self.maps else list(self.maps.keys())[0]
            self.auto_fit_map_view()
            if self.path_nodes:
                self.precalculate_path_base_maps()

    def load_waypoints_from_file(self, json_file):
        self.waypoints_file = json_file
        if not os.path.exists(json_file):
            print(f"Error: Waypoints file {json_file} not found.")
            return False

        try:
            with open(json_file, 'r') as f:
                self.path_nodes = json.load(f)
            if isinstance(self.path_nodes, list):
                for node in self.path_nodes:
                    if isinstance(node, dict) and 'fix_yaw' not in node:
                        node['fix_yaw'] = True
            if self.maps:
                self.precalculate_path_base_maps()
                if self.path_nodes:
                    first_mid = self.path_nodes[0].get('MapID', 0)
                    if first_mid in self.maps:
                        self.current_map_id = first_mid
                        self.auto_fit_map_view()
            return True
        except Exception as e:
            print(f"Error reading JSON waypoints: {e}")
            return False

    def get_map_rotation_rad(self):
        if self.display_mode == "Occ Map": return 0.0
        p = self.display_params.get(self.display_mode, self.display_params['Layout'])
        return math.radians(p.get('angle', 0))

    def world_to_pixel(self, x, y, map_id):
        if map_id not in self.maps: map_id = self.current_map_id
        if map_id not in self.maps: return 0, 0
        m = self.maps[map_id]
        if self.display_mode == "Occ Map":
            res = m['resolution']
            ox, oy = m['origin'][:2]
            u = (x - ox) / res
            v = m['height'] - (y - oy) / res
            return u, v
        else:
            p = self.display_params.get(self.display_mode, self.display_params['Layout'])
            u0, v0 = p['u0'], p['v0']
            res = p['res']
            angle_rad = math.radians(p['angle'])
            xr = x * math.cos(angle_rad) - y * math.sin(angle_rad)
            yr = x * math.sin(angle_rad) + y * math.cos(angle_rad)
            return u0 + xr / res, v0 - yr / res

    def pixel_to_world(self, u, v, map_id):
        if map_id not in self.maps: map_id = self.current_map_id
        if map_id not in self.maps: return 0.0, 0.0
        m = self.maps[map_id]
        if self.display_mode == "Occ Map":
            res = m['resolution']
            ox, oy = m['origin'][:2]
            x = u * res + ox
            y = (m['height'] - v) * res + oy
            return x, y
        else:
            p = self.display_params.get(self.display_mode, self.display_params['Layout'])
            u0, v0 = p['u0'], p['v0']
            res = p['res']
            angle_rad = math.radians(p['angle'])
            du = (u - u0) * res
            dv = (v0 - v) * res
            x = du * math.cos(angle_rad) + dv * math.sin(angle_rad)
            y = -du * math.sin(angle_rad) + dv * math.cos(angle_rad)
            return x, y

    def precalculate_path_base_maps(self):
        self.base_maps = {}
        floor_colors = [
            [(250, 206, 135), (0, 165, 255)],  # Flr 1: Via (Light Blue), Inspect (Orange)
            [(150, 255, 150), (0, 200, 0)],    # Flr 2: Via (Light Green), Inspect (Green)
            [(200, 200, 255), (0, 0, 255)],    # Flr 3: Via (Pink), Inspect (Red)
            [(255, 200, 255), (200, 0, 200)],  # Flr 4: Via (Light Purple), Inspect (Purple)
        ]

        for mid, m in self.maps.items():
            if self.display_mode == "Layout" and m.get('layout_image') is not None:
                b_map = m['layout_image'].copy()
            elif self.display_mode == "Combine" and m.get('combine_image') is not None:
                b_map = m['combine_image'].copy()
            else:
                b_map = m['image'].copy()

            # Draw lines
            visible_nodes = [node for node in self.path_nodes if not node.get('_hidden')]
            for i in range(len(visible_nodes)-1):
                p1, p2 = visible_nodes[i], visible_nodes[i+1]
                u1, v1 = self.world_to_pixel(p1['PosX'], p1['PosY'], mid)
                u2, v2 = self.world_to_pixel(p2['PosX'], p2['PosY'], mid)
                cv2.line(b_map, (int(u1), int(v1)), (int(u2), int(v2)), (200, 200, 200), 2)

            # Draw waypoints
            for node in self.path_nodes:
                if node.get('_hidden'): continue
                node_mid = node.get('MapID', 0)
                u, v = self.world_to_pixel(node['PosX'], node['PosY'], mid)
                name = str(node.get('Node_info', ''))
                n_category = NodeManager.get_node_type(name)
                val_fix_yaw = node.get('fix_yaw', True)
                fix_yaw = False if (val_fix_yaw is False or str(val_fix_yaw).lower() in ['0', 'false']) else True
                
                # Via: Blue (255,0,0), Inspection: Red (0,0,255)
                palette = [(255, 0, 0), (0, 0, 255)] if node_mid == 0 else [(255, 180, 100), (255, 0, 255)]
                color = palette[0] if n_category == 'via' else palette[1]
                
                cv2.circle(b_map, (int(u), int(v)), 4, color, -1)
                if fix_yaw:
                    arrow_len = 15
                    rot_yaw = node.get('AngleYaw', 0) + self.get_map_rotation_rad()
                    end_u = int(u + arrow_len * math.cos(rot_yaw))
                    end_v = int(v - arrow_len * math.sin(rot_yaw))
                    cv2.arrowedLine(b_map, (int(u), int(v)), (end_u, end_v), color, 2, tipLength=0.4)
                    if self.edit_mode == 'edit_point':
                        cv2.circle(b_map, (end_u, end_v), 3, (0, 255, 255), -1)
                
            # Draw CSV nodes and paths
            node_coords = {}
            for row in self.node_manager.nodes:
                if len(row) < 6: continue
                n_id = row[0]
                n_name = row[1] if len(row) > 1 else ''
                n_type = row[4].lower() if len(row) > 4 else ''
                pose_str = row[3].strip('{}')
                fix_yaw_raw = row[7] if len(row) > 7 else "1"
                fix_yaw = False if str(fix_yaw_raw).lower() in ['0', 'false'] else True
                try:
                    parts = pose_str.split(',')
                    x, y, z, yaw = map(float, parts)
                    node_mid = int(row[5])
                    if node_mid == mid or getattr(self, 'show_all_floors', False):
                        u, v = self.world_to_pixel(x, y, mid)
                        node_coords[n_id] = (u, v, yaw, n_name, node_mid, n_type, fix_yaw)
                except:
                    pass
            
            for row in self.node_manager.paths:
                if len(row) < 3: continue
                p_id = row[0]
                if p_id in self.node_manager.hidden_paths: continue
                
                n1, n2 = row[1], row[2]
                if n1 in node_coords and n2 in node_coords:
                    u1, v1 = node_coords[n1][:2]
                    u2, v2 = node_coords[n2][:2]
                    n_mid = node_coords[n1][4]
                    
                    is_selected = (p_id == self.node_manager.selected_path_id)
                    
                    if n_mid != 0 and getattr(self, 'show_all_floors', False):
                        color = (0, 255, 255) if is_selected else (200, 100, 255) # Pinkish for other floors
                    else:
                        color = (0, 255, 255) if is_selected else (200, 200, 0) # Cyan for floor 1
                    
                    thickness = 5 if is_selected else 2
                    
                    cv2.line(b_map, (int(u1), int(v1)), (int(u2), int(v2)), color, thickness)
                    
            selected_pair = getattr(self, 'selected_node_pair', [])
            for n_id, (u, v, yaw, n_name, node_mid, n_type, fix_yaw) in node_coords.items():
                if n_id in getattr(self.node_manager, 'hidden_nodes', set()): continue
                
                is_selected = (n_id == getattr(self.node_manager, 'selected_node_id', None)) or (n_id in selected_pair)
                n_category = NodeManager.get_node_type(n_id, n_name, n_type)
                
                if node_mid != 0 and getattr(self, 'show_all_floors', False):
                    # Other floors (Pink for Inspection, Light Blue for Via)
                    color = (0, 255, 255) if is_selected else ((255, 180, 100) if n_category == 'via' else (255, 0, 255)) 
                else:
                    # Floor 1 (Pure Blue (255,0,0) for Via, Pure Red (0,0,255) for Inspection)
                    color = (0, 255, 255) if is_selected else ((255, 0, 0) if n_category == 'via' else (0, 0, 255))
                
                radius = 4
                thickness = 2
                
                cv2.circle(b_map, (int(u), int(v)), radius, color, -1)
                if is_selected:
                    cv2.circle(b_map, (int(u), int(v)), 8, (0, 0, 255), 2) # Red outline circle for highlight
                
                if fix_yaw:
                    arrow_len = 15
                    r_yaw = yaw + self.get_map_rotation_rad()
                    end_u = int(u + arrow_len * math.cos(r_yaw))
                    end_v = int(v - arrow_len * math.sin(r_yaw))
                    cv2.arrowedLine(b_map, (int(u), int(v)), (end_u, end_v), color, thickness, tipLength=0.4)

            self.base_maps[mid] = b_map

    def draw_robot(self, frame, u, v, yaw):
        if self.current_map_id not in self.maps: return
        m = self.maps[self.current_map_id]
        res = m['resolution']
        
        target_w = int(self.robot_config.get('length_m', 1.0) / res)
        target_h = int(self.robot_config.get('width_m', 0.46) / res)

        if self.robot_img_raw is not None:
            resized = cv2.resize(self.robot_img_raw, (target_w, target_h))
            angle_deg = math.degrees(yaw)
            rot_mat = cv2.getRotationMatrix2D((target_w/2, target_h/2), angle_deg, 1.0)
            
            cos = np.abs(rot_mat[0, 0])
            sin = np.abs(rot_mat[0, 1])
            new_w = int((target_h * sin) + (target_w * cos))
            new_h = int((target_h * cos) + (target_w * sin))
            
            rot_mat[0, 2] += (new_w / 2) - (target_w / 2)
            rot_mat[1, 2] += (new_h / 2) - (target_h / 2)
            
            rotated = cv2.warpAffine(resized, rot_mat, (new_w, new_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0,0))
            
            y1, y2 = int(v - new_h/2), int(v + new_h - new_h/2)
            x1, x2 = int(u - new_w/2), int(u + new_w - new_w/2)
            
            fh, fw = frame.shape[:2]
            if y1 < 0 or y2 > fh or x1 < 0 or x2 > fw:
                ry1, ry2 = max(0, -y1), new_h - max(0, y2 - fh)
                rx1, rx2 = max(0, -x1), new_w - max(0, x2 - fw)
                y1, y2 = max(0, y1), min(fh, y2)
                x1, x2 = max(0, x1), min(fw, x2)
                if ry1 >= ry2 or rx1 >= rx2: return
                rotated = rotated[ry1:ry2, rx1:rx2]
            
            alpha = rotated[:, :, 3] / 255.0
            for c in range(3):
                frame[y1:y2, x1:x2, c] = (1.0 - alpha) * frame[y1:y2, x1:x2, c] + alpha * rotated[:, :, c]
        else:
            radius = 15
            cv2.circle(frame, (int(u), int(v)), radius, (0, 255, 255), -1)
            cv2.circle(frame, (int(u), int(v)), radius, (0, 0, 0), 2)
            end_u = int(u + radius * 1.5 * math.cos(yaw))
            end_v = int(v - radius * 1.5 * math.sin(yaw))
            cv2.line(frame, (int(u), int(v)), (end_u, end_v), (0, 0, 255), 3)

    def point_to_line_dist(self, px, py, x1, y1, x2, y2):
        line_len = math.hypot(x2 - x1, y2 - y1)
        if line_len < 1e-6: return math.hypot(px - x1, py - y1)
        t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / (line_len**2)))
        proj_x = x1 + t * (x2 - x1)
        proj_y = y1 + t * (y2 - y1)
        return math.hypot(px - proj_x, py - proj_y)

    def get_closest_edge(self, px, py, threshold=15):
        best_idx = None
        min_dist = threshold
        for i in range(len(self.path_nodes) - 1):
            p1, p2 = self.path_nodes[i], self.path_nodes[i+1]
            if p1.get('_hidden') or p2.get('_hidden'): continue
            u1, v1 = self.world_to_pixel(p1['PosX'], p1['PosY'], self.current_map_id)
            u2, v2 = self.world_to_pixel(p2['PosX'], p2['PosY'], self.current_map_id)
            dist = self.point_to_line_dist(px, py, u1, v1, u2, v2)
            if dist < min_dist:
                min_dist = dist
                best_idx = i + 1
        return best_idx

    def render_current_frame(self, cw=None, ch=None):
        """Generates the OpenCV BGR frame scaled to exact canvas resolution (cw, ch)."""
        if not self.maps:
            if cw is None or ch is None:
                cw, ch = 1200, 800
            return cv2.resize(self.splash_img, (cw, ch))

        if self.current_map_id in self.base_maps:
            frame = self.base_maps[self.current_map_id].copy()
        else:
            frame = self.maps[self.current_map_id]['image'].copy()

        if cw is None or ch is None:
            cw, ch = self.get_target_canvas_size()

        # Dynamic trajectory when simulation is running
        if self.robot_pose is not None and self.sim_running:
            u, v, yaw, r_step = self.robot_pose['u'], self.robot_pose['v'], self.robot_pose['yaw'], self.robot_pose['step']
            visible_visited = [node for node in self.path_nodes[:r_step+1] if not node.get('_hidden')]
            for j in range(len(visible_visited)-1):
                p1, p2 = visible_visited[j], visible_visited[j+1]
                u1, v1 = self.world_to_pixel(p1['PosX'], p1['PosY'], self.current_map_id)
                u2, v2 = self.world_to_pixel(p2['PosX'], p2['PosY'], self.current_map_id)
                cv2.line(frame, (int(u1), int(v1)), (int(u2), int(v2)), (0, 255, 0), 3)

            if r_step < len(self.path_nodes) - 1 and len(visible_visited) > 0:
                p1 = visible_visited[-1]
                u1, v1 = self.world_to_pixel(p1['PosX'], p1['PosY'], self.current_map_id)
                cv2.line(frame, (int(u1), int(v1)), (int(u), int(v)), (0, 255, 0), 3)

            self.draw_robot(frame, u, v, yaw)

            cv2.putText(frame, f"State: {self.status_text}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
            cv2.putText(frame, f"Waypoints: {len(self.path_nodes)} | Layer: {self.current_map_id}", (50, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        else:
            # Draw robot at the first waypoint if path_nodes is not empty and map matches
            if self.path_nodes:
                p = self.path_nodes[0]
                mu = p.get('MapID', 0)
                if mu == self.current_map_id:
                    u, v = self.world_to_pixel(p['PosX'], p['PosY'], mu)
                    yaw = p.get('AngleYaw', 0) + self.get_map_rotation_rad()
                    self.draw_robot(frame, u, v, yaw)

            # Highlight selected waypoint
            if self.selected_wp_idx is not None and self.selected_wp_idx < len(self.path_nodes):
                node = self.path_nodes[self.selected_wp_idx]
                u, v = self.world_to_pixel(node['PosX'], node['PosY'], self.current_map_id)
                cv2.circle(frame, (int(u), int(v)), 15, (0, 0, 255), 2)
                cv2.circle(frame, (int(u), int(v)), 2, (0, 0, 255), -1)

            # Highlight AlignYaw points (red circles)
            if getattr(self, 'align_p1_idx', None) is not None and self.align_p1_idx < len(self.path_nodes):
                node = self.path_nodes[self.align_p1_idx]
                u, v = self.world_to_pixel(node['PosX'], node['PosY'], self.current_map_id)
                cv2.circle(frame, (int(u), int(v)), 25, (0, 0, 255), 3)
            
            if getattr(self, 'align_p2_idx', None) is not None and self.align_p2_idx < len(self.path_nodes):
                node = self.path_nodes[self.align_p2_idx]
                u, v = self.world_to_pixel(node['PosX'], node['PosY'], self.current_map_id)
                cv2.circle(frame, (int(u), int(v)), 25, (0, 0, 255), 3)

            # Highlight Shift-selected node pair or add_path pair
            pair = getattr(self, 'selected_node_pair', [])
            if pair and len(pair) == 2:
                n1_id, n2_id = pair[0], pair[1]
                node_dict = {}
                for row in self.node_manager.nodes:
                    if len(row) >= 6:
                        try:
                            parts = row[3].strip('{}').split(',')
                            node_dict[row[0]] = self.world_to_pixel(float(parts[0]), float(parts[1]), self.current_map_id)
                        except: pass
                for i, node in enumerate(self.path_nodes):
                    node_name = str(node.get('Node_info', f'wp_{i}'))
                    node_dict[node_name] = self.world_to_pixel(node['PosX'], node['PosY'], self.current_map_id)
                
                p1_uv = node_dict.get(n1_id)
                p2_uv = node_dict.get(n2_id)
                
                if p1_uv:
                    cv2.circle(frame, (int(p1_uv[0]), int(p1_uv[1])), 8, (0, 0, 255), 2)
                if p2_uv:
                    cv2.circle(frame, (int(p2_uv[0]), int(p2_uv[1])), 8, (0, 0, 255), 2)
                if p1_uv and p2_uv:
                    cv2.line(frame, (int(p1_uv[0]), int(p1_uv[1])), (int(p2_uv[0]), int(p2_uv[1])), (0, 255, 255), 3)

            # Highlight selected edge (#00264d -> BGR: (77, 38, 0))
            if self.selected_edge_idx is not None and self.selected_edge_idx < len(self.path_nodes):
                idx = self.selected_edge_idx
                p1, p2 = self.path_nodes[idx-1], self.path_nodes[idx]
                u1, v1 = self.world_to_pixel(p1['PosX'], p1['PosY'], self.current_map_id)
                u2, v2 = self.world_to_pixel(p2['PosX'], p2['PosY'], self.current_map_id)
                cv2.line(frame, (int(u1), int(v1)), (int(u2), int(v2)), (77, 38, 0), 4)

            # Draw temporary 2D goal pose arrow
            if self.temp_goal:
                su, sv = self.temp_goal['start_u'], self.temp_goal['start_v']
                cu, cv = self.temp_goal['current_u'], self.temp_goal['current_v']
                cv2.circle(frame, (int(su), int(sv)), 5, (0, 255, 0), -1)
                dist_scr = math.hypot(cu - su, cv - sv)
                if dist_scr > 5:
                    cv2.arrowedLine(frame, (int(su), int(sv)), (int(cu), int(cv)), (0, 255, 0), 3, tipLength=0.3)

            # Live interactive rotation or position dragging overlay
            dtype = getattr(self, 'dragging_node_type', '') or ''
            if getattr(self, 'is_dragging', False) and dtype:
                if dtype == 'rotate_json' and getattr(self, 'dragging_node_target', None) is not None:
                    idx = self.dragging_node_target
                    if 0 <= idx < len(self.path_nodes):
                        node = self.path_nodes[idx]
                        u, v = self.world_to_pixel(node['PosX'], node['PosY'], self.current_map_id)
                        rot_yaw = node.get('AngleYaw', 0) + self.get_map_rotation_rad()
                        end_u = int(u + 25 * math.cos(rot_yaw))
                        end_v = int(v - 25 * math.sin(rot_yaw))
                        cv2.circle(frame, (int(u), int(v)), 10, (0, 255, 255), 2)
                        cv2.arrowedLine(frame, (int(u), int(v)), (end_u, end_v), (0, 255, 255), 3, tipLength=0.3)
                        cv2.circle(frame, (end_u, end_v), 5, (0, 255, 255), -1)
                elif dtype == 'rotate_csv' and getattr(self, 'dragging_node_target', None) is not None:
                    nid = self.dragging_node_target
                    row = self.node_manager.get_node_by_id(nid)
                    if row and len(row) > 3:
                        parts = row[3].strip('{}').split(',')
                        x, y, yaw = float(parts[0]), float(parts[1]), float(parts[3])
                        u, v = self.world_to_pixel(x, y, self.current_map_id)
                        rot_yaw = yaw + self.get_map_rotation_rad()
                        end_u = int(u + 25 * math.cos(rot_yaw))
                        end_v = int(v - 25 * math.sin(rot_yaw))
                        cv2.circle(frame, (int(u), int(v)), 10, (0, 255, 255), 2)
                        cv2.arrowedLine(frame, (int(u), int(v)), (end_u, end_v), (0, 255, 255), 3, tipLength=0.3)
                        cv2.circle(frame, (end_u, end_v), 5, (0, 255, 255), -1)
                elif dtype in ['json', 'csv'] and getattr(self, 'dragging_node_target', None) is not None:
                    if dtype == 'json':
                        idx = self.dragging_node_target
                        if 0 <= idx < len(self.path_nodes):
                            node = self.path_nodes[idx]
                            u, v = self.world_to_pixel(node['PosX'], node['PosY'], self.current_map_id)
                            cv2.circle(frame, (int(u), int(v)), 12, (0, 255, 255), 3)
                    elif dtype == 'csv':
                        nid = self.dragging_node_target
                        row = self.node_manager.get_node_by_id(nid)
                        if row and len(row) > 3:
                            parts = row[3].strip('{}').split(',')
                            x, y = float(parts[0]), float(parts[1])
                            u, v = self.world_to_pixel(x, y, self.current_map_id)
                            cv2.circle(frame, (int(u), int(v)), 12, (0, 255, 255), 3)

        # If follow mode is ON, update offsets to center the robot
        if self.view_state['follow_robot'] and self.robot_pose is not None:
            self.view_state['offset_x'] = cw / 2 - self.robot_pose['u'] * self.view_state['zoom']
            self.view_state['offset_y'] = ch / 2 - self.robot_pose['v'] * self.view_state['zoom']

        # Apply Viewport Matrix Transformation to Target Canvas Resolution (cw, ch) - Matching simulate_path_back.py line 1556
        M = np.float32([
            [self.view_state['zoom'], 0, self.view_state['offset_x']],
            [0, self.view_state['zoom'], self.view_state['offset_y']]
        ])
        return cv2.warpAffine(frame, M, (cw, ch))

    def frame_to_base64_url(self, frame):
        """Converts OpenCV BGR image to Data URL for web display."""
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
        return f"data:image/jpeg;base64,{jpg_as_text}"

    def find_inspection_photo(self, node_info):
        """Finds matching photo in resource/maps/picture/ matching simulate_path_back.py."""
        if not node_info: return None
        pic_dir = os.path.join(self.script_dir, '../resource/maps/picture')
        if not os.path.exists(pic_dir): return None

        search_term = str(node_info).strip().lower()
        core_match = re.search(r'(thermal|leak|gauge|vibration|loto|asset)[a-z]*[-_]*0*(\d+)', search_term)

        for f in os.listdir(pic_dir):
            f_lower = f.lower()
            if f_lower.endswith(('.png', '.jpg', '.jpeg')):
                f_clean = f_lower.replace('_', '-')
                s_clean = search_term.replace('_', '-')
                if s_clean in f_clean or s_clean.replace('-', '') in f_clean.replace('-', ''):
                    return os.path.join(pic_dir, f)
                if core_match:
                    cat, num = core_match.group(1), core_match.group(2)
                    if re.search(rf'{cat}[a-z]*[-_]*0*{num}(?!\d)', f_lower):
                        return os.path.join(pic_dir, f)
        return None


# Global Engine Instance
engine = SimulatorEngine()

# --- NiceGUI Application UI Setup ---

class LocalFilePicker(ui.dialog):
    def __init__(self, directory: str, *, 
                 only_dirs: bool = False, 
                 upper_limit: str | None = None, 
                 multiple: bool = False, 
                 show_hidden_files: bool = False) -> None:
        super().__init__()
        self.path = Path(directory).resolve()
        if not self.path.exists():
            self.path = Path('.').resolve()
        
        self.only_dirs = only_dirs
        self.upper_limit = Path(upper_limit).resolve() if upper_limit else None
        self.show_hidden_files = show_hidden_files
        self.hovered_path = None

        with self, ui.card().style('width: 500px; max-width: 90vw; background-color: white; border: 2px solid #00264d; border-radius: 12px; padding: 16px;'):
            ui.label('Select Folder' if only_dirs else 'Select File').style('font-size: 18px; font-weight: bold; color: #00264d;')
            self.path_label = ui.label(str(self.path)).style('font-size: 13px; color: #555555; word-break: break-all; font-weight: 500;')
            self.add_drives_toggle()
            
            # Custom navigation header replacing aggrid column header
            with ui.row().classes('w-full items-center justify-between no-wrap px-3 py-1 bg-gray-100 border border-gray-300 rounded-t mt-2').style('height: 38px; border-bottom: none;'):
                ui.button('◀️', on_click=self.go_up).props('flat dense').style('font-size: 14px; color: #00264d; font-weight: bold; min-width: 32px;')
                ui.label('Name').style('font-weight: bold; font-size: 14px; color: #00264d; letter-spacing: 0.5px;')
                ui.button('▶️', on_click=self.go_forward).props('flat dense').style('font-size: 14px; color: #00264d; font-weight: bold; min-width: 32px;')

            self.grid = ui.aggrid({
                'columnDefs': [{'field': 'name'}],
                'rowSelection': {'mode': 'multiRow' if multiple else 'singleRow'},
                'headerHeight': 0,
            }, html_columns=[0]).classes('w-full h-80').style('border: 1px solid #d1d5db; border-top: none; border-radius: 0 0 8px 8px;').on('cellDoubleClicked', self.handle_double_click)
            
            self.grid.on('cellMouseOver', self.handle_mouse_over)
            self.grid.on('cellMouseOut', self.handle_mouse_out)
            
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=self.close).style('background-color: gray; color: white;')
                if only_dirs:
                    ui.button('Choose Current Folder', on_click=self._handle_current_dir).style('background-color: #00264d; color: white;')
                ui.button('Ok', on_click=self._handle_ok).style('background-color: #b71836; color: white;')
                
        self.update_grid()

    def add_drives_toggle(self):
        if platform.system() == 'Windows':
            try:
                import win32api
                drives = win32api.GetLogicalDriveStrings().split('\000')[:-1]
                self.drives_toggle = ui.toggle(drives, value=self.path.anchor, on_change=self.update_drive)
            except Exception:
                pass

    def update_drive(self):
        self.path = Path(self.drives_toggle.value).resolve()
        self.update_grid()

    def handle_mouse_over(self, e: events.GenericEventArguments) -> None:
        try:
            self.hovered_path = e.args['data']['path']
        except Exception:
            self.hovered_path = None

    def handle_mouse_out(self, e: events.GenericEventArguments) -> None:
        self.hovered_path = None

    def go_up(self) -> None:
        is_at_limit = self.upper_limit is not None and self.path == self.upper_limit
        is_root = self.path == self.path.parent
        if not is_at_limit and not is_root:
            self.path = self.path.parent
            self.update_grid()

    async def go_forward(self) -> None:
        if self.hovered_path:
            selected_path = Path(self.hovered_path)
            if selected_path.is_dir():
                self.path = selected_path
                self.update_grid()
                return
        
        rows = await self.grid.get_selected_rows()
        if rows:
            selected_path = Path(rows[0]['path'])
            if selected_path.is_dir():
                self.path = selected_path
                self.update_grid()

    def update_grid(self) -> None:
        self.path_label.set_text(str(self.path))
        try:
            paths = list(self.path.glob('*'))
        except Exception:
            paths = []

        if self.only_dirs:
            paths = [p for p in paths if p.is_dir()]
        if not self.show_hidden_files:
            paths = [p for p in paths if not p.name.startswith('.')]
        
        paths.sort(key=lambda p: p.name.lower())
        if not self.only_dirs:
            paths.sort(key=lambda p: not p.is_dir())

        self.grid.options['rowData'] = [
            {
                'name': f'📁 <strong>{p.name}</strong>' if p.is_dir() else p.name,
                'path': str(p),
            }
            for p in paths
        ]
        
        self.grid.update()

    def handle_double_click(self, e: events.GenericEventArguments) -> None:
        selected_path = Path(e.args['data']['path'])
        if selected_path.is_dir():
            self.path = selected_path
            self.update_grid()
        else:
            self.submit([str(selected_path)])

    def _handle_current_dir(self):
        self.submit([str(self.path)])

    async def _handle_ok(self):
        rows = await self.grid.get_selected_rows()
        if not rows:
            if self.only_dirs:
                self.submit([str(self.path)])
            return
        self.submit([r['path'] for r in rows])


def create_nicegui_app():
    if not HAS_NICEGUI:
        print("Error: nicegui is not installed. Please run `pip install nicegui`.")
        sys.exit(1)

    app.add_static_files('/resource', os.path.join(engine.script_dir, '../resource'))
    app.add_static_files('/TakeScreen', os.path.join(engine.script_dir, '../TakeScreen'))

    async def open_map_dialog():
        default_dir = os.path.normpath(os.path.join(engine.script_dir, '../resource/maps'))
        if not os.path.exists(default_dir):
            default_dir = os.path.normpath(os.path.join(engine.script_dir, '../resource'))
        picker = LocalFilePicker(default_dir, only_dirs=True)
        result = await picker
        if result:
            update_map_folder(result[0])

    async def open_json_dialog():
        default_dir = os.path.normpath(os.path.join(engine.script_dir, '../resource/waypoints'))
        if not os.path.exists(default_dir):
            default_dir = os.path.normpath(os.path.join(engine.script_dir, '../resource/path'))
        if not os.path.exists(default_dir):
            default_dir = os.path.normpath(os.path.join(engine.script_dir, '../resource'))
        picker = LocalFilePicker(default_dir, only_dirs=False)
        result = await picker
        if result:
            reload_waypoints(result[0])

    async def load_node_paths_csv():
        default_dir = os.path.normpath(os.path.join(engine.script_dir, '../resource'))
        
        picker = LocalFilePicker(default_dir, only_dirs=False)
        result = await picker
        if not result:
            return
            
        nodes_path = result[0]
        dir_path = os.path.dirname(nodes_path)
        file_name = os.path.basename(nodes_path)
        
        # Automatically look for the corresponding path csv
        if "node" in file_name:
            path_file_name = file_name.replace("node", "path")
        else:
            path_file_name = 'paths.csv'
            
        paths_path = os.path.join(dir_path, path_file_name)
        if not os.path.exists(paths_path):
            # If not found, ask user to select it
            picker2 = LocalFilePicker(dir_path, only_dirs=False)
            result2 = await picker2
            if not result2:
                return
            paths_path = result2[0]
            
        n_ok = engine.node_manager.load_nodes(nodes_path)
        p_ok = engine.node_manager.load_paths(paths_path)
        
        if n_ok and p_ok:
            engine.precalculate_path_base_maps()
            refresh_left_sidebar()
            update_status(f"Loaded {len(engine.node_manager.nodes)} nodes and {len(engine.node_manager.paths)} paths.")
        else:
            update_status("Failed to load selected CSV files.")

    def save_node_paths_csv():
        n_ok = engine.node_manager.save_nodes()
        p_ok = engine.node_manager.save_paths()
        if n_ok and p_ok:
            update_status("Saved nodes.csv and paths.csv successfully.")
        else:
            update_status("Failed to save nodes.csv or paths.csv.")
        
    def push_undo_state():
        if not hasattr(engine, 'undo_stack'):
            engine.undo_stack = []
        state = {
            'path_nodes': copy.deepcopy(engine.path_nodes),
            'nodes': copy.deepcopy(engine.node_manager.nodes),
            'paths': copy.deepcopy(engine.node_manager.paths)
        }
        engine.undo_stack.append(state)
        if len(engine.undo_stack) > 30:
            engine.undo_stack.pop(0)

    def undo_last_edit():
        if not hasattr(engine, 'undo_stack') or not engine.undo_stack:
            ui.notify("No edits to undo", type='warning')
            update_status("No edits to undo.")
            return
        
        state = engine.undo_stack.pop()
        engine.path_nodes = state['path_nodes']
        engine.node_manager.nodes = state['nodes']
        engine.node_manager.paths = state['paths']

        try:
            engine.node_manager.save_nodes()
            engine.node_manager.save_paths()
            if engine.waypoints_file and os.path.exists(engine.waypoints_file):
                with open(engine.waypoints_file, 'w') as f:
                    json.dump(engine.path_nodes, f, indent=4)
        except Exception as e:
            print(f"Error saving undo state: {e}")

        engine.precalculate_path_base_maps()
        refresh_left_sidebar()
        refresh_canvas(force=True)
        update_status("Undid last edit.")
        ui.notify("Undid last edit.", type='positive')

    def on_add_path_click():
        pair = getattr(engine, 'selected_node_pair', [])
        if pair and len(pair) == 2:
            push_undo_state()
            n1_id, n2_id = pair[0], pair[1]
            p_id = f"path_{len(engine.node_manager.paths)+1}"
            new_path_row = [p_id, str(n1_id), str(n2_id), "1.0", "1", ""]
            engine.node_manager.paths.append(new_path_row)
            engine.node_manager.save_paths()
            
            engine.precalculate_path_base_maps()
            refresh_canvas(force=True)
            refresh_left_sidebar()
            update_status(f"Added Path [{p_id}]: {n1_id} -> {n2_id}")
        else:
            set_edit_mode('add_path')

    # Inject CSS to completely eliminate margins and paddings across all Quasar & NiceGUI page wrappers
    ui.add_head_html('''
        <style>
            html, body, .q-layout, .q-page-container, .q-page, .nicegui-content {
                margin: 0 !important;
                padding: 0 !important;
                width: 100% !important;
                height: 100% !important;
                min-height: 100% !important;
                max-width: 100vw !important;
                max-height: 100vh !important;
                overflow: hidden !important;
            }
        </style>
        <script>
            (function() {
                function setupResizeObserver() {
                    const el = document.getElementById('map-image-canvas');
                    if (el) {
                        if (el.dataset.observed) return;
                        el.dataset.observed = 'true';
                        
                        let resizeTimeout;
                        const observer = new ResizeObserver(entries => {
                            for (let entry of entries) {
                                const width = Math.round(entry.contentRect.width);
                                const height = Math.round(entry.contentRect.height);
                                if (width > 0 && height > 0) {
                                    clearTimeout(resizeTimeout);
                                    resizeTimeout = setTimeout(() => {
                                        const fn = window.emitEvent || emitEvent;
                                        if (typeof fn === 'function') {
                                            fn('map_resize', { width: width, height: height });
                                        }
                                    }, 150);
                                }
                            }
                        });
                        observer.observe(el);
                    }
                }
                
                const interval = setInterval(() => {
                    const el = document.getElementById('map-image-canvas');
                    if (el) {
                        setupResizeObserver();
                        clearInterval(interval);
                    }
                }, 100);
                
                document.addEventListener('DOMContentLoaded', setupResizeObserver);
            })();
        </script>
    ''')

    # Master Viewport Container (Fixed 100vh flex column)

    with ui.element('div').style('width: 100vw; height: 100vh; display: flex; flex-direction: column; overflow: hidden; background-color: #f3f4f6; margin: 0; padding: 0;'):

        # =========================================================================
        # ITEM 1: Layer 1 Top Bar (#00264d Dark Navy, Height 60px, 100% Full Width)
        # =========================================================================
        with ui.element('div').style('background-color: #00264d; height: 60px; width: 100%; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; border-bottom: 2px solid #001a35; box-sizing: border-box; flex-shrink: 0;'):
            
            # Left Side: Pill Menu Buttons (Dark Blue Background, White Border)
            with ui.row().classes('items-center gap-3 no-wrap'):
                
                # File Button & Dropdown Menu
                with ui.button('File').style('background-color: #00264d; border: 2px solid white; color: white; border-radius: 10px; font-weight: bold; font-size: 15px; padding: 4px 16px;'):
                    with ui.menu().style('background-color: #00264d; color: white; border: 2px solid white; border-radius: 10px; padding: 8px;'):
                        ui.label('Import').classes('text-xs font-bold text-gray-400 px-3 py-1')
                        ui.menu_item('Import Map Folder / Files', on_click=open_map_dialog).classes('text-white hover:bg-blue-900')
                        ui.menu_item('Import Waypoints JSON', on_click=open_json_dialog).classes('text-white hover:bg-blue-900')
                        ui.separator().style('background-color: white;')
                        ui.label('Export').classes('text-xs font-bold text-gray-400 px-3 py-1')
                        ui.menu_item('Export Waypoints', on_click=lambda: export_waypoints_dialog()).classes('text-white hover:bg-blue-900')
                        ui.menu_item('Export as Image', on_click=lambda: export_image_dialog()).classes('text-white hover:bg-blue-900')

                # Create Button & Dropdown Menu
                with ui.button('Create').style('background-color: #00264d; border: 2px solid white; color: white; border-radius: 10px; font-weight: bold; font-size: 15px; padding: 4px 16px;'):
                    with ui.menu().style('background-color: #00264d; color: white; border: 2px solid white; border-radius: 10px; padding: 8px;'):
                        ui.label('Waypoints').classes('text-xs font-bold text-gray-400 px-3 py-1')
                        ui.menu_item('Create Waypoint', on_click=lambda: open_create_dialog()).classes('text-white hover:bg-blue-900')

                # Edit Button (Toggles Row 5 Toolbar)
                edit_nav_btn = ui.button('Edit', on_click=lambda: toggle_edit_toolbar()).style('background-color: #00264d; border: 2px solid white; color: white; border-radius: 10px; font-weight: bold; font-size: 15px; padding: 4px 16px;')

                # View Button & Dropdown Menu
                with ui.button('View').style('background-color: #00264d; border: 2px solid white; color: white; border-radius: 10px; font-weight: bold; font-size: 15px; padding: 4px 16px;'):
                    with ui.menu().style('background-color: #00264d; color: white; border: 2px solid white; border-radius: 10px; padding: 8px;'):
                        ui.label('Capture').classes('text-xs font-bold text-gray-400 px-3 py-1')
                        ui.menu_item('Take UI Screenshot', on_click=lambda: capture_ui_screenshot()).classes('text-white hover:bg-blue-900')
                        ui.separator().style('background-color: white;')
                        ui.label('Layout').classes('text-xs font-bold text-gray-400 px-3 py-1')
                        ui.menu_item('Reset View', on_click=lambda: reset_view()).classes('text-white hover:bg-blue-900')
                        ui.menu_item('Toggle Sidebar', on_click=lambda: toggle_sidebar()).classes('text-white hover:bg-blue-900')

                # NODE Button & Dropdown Menu
                with ui.button('NODE').style('background-color: #00264d; border: 2px solid white; color: white; border-radius: 10px; font-weight: bold; font-size: 15px; padding: 4px 16px;'):
                    with ui.menu().style('background-color: #00264d; color: white; border: 2px solid white; border-radius: 10px; padding: 8px;'):
                        ui.label('Manager').classes('text-xs font-bold text-gray-400 px-3 py-1')
                        ui.menu_item('Load CSVs', on_click=lambda: load_node_paths_csv()).classes('text-white hover:bg-blue-900')
                        ui.menu_item('Save CSVs', on_click=lambda: save_node_paths_csv()).classes('text-white hover:bg-blue-900')

                # Simulate Button
                sim_nav_btn = ui.button('Simulate', on_click=lambda: start_simulation()).style('background-color: #00264d; border: 2px solid white; color: white; border-radius: 10px; font-weight: bold; font-size: 15px; padding: 4px 16px;')

            # Far Right: Gensurv Company Logo Image (Use native HTML <img> inside flex row with flex-shrink: 0)
            with ui.dialog() as settings_dialog, ui.card().style('min-width: 300px'):
                ui.label('Software Settings').classes('text-lg font-bold w-full text-center mb-4')
                ui.input('Host IP', value=engine.host_ip).on('change', lambda e: setattr(engine, 'host_ip', e.value)).classes('w-full')
                ui.number('Simulation Speed (m/s)', value=engine.sim_speed, format='%.2f', step=0.1).on('change', lambda e: setattr(engine, 'sim_speed', float(e.value))).classes('w-full')
                ui.button('Close', on_click=settings_dialog.close).classes('mt-4 w-full').style('background-color: #00264d; color: white;')

            logo_src = engine.logo_b64 if engine.logo_b64 else "/resource/gensurv-logo.jpg"
            logo_path = os.path.normpath(os.path.join(engine.script_dir, '../resource/gensurv-logo.jpg'))
            if engine.logo_b64 or os.path.exists(logo_path):
                ui.element('img').props(f'src="{logo_src}"').style('height: 40px; width: auto; object-fit: contain; flex-shrink: 0; margin-left: auto; cursor: pointer;').on('click', settings_dialog.open)
            else:
                ui.label('GENSURV ROBOTICS').style('color: white; font-weight: bold; font-size: 14px; margin-left: auto; flex-shrink: 0; cursor: pointer;').on('click', settings_dialog.open)

        # =========================================================================
        # ITEM 2: Layer 2 Top Navbar (White Control Strip with 2px #002b5b Border)
        # =========================================================================
        with ui.element('div').style('background-color: white; border-bottom: 2px solid #002b5b; width: 100%; padding: 4px 16px; display: flex; flex-direction: column; gap: 4px; box-sizing: border-box; flex-shrink: 0;'):
            
            # Row 1: Map Folder
            with ui.row().classes('items-center gap-2 w-full no-wrap'):
                ui.label('Map Dir:').style('color: black; font-weight: 500; font-size: 14px; white-space: nowrap;')
                map_input = ui.input(value=engine.map_folder).props('outlined dense').style('flex: 1; min-width: 250px; background-color: white; color: black;')
                folder_load_btn = ui.button('Update Map', on_click=open_map_dialog).style('background-color: #00264d; color: white; border-radius: 6px; font-size: 13px; width: 100px; white-space: nowrap;')

            # Row 2: Waypoints File
            with ui.row().classes('items-center gap-2 w-full no-wrap'):
                ui.label('Waypoints File:').style('color: black; font-weight: 500; font-size: 14px; white-space: nowrap;')
                wp_input = ui.input(value=engine.waypoints_file).props('outlined dense').style('flex: 1; min-width: 350px; background-color: white; color: black;')
                wp_reload_btn = ui.button('Reload', on_click=lambda: reload_waypoints(wp_input.value)).style('background-color: #00264d; color: white; border-radius: 6px; font-size: 13px; width: 80px; white-space: nowrap;')

            # Row 3: Simulation Controls
            with ui.row().classes('items-center gap-2 w-full no-wrap'):
                start_btn = ui.button('Start', on_click=lambda: start_simulation()).style('background-color: green; color: white; font-weight: bold; width: 60px; border-radius: 6px;')
                pause_btn = ui.button('Pause', on_click=lambda: toggle_pause()).style('background-color: #00264d; color: white; width: 60px; border-radius: 6px;')
                stop_btn = ui.button('Stop', on_click=lambda: stop_simulation()).style('background-color: red; color: white; font-weight: bold; width: 60px; border-radius: 6px;')
                reset_btn = ui.button('Reset View', on_click=lambda: reset_view()).style('background-color: #00264d; color: white; min-width: 100px; width: auto; white-space: nowrap; border-radius: 6px;')
                
                goal_pose_btn = ui.button('2D Goal Pose', on_click=lambda: toggle_goal_pose_mode()).style('background-color: #d1d5db; color: black; min-width: 120px; width: auto; white-space: nowrap; border-radius: 6px;')
                follow_checkbox = ui.checkbox('Follow Robot', value=engine.view_state['follow_robot'], on_change=lambda e: toggle_follow_robot(e.value)).style('color: black; white-space: nowrap;')

                status_label = ui.label(engine.status_text).style('color: black; font-size: 13px; font-weight: 500; flex: 1; min-width: 150px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;')

                ui.label('Mode:').style('color: black; font-size: 14px; white-space: nowrap;')
                mode_select = ui.select(['Occ Map', 'Layout', 'Combine'], value=engine.display_mode, 
                                       on_change=lambda e: on_mode_change(e.value)).props('outlined dense bg-color="white"').style('min-width: 130px; width: 130px; background-color: white; color: #00264d; font-weight: 500;')

            # Row 4: Manual Floor Selector Buttons
            floor_container = ui.row().classes('items-center gap-2 w-full no-wrap')
            def refresh_floor_buttons():
                floor_container.clear()
                with floor_container:
                    ui.label('Manual Floor:').style('color: black; font-size: 14px; font-weight: 500; margin-right: 4px; white-space: nowrap;')
                    
                    all_bg = '#00264d' if getattr(engine, 'show_all_floors', False) else '#e5e7eb'
                    all_text = 'white' if getattr(engine, 'show_all_floors', False) else 'black'
                    ui.button('ALL', on_click=lambda: switch_floor('ALL')).style(f'background-color: {all_bg}; color: {all_text}; font-size: 13px; padding: 2px 12px; border-radius: 6px; font-weight: bold;')
                    
                    for mid in sorted(engine.maps.keys()):
                        is_active = (mid == engine.current_map_id and not getattr(engine, 'show_all_floors', False))
                        bg_col = '#00264d' if is_active else '#e5e7eb'
                        text_col = 'white' if is_active else 'black'
                        ui.button(f'Floor {mid + 1}', on_click=lambda m=mid: switch_floor(m)).style(f'background-color: {bg_col}; color: {text_col}; font-size: 13px; padding: 2px 12px; border-radius: 6px;')
            refresh_floor_buttons()

            # Row 5: Edit Controls Toolbar (Initially Hidden)
            edit_toolbar_row = ui.row().classes('items-center gap-3 w-full py-1 hidden')
            with edit_toolbar_row:
                insert_point_btn = ui.button('InsertPoint', on_click=lambda: set_edit_mode('insert')).style('background-color: #b71836; color: white; font-weight: bold; border-radius: 6px; width: 120px; height: 35px;')
                insert_line_btn = ui.button('InsertPoint2Line', on_click=lambda: set_edit_mode('insert_line')).style('background-color: #b71836; color: white; font-weight: bold; border-radius: 6px; width: 140px; height: 35px;')
                edit_point_btn = ui.button('EditPoint', on_click=lambda: set_edit_mode('edit_point')).style('background-color: #b71836; color: white; font-weight: bold; border-radius: 6px; width: 120px; height: 35px;')
                align_yaw_btn = ui.button('AlignYaw', on_click=lambda: set_edit_mode('align_yaw')).style('background-color: #b71836; color: white; font-weight: bold; border-radius: 6px; width: 120px; height: 35px;')
                add_path_btn = ui.button('AddPath', on_click=lambda: on_add_path_click()).style('background-color: #b71836; color: white; font-weight: bold; border-radius: 6px; width: 120px; height: 35px;')
                undo_btn = ui.button('Undo', on_click=lambda: undo_last_edit()).style('background-color: #00264d; color: white; font-weight: bold; border-radius: 6px; width: 100px; height: 35px;')
        # ITEM 4 & ITEM 3: Main Canvas Viewport (Left) + Right Navbar Sidebar (Right)
        # =========================================================================
        with ui.splitter(value=18).classes('w-full flex-1 min-h-0 overflow-hidden bg-black').style('box-sizing: border-box;').props('separator-style="background-color: #001a35; width: 4px;"') as outer_splitter:
            with outer_splitter.before:
                # ITEM 5: Left Navbar (Waypoints List)
                left_sidebar_card = ui.element('div').style('background-color: #00264d; display: flex; flex-direction: column; padding: 16px; height: 100%; width: 100%; box-sizing: border-box; border-radius: 0;')
                with left_sidebar_card:
                    def on_switch_click():
                        if left_sidebar_title.text == 'Path List':
                            left_sidebar_title.set_text('Node List')
                        else:
                            left_sidebar_title.set_text('Path List')
                        refresh_left_sidebar()
                        
                    left_sidebar_title = ui.label('Path List').classes('cursor-pointer hover:text-red-400').style('color: white; font-size: 18px; font-weight: bold; text-align: center; width: 100%; margin-bottom: 12px; transition: color 0.2s;').on('click', on_switch_click)
                    
                    # Search Box for Left Sidebar
                    left_search_input = ui.input(placeholder='Search point...').props('outlined dense clearable').style('width: 100%; background-color: white; color: black; border-radius: 4px; margin-bottom: 12px;')
                    
                    waypoint_list_container = ui.column().classes('w-full flex-1 overflow-y-auto gap-2 no-wrap').style('padding-right: 4px;')
            
            with outer_splitter.after:
                with ui.splitter(value=75).classes('w-full h-full bg-black').props('separator-style="background-color: #00264d; width: 4px;"') as inner_splitter:
                    with inner_splitter.before:
                        # Left: Map Canvas with Left-click Drag Panning & Mouse Scroll Wheel Zooming
                        with ui.element('div').classes('h-full w-full bg-black flex justify-center items-center relative rounded border border-gray-400 overflow-hidden'):
                            map_image = ui.interactive_image(engine.frame_to_base64_url(engine.render_current_frame()), 
                                                            on_mouse=lambda e: on_map_mouse_event(e),
                                                            events=['click', 'mousedown', 'mouseup', 'mousemove']) \
                                .classes('w-full h-full cursor-grab active:cursor-grabbing') \
                                .props('id=map-image-canvas')
            
                            def handle_wheel_zoom(e):
                                delta = e.args.get('deltaY', 0)
                                px = e.args.get('offsetX', 0)
                                py = e.args.get('offsetY', 0)
                                if delta != 0:
                                    zoom_factor = 1.1 if delta < 0 else (1.0 / 1.1)
                                    zoom_map(zoom_factor, center_x=px, center_y=py)
                            
                            map_image.on('wheel', handle_wheel_zoom)

                            def handle_keyboard(e):
                                if e.key.name in ['Shift', 'ShiftLeft', 'ShiftRight']:
                                    engine.shift_pressed = e.action.keydown
                            ui.keyboard(on_key=handle_keyboard)
            
                            # ITEM 4: Floating Zoom Controls (+ / - / Reset)
                            with ui.row().classes('absolute bottom-4 left-4 gap-2 bg-black/60 p-2 rounded-lg backdrop-blur-sm z-10'):
                                ui.button('+', on_click=lambda: zoom_map(1.1)).props('dense round').style('background-color: #00264d; color: white; font-weight: bold;')
                                ui.button('-', on_click=lambda: zoom_map(1.0/1.1)).props('dense round').style('background-color: #00264d; color: white; font-weight: bold;')
                                ui.button('Reset', on_click=lambda: reset_view()).props('dense').style('background-color: #00264d; color: white; font-size: 12px;')
            
                            with ui.element('div').classes('absolute left-0 top-1/2 -translate-y-1/2 z-10'):
                                left_sidebar_arrow_btn = ui.button(icon='chevron_left', on_click=lambda: toggle_left_sidebar()) \
                                    .props('dense flat') \
                                    .style('background-color: #00264d; color: white; border-radius: 0 4px 4px 0;')
            
                            with ui.element('div').classes('absolute right-0 top-1/2 -translate-y-1/2 z-10'):
                                sidebar_arrow_btn = ui.button(icon='chevron_right', on_click=lambda: toggle_sidebar()) \
                                    .props('dense flat') \
                                    .style('background-color: #00264d; color: white; border-radius: 4px 0 0 4px;')
            
                    with inner_splitter.after:
                        # ITEM 3: Right Navbar Sidebar Drawer (#b71836 Red Theme, Width 450px)
                        # Exact Copy of simulate_path_back.py properties: #b71836 background, #000000 black text, 450px width
                        sidebar_card = ui.element('div').style('background-color: #b71836; display: flex; flex-direction: column; padding: 16px; height: 100%; width: 100%; overflow-y: auto; box-sizing: border-box; border-radius: 0;')
                        with sidebar_card:
                            def on_right_title_click():
                                if right_sidebar_title.text == 'Waypoint Information':
                                    right_sidebar_title.set_text('Connected Information')
                                else:
                                    right_sidebar_title.set_text('Waypoint Information')
                                refresh_right_sidebar_view()

                            right_sidebar_title = ui.label('Waypoint Information').classes('cursor-pointer hover:text-blue-900').style('color: #00264d; font-size: 20px; font-weight: bold; text-align: center; width: 100%; margin-bottom: 8px; transition: color 0.2s;').on('click', on_right_title_click)

                            # Search Row: Entry (width 250px, border 3px #00264d, bg #b71836, text #00264d) + Search button (width 80px, bg #00264d, text #FFFFFF)
                            with ui.row().classes('w-full items-center gap-2 mb-2 no-wrap'):
                                search_input = ui.input(placeholder='Name or Index...').props('outlined dense').style('width: 250px; background-color: #b71836; border: 3px solid #00264d; color: #00264d; border-radius: 0px;')
                                ui.button('Search', on_click=lambda: perform_search(search_input.value)).style('background-color: #00264d; color: #FFFFFF; font-weight: bold; border-radius: 5px; height: 35px; width: 80px;')

                            # Separator Line (#00264d height 2px)
                            ui.element('div').style('width: 100%; height: 2px; background-color: #00264d; margin: 10px 0;')

                            # Mode Toggle Buttons: Informational View vs Waypoint Editor
                            with ui.row().classes('w-full gap-2 mb-3 no-wrap'):
                                info_mode_btn = ui.button('Info View', on_click=lambda: set_sidebar_mode('info')).style('flex: 1; background-color: #00264d; color: white; font-weight: bold; border-radius: 6px;')
                                editor_mode_btn = ui.button('Editor View', on_click=lambda: set_sidebar_mode('editor')).style('flex: 1; background-color: #9ca3af; color: #00264d; font-weight: bold; border-radius: 6px;')

                            # --- Panel 1: Informational View Container ---
                            info_frame_div = ui.element('div').style('width: 100%; display: flex; flex-direction: column; gap: 8px;')
                            with info_frame_div:
                                # CTkTextbox equivalent (width 400, height 300, fg_color #b71836, text_color #00264d, border_color #00264d 2px)
                                wp_json_display = ui.code('=== CURRENT WAYPOINT ===\nSelect a waypoint on the map or via search.', language='text').style('width: 100%; height: 260px; background-color: #b71836; color: #00264d; border: 2px solid #00264d; border-radius: 0; font-weight: bold; overflow: auto; font-size: 13px;')
                                
                                prev_node_label = ui.label('Previous: None').style('color: #00264d; font-weight: bold; font-size: 13px;')
                                next_node_label = ui.label('Next: None').style('color: #00264d; font-weight: bold; font-size: 13px;')

                                # Inspection Photo Container (fg_color #FFFFFF, border_width 2, border_color #00264d)
                                photo_card = ui.element('div').style('width: 100%; min-height: 180px; background-color: #FFFFFF; border: 2px solid #00264d; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 8px; margin-top: 8px;')
                                with photo_card:
                                    photo_img = ui.image().style('max-height: 200px; max-width: 100%; object-fit: contain;')
                                    photo_msg = ui.label('No Photo Available').style('color: black; font-weight: bold; font-size: 12px; text-align: center;')

                            # --- Panel 2: Waypoint Editor Container ---
                            editor_frame_div = ui.element('div').style('width: 100%; display: none; flex-direction: column; gap: 8px;')
                            with editor_frame_div:
                                
                                def create_field_row(label_text):
                                    row = ui.row().classes('items-center gap-2 w-full no-wrap')
                                    with row:
                                        ui.label(label_text).style('color: #00264d; font-weight: bold; width: 110px; font-size: 13px;')
                                    return row

                                with create_field_row('PosX'):
                                    pos_x_in = ui.number(value=0.0, precision=4).props('outlined dense').style('flex: 1; background-color: #FFFFFF; color: #00264d; border: 1px solid #00264d;')

                                with create_field_row('PosY'):
                                    pos_y_in = ui.number(value=0.0, precision=4).props('outlined dense').style('flex: 1; background-color: #FFFFFF; color: #00264d; border: 1px solid #00264d;')

                                with create_field_row('PosZ'):
                                    pos_z_in = ui.number(value=0.0, precision=4).props('outlined dense').style('flex: 1; background-color: #FFFFFF; color: #00264d; border: 1px solid #00264d;')

                                with create_field_row('AngleYaw'):
                                    yaw_in = ui.number(value=0.0, precision=4).props('outlined dense').style('flex: 1; background-color: #FFFFFF; color: #00264d; border: 1px solid #00264d;')

                                with create_field_row('Node Info'):
                                    node_info_in = ui.input(value='Waypoint_1').props('outlined dense').style('flex: 1; background-color: #FFFFFF; color: #00264d; border: 1px solid #00264d;')

                                with create_field_row('Map ID'):
                                    map_id_in = ui.number(value=0).props('outlined dense').style('flex: 1; background-color: #FFFFFF; color: #00264d; border: 1px solid #00264d;')

                                with create_field_row('Map Name'):
                                    map_name_in = ui.input(value='1st_floor').props('outlined dense').style('flex: 1; background-color: #FFFFFF; color: #00264d; border: 1px solid #00264d;')

                                with create_field_row('Zone'):
                                    zone_in = ui.input(value='wet1').props('outlined dense').style('flex: 1; background-color: #FFFFFF; color: #00264d; border: 1px solid #00264d;')

                                # Dropdowns (White background, #00264d Navy text for crisp readability)
                                with create_field_row('Gait'):
                                    gait_select = ui.select(list(engine.gait_map.keys()), value='Walking').props('outlined dense bg-color="white"').style('flex: 1; color: #00264d;')
                                with create_field_row('Nav Mode'):
                                    nav_select = ui.select(list(engine.nav_mode_map.keys()), value='Straight').props('outlined dense bg-color="white"').style('flex: 1; color: #00264d;')
                                with create_field_row('Speed'):
                                    speed_select = ui.select(list(engine.speed_map.keys()), value='Normal').props('outlined dense bg-color="white"').style('flex: 1; color: #00264d;')
                                with create_field_row('Terrain'):
                                    terrain_select = ui.select(list(engine.terrain_map.keys()), value='Solid').props('outlined dense bg-color="white"').style('flex: 1; color: #00264d;')
                                with create_field_row('Point Info'):
                                    point_info_select = ui.select(list(engine.point_info_map.keys()), value='Transition').props('outlined dense bg-color="white"').style('flex: 1; color: #00264d;')
                                with create_field_row('Obs Mode'):
                                    obs_select = ui.select(list(engine.obs_mode_map.keys()), value='Enable').props('outlined dense bg-color="white"').style('flex: 1; color: #00264d;')
                                with create_field_row('Manner'):
                                    manner_select = ui.select(list(engine.manner_map.keys()), value='Forward').props('outlined dense bg-color="white"').style('flex: 1; color: #00264d;')
                                with create_field_row('Posture'):
                                    posture_select = ui.select(list(engine.posture_map.keys()), value='Normal').props('outlined dense bg-color="white"').style('flex: 1; color: #00264d;')
                                with create_field_row('Fix Yaw'):
                                    fix_yaw_select = ui.select(['True', 'False'], value='True').props('outlined dense bg-color="white"').style('flex: 1; color: #00264d;')

                                # Save Point Button (#00264d Navy Blue, height 50px, bold white font)
                                ui.button('Save Point', on_click=lambda: save_waypoint_from_editor()).style('background-color: #00264d; color: #FFFFFF; font-weight: bold; font-size: 16px; height: 50px; width: 100%; border-radius: 10px; margin-top: 8px;')

                            # --- Panel 3: Connected Information Container ---
                            connected_frame_div = ui.element('div').style('width: 100%; display: none; flex-direction: column; gap: 10px;')


    # =========================================================================
    # UI Mode Functions & Local File Import/Export Dialogs
    # =========================================================================

    def set_sidebar_mode(mode):
        engine.sidebar_mode = mode
        if mode == 'info':
            if right_sidebar_title.text == 'Connected Information':
                connected_frame_div.style(replace='width: 100%; display: flex; flex-direction: column; gap: 10px;')
                info_frame_div.style(replace='width: 100%; display: none;')
                editor_frame_div.style(replace='width: 100%; display: none;')
                update_connected_info()
            else:
                info_frame_div.style(replace='width: 100%; display: flex; flex-direction: column; gap: 8px;')
                editor_frame_div.style(replace='width: 100%; display: none;')
                connected_frame_div.style(replace='width: 100%; display: none;')
            info_mode_btn.style(replace='flex: 1; background-color: #00264d; color: white; font-weight: bold; border-radius: 6px;')
            editor_mode_btn.style(replace='flex: 1; background-color: #9ca3af; color: black; font-weight: bold; border-radius: 6px;')
        else:
            info_frame_div.style(replace='width: 100%; display: none;')
            connected_frame_div.style(replace='width: 100%; display: none;')
            editor_frame_div.style(replace='width: 100%; display: flex; flex-direction: column; gap: 8px;')
            info_mode_btn.style(replace='flex: 1; background-color: #9ca3af; color: black; font-weight: bold; border-radius: 6px;')
            editor_mode_btn.style(replace='flex: 1; background-color: #00264d; color: white; font-weight: bold; border-radius: 6px;')

    def refresh_right_sidebar_view():
        if right_sidebar_title.text == 'Connected Information':
            info_frame_div.style(replace='width: 100%; display: none;')
            editor_frame_div.style(replace='width: 100%; display: none;')
            connected_frame_div.style(replace='width: 100%; display: flex; flex-direction: column; gap: 10px;')
            update_connected_info()
        else:
            connected_frame_div.style(replace='width: 100%; display: none;')
            if getattr(engine, 'sidebar_mode', 'info') == 'editor':
                editor_frame_div.style(replace='width: 100%; display: flex; flex-direction: column; gap: 8px;')
                info_frame_div.style(replace='width: 100%; display: none;')
            else:
                info_frame_div.style(replace='width: 100%; display: flex; flex-direction: column; gap: 8px;')
                editor_frame_div.style(replace='width: 100%; display: none;')

    def select_node_and_update(nid):
        engine.node_manager.selected_node_id = nid
        hit_csv_node = engine.node_manager.get_node_by_id(nid)
        if hit_csv_node and len(hit_csv_node) > 5:
            try:
                f_mid = int(hit_csv_node[5])
                if f_mid in engine.maps and f_mid != engine.current_map_id:
                    switch_floor(f_mid)
            except Exception:
                pass
        select_csv_node_by_id(nid)
        engine.precalculate_path_base_maps()
        refresh_canvas(force=True)

    def update_connected_info():
        connected_frame_div.clear()
        with connected_frame_div:
            sel_nid = getattr(engine.node_manager, 'selected_node_id', None)
            sel_wp = engine.selected_wp_idx
            
            if not sel_nid and sel_wp is None:
                with ui.card().style('background-color: #00264d; color: white; width: 100%; padding: 12px; border-radius: 8px; border: 2px solid white; margin-top: 10px;'):
                    ui.label('No Node Selected').style('color: #93c5fd; font-size: 14px; font-weight: bold; text-align: center;')
                    ui.label('Click a node on the map or list to view its connected paths.').style('color: white; font-size: 12px; text-align: center; margin-top: 4px;')
                return

            node_id_str = ""
            node_name_str = ""
            incoming = []
            outgoing = []

            if sel_nid:
                node_id_str = sel_nid
                csv_node = engine.node_manager.get_node_by_id(sel_nid)
                node_name_str = csv_node[1] if (csv_node and len(csv_node) > 1) else sel_nid
                
                for row in engine.node_manager.paths:
                    if len(row) >= 3:
                        p_id, n1, n2 = row[0], row[1], row[2]
                        if n2 == sel_nid:
                            incoming.append((p_id, n1))
                        if n1 == sel_nid:
                            outgoing.append((p_id, n2))

            elif sel_wp is not None and 0 <= sel_wp < len(engine.path_nodes):
                curr_node = engine.path_nodes[sel_wp]
                node_id_str = f"wp_{sel_wp}"
                node_name_str = str(curr_node.get('Node_info', f"wp_{sel_wp}"))
                
                if sel_wp > 0:
                    prev_info = engine.path_nodes[sel_wp-1].get('Node_info', f"wp_{sel_wp-1}")
                    incoming.append(("seq", prev_info, sel_wp-1))
                if sel_wp < len(engine.path_nodes) - 1:
                    next_info = engine.path_nodes[sel_wp+1].get('Node_info', f"wp_{sel_wp+1}")
                    outgoing.append(("seq", next_info, sel_wp+1))

            with ui.card().style('background-color: #00264d; color: white; width: 100%; padding: 12px; border-radius: 8px; border: 2px solid white;'):
                ui.label('SELECTED NODE').style('color: #93c5fd; font-size: 11px; font-weight: bold; letter-spacing: 1px;')
                ui.label(f'{node_id_str} : {node_name_str}').style('color: white; font-size: 16px; font-weight: bold;')

            with ui.column().classes('w-full gap-1 mt-1'):
                with ui.row().classes('items-center justify-between w-full px-1'):
                    ui.label('INCOMING (มาจาก Node)').style('color: #00264d; font-weight: bold; font-size: 14px;')
                    ui.label(f'{len(incoming)} paths').style('color: #00264d; font-weight: bold; font-size: 12px;')
                
                if not incoming:
                    ui.label('No incoming paths').style('color: white; font-size: 12px; font-style: italic; margin-left: 8px;')
                else:
                    for item in incoming:
                        if len(item) == 2:
                            p_id, from_nid = item
                            with ui.row().classes('w-full items-center justify-between p-2 rounded cursor-pointer hover:bg-blue-900').style('background-color: #00264d; border: 1px solid white; margin-bottom: 2px;').on('click', lambda fn=from_nid: select_node_and_update(fn)):
                                ui.label(f'← FROM: {from_nid}').style('color: white; font-weight: bold; font-size: 13px;')
                                ui.label(f'[{p_id}]').style('color: #93c5fd; font-size: 11px;')
                        elif len(item) == 3:
                            _, prev_name, prev_idx = item
                            with ui.row().classes('w-full items-center justify-between p-2 rounded cursor-pointer hover:bg-blue-900').style('background-color: #00264d; border: 1px solid white; margin-bottom: 2px;').on('click', lambda pidx=prev_idx: select_waypoint_from_list(pidx)):
                                ui.label(f'← FROM: {prev_name}').style('color: white; font-weight: bold; font-size: 13px;')
                                ui.label(f'[Index {prev_idx}]').style('color: #93c5fd; font-size: 11px;')

            with ui.column().classes('w-full gap-1 mt-2'):
                with ui.row().classes('items-center justify-between w-full px-1'):
                    ui.label('OUTGOING (ไป Node)').style('color: #00264d; font-weight: bold; font-size: 14px;')
                    ui.label(f'{len(outgoing)} paths').style('color: #00264d; font-weight: bold; font-size: 12px;')
                
                if not outgoing:
                    ui.label('No outgoing paths').style('color: white; font-size: 12px; font-style: italic; margin-left: 8px;')
                else:
                    for item in outgoing:
                        if len(item) == 2:
                            p_id, to_nid = item
                            with ui.row().classes('w-full items-center justify-between p-2 rounded cursor-pointer hover:bg-blue-900').style('background-color: #00264d; border: 1px solid white; margin-bottom: 2px;').on('click', lambda tn=to_nid: select_node_and_update(tn)):
                                ui.label(f'→ TO: {to_nid}').style('color: white; font-weight: bold; font-size: 13px;')
                                ui.label(f'[{p_id}]').style('color: #93c5fd; font-size: 11px;')
                        elif len(item) == 3:
                            _, next_name, next_idx = item
                            with ui.row().classes('w-full items-center justify-between p-2 rounded cursor-pointer hover:bg-blue-900').style('background-color: #00264d; border: 1px solid white; margin-bottom: 2px;').on('click', lambda nidx=next_idx: select_waypoint_from_list(nidx)):
                                ui.label(f'→ TO: {next_name}').style('color: white; font-weight: bold; font-size: 13px;')
                                ui.label(f'[Index {next_idx}]').style('color: #93c5fd; font-size: 11px;')

    def toggle_sidebar():
        engine.sidebar_visible = not engine.sidebar_visible
        if engine.sidebar_visible:
            inner_splitter.set_value(75)
            sidebar_arrow_btn._props['icon'] = 'chevron_right'
            sidebar_arrow_btn.update()
        else:
            inner_splitter.set_value(100)
            sidebar_arrow_btn._props['icon'] = 'chevron_left'
            sidebar_arrow_btn.update()

    def toggle_edit_toolbar():
        if 'hidden' in edit_toolbar_row.classes:
            edit_toolbar_row.classes(remove='hidden')
            edit_nav_btn.style('background-color: #001a35; border: 2px solid white; color: white; border-radius: 10px; font-weight: bold; font-size: 15px; padding: 4px 16px;')
        else:
            edit_toolbar_row.classes(add='hidden')
            edit_nav_btn.style('background-color: #00264d; border: 2px solid white; color: white; border-radius: 10px; font-weight: bold; font-size: 15px; padding: 4px 16px;')
            set_edit_mode('none')



    def open_create_dialog():
        with ui.dialog() as dialog, ui.card().style('background-color: #ffffff; border: 2px solid #00264d; padding: 20px; width: 350px; border-radius: 15px;'):
            ui.label('Create Waypoints').style('font-size: 18px; font-weight: bold; color: #00264d; margin-bottom: 10px;')
            ui.label('Filename:').style('color: black; font-weight: 500;')
            name_in = ui.input(placeholder='e.g. mission_01').props('outlined dense').style('width: 100%; background-color: white; margin-bottom: 15px;')
            with ui.row().classes('justify-between w-full gap-2'):
                ui.button('Cancel', on_click=dialog.close).style('background-color: #9ca3af; color: black; flex: 1;')
                ui.button('Create', on_click=lambda: (create_new_waypoints_file(name_in.value), dialog.close())).style('background-color: #00264d; color: white; flex: 1;')
        dialog.open()

    def create_new_waypoints_file(filename):
        if not filename: return
        if not filename.endswith('.json'): filename += '.json'
        
        script_dir = engine.script_dir
        tmp_dir = os.path.join(script_dir, '../tmp')
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
            
        file_path = os.path.join(tmp_dir, filename)
        try:
            with open(file_path, 'w') as f:
                json.dump([], f, indent=4)
            engine.waypoints_file = file_path
            wp_input.set_value(file_path)
            engine.path_nodes = []
            engine.precalculate_path_base_maps()
            refresh_canvas()
            update_status(f'Created new waypoint file: {filename}')
            ui.notify(f'Created new waypoint file: {filename}', type='positive')
        except Exception as e:
            update_status(f'Error creating file: {e}')
            ui.notify(f'Error creating file: {e}', type='negative')

    def export_waypoints_dialog():
        if engine.waypoints_file and engine.path_nodes:
            ui.download(engine.waypoints_file, os.path.basename(engine.waypoints_file))
            update_status(f'Exported to {os.path.basename(engine.waypoints_file)}')
            ui.notify(f'Exported {os.path.basename(engine.waypoints_file)}', type='positive')
        else:
            update_status('No waypoints to export.')

    def export_image_dialog():
        frame = engine.render_current_frame()
        export_path = os.path.join(engine.takescreen_dir, f'map_export_{int(time.time())}.png')
        cv2.imwrite(export_path, frame)
        ui.download(export_path, os.path.basename(export_path))
        update_status(f'Image saved to {os.path.basename(export_path)}')
        ui.notify('Exported current map frame as image!', type='positive')

    def capture_ui_screenshot():
        frame = engine.render_current_frame()
        save_path = os.path.join(engine.takescreen_dir, f'ui_screenshot_{int(time.time())}.png')
        cv2.imwrite(save_path, frame)
        update_status(f'UI Screenshot saved to {os.path.basename(save_path)}')
        ui.notify(f'UI Screenshot saved to {os.path.basename(save_path)}', type='positive')

    def reset_view():
        engine.auto_fit_map_view()
        refresh_canvas(force=True)

    def zoom_map(factor, center_x=None, center_y=None):
        """Map zoom calculation matching simulate_path_back.py lines 1796-1799."""
        if center_x is None or center_y is None:
            cw, ch = engine.get_target_canvas_size()
            center_x, center_y = cw / 2, ch / 2
        engine.view_state['offset_x'] = center_x - (center_x - engine.view_state['offset_x']) * factor
        engine.view_state['offset_y'] = center_y - (center_y - engine.view_state['offset_y']) * factor
        engine.view_state['zoom'] *= factor
        refresh_canvas()

    # Keyboard shortcut listener (w/a/s/d pan, +/- zoom, r reset) matching simulate_path_back.py
    def on_keyboard(e):
        k = e.key.name.lower() if e.key.name else ""
        if k == 'r':
            reset_view()
        elif k in ['=', '+']:
            zoom_map(1.1)
        elif k == '-':
            zoom_map(1.0 / 1.1)
        elif k == 'w':
            engine.view_state['offset_y'] += 50
            refresh_canvas(force=True)
        elif k == 's':
            engine.view_state['offset_y'] -= 50
            refresh_canvas(force=True)
        elif k == 'a':
            engine.view_state['offset_x'] += 50
            refresh_canvas(force=True)
        elif k == 'd':
            engine.view_state['offset_x'] -= 50
            refresh_canvas(force=True)

    ui.keyboard(on_key=on_keyboard)

    # =========================================================================
    # Event Handlers & State Management
    # =========================================================================

    last_render_time = [0.0]

    def refresh_canvas(force=False):
        now = time.time()
        if not force and (now - last_render_time[0]) < 0.05:
            return
        last_render_time[0] = now
        map_image.set_source(engine.frame_to_base64_url(engine.render_current_frame()))

    def handle_map_resize(e):
        w = int(e.args.get('width', 1200))
        h = int(e.args.get('height', 800))
        if abs(engine.canvas_w - w) > 5 or abs(engine.canvas_h - h) > 5:
            engine.canvas_w = w
            engine.canvas_h = h
            if not getattr(engine, 'view_initialized', False):
                engine.auto_fit_map_view(w, h)
                engine.view_initialized = True
            refresh_canvas(force=True)

    ui.on('map_resize', handle_map_resize)

    engine.left_sidebar_visible = True
    def toggle_left_sidebar():
        engine.left_sidebar_visible = not getattr(engine, 'left_sidebar_visible', True)
        if engine.left_sidebar_visible:
            outer_splitter.set_value(18)
            left_sidebar_arrow_btn._props['icon'] = 'chevron_left'
            left_sidebar_arrow_btn.update()
        else:
            outer_splitter.set_value(0)
            left_sidebar_arrow_btn._props['icon'] = 'chevron_right'
            left_sidebar_arrow_btn.update()

    def toggle_waypoint_visibility(idx):
        if 0 <= idx < len(engine.path_nodes):
            node = engine.path_nodes[idx]
            node['_hidden'] = not node.get('_hidden', False)
            engine.precalculate_path_base_maps()
            refresh_canvas(force=True)
            refresh_left_sidebar()

    def handle_sidebar_item_update(update_sidebar=True, push_undo=False):
        if push_undo:
            push_undo_state()
        engine.precalculate_path_base_maps()
        refresh_canvas(force=True)
        if update_sidebar:
            refresh_left_sidebar()

        sel_nid = getattr(engine.node_manager, 'selected_node_id', None)
        sel_pid = getattr(engine.node_manager, 'selected_path_id', None)
        if sel_nid:
            select_csv_node_by_id(sel_nid)
        elif sel_pid:
            select_csv_path_by_id(sel_pid)

    def select_csv_node_by_id(n_id):
        if not n_id: return
        hit_csv_node = engine.node_manager.get_node_by_id(n_id)
        if not hit_csv_node: return

        engine.selected_wp_idx = None
        fix_yaw_raw = hit_csv_node[7] if len(hit_csv_node) > 7 else "1"
        fix_yaw_val = False if str(fix_yaw_raw).lower() in ['0', 'false'] else True

        node_dict = {
            "ID": n_id,
            "Name": hit_csv_node[1] if len(hit_csv_node) > 1 else "",
            "Group": hit_csv_node[2] if len(hit_csv_node) > 2 else "",
            "Pose": hit_csv_node[3] if len(hit_csv_node) > 3 else "",
            "Type": hit_csv_node[4] if len(hit_csv_node) > 4 else "",
            "MapID": hit_csv_node[5] if len(hit_csv_node) > 5 else "",
            "Zone": hit_csv_node[6] if len(hit_csv_node) > 6 else "",
            "fix_yaw": fix_yaw_val
        }
        
        formatted_json = "=== CSV NODE ===\n" + json.dumps(node_dict, indent=2)
        wp_json_display.set_content(formatted_json)
        
        prev_node_label.set_text('Previous: None')
        next_node_label.set_text('Next: None')
        
        node_info_in.set_value(node_dict["Name"])
        try:
            map_id_in.set_value(int(node_dict["MapID"]))
            parts = node_dict["Pose"].strip('{}').split(',')
            pos_x_in.set_value(round(float(parts[0]), 4))
            pos_y_in.set_value(round(float(parts[1]), 4))
            pos_z_in.set_value(round(float(parts[2]), 4))
            yaw_in.set_value(round(float(parts[3]), 4))
        except Exception:
            pass
            
        zone_in.set_value(node_dict["Zone"])
        fix_yaw_select.set_value('True' if fix_yaw_val else 'False')
        
        photo_path = engine.find_inspection_photo(node_dict["ID"])
        if photo_path and os.path.exists(photo_path):
            rel_photo = os.path.relpath(photo_path, os.path.join(engine.script_dir, '../resource'))
            photo_img.set_source(f'/resource/{rel_photo}')
            photo_msg.set_text(f'Inspection Photo: {node_dict["ID"]}')
        else:
            photo_img.set_source('')
            photo_msg.set_text('No Photo Available')
            
        update_connected_info()
        update_status(f"Selected CSV Node [{n_id}]: {node_dict['Name']}")

    def select_csv_path_by_id(p_id):
        if not p_id: return
        hit_csv_path = None
        for row in engine.node_manager.paths:
            if len(row) > 0 and row[0] == p_id:
                hit_csv_path = row
                break
        if not hit_csv_path: return

        engine.selected_wp_idx = None
        path_dict = {
            "ID": p_id,
            "Start Node": hit_csv_path[1] if len(hit_csv_path) > 1 else "",
            "End Node": hit_csv_path[2] if len(hit_csv_path) > 2 else "",
            "Length": hit_csv_path[3] if len(hit_csv_path) > 3 else "",
            "Type": hit_csv_path[4] if len(hit_csv_path) > 4 else "",
            "Data": hit_csv_path[5] if len(hit_csv_path) > 5 else ""
        }
        
        formatted_json = "=== CSV PATH ===\n" + json.dumps(path_dict, indent=2)
        wp_json_display.set_content(formatted_json)
        
        prev_node_label.set_text(f'Start: {path_dict["Start Node"]}')
        next_node_label.set_text(f'End: {path_dict["End Node"]}')
        
        node_info_in.set_value(f"{path_dict['Start Node']} -> {path_dict['End Node']}")
        photo_img.set_source('')
        photo_msg.set_text('No Photo Available')
        update_status(f"Selected CSV Path [{p_id}]: {path_dict['Start Node']} -> {path_dict['End Node']}")

    def refresh_left_sidebar():
        waypoint_list_container.clear()
        search_query = left_search_input.value.lower() if left_search_input.value else ""
        with waypoint_list_container:
            if left_sidebar_title.text == 'Path List':
                engine.node_manager.render_left_sidebar_paths(handle_sidebar_item_update, search_query)
            else:
                engine.node_manager.render_left_sidebar_nodes(handle_sidebar_item_update, search_query)

    left_search_input.on('update:model-value', lambda e: refresh_left_sidebar())

    def select_waypoint_from_list(idx):
        engine.selected_wp_idx = idx
        update_sidebar_info(idx)
        f_mid = engine.path_nodes[idx].get('MapID', 0)
        if f_mid in engine.maps and f_mid != engine.current_map_id:
            switch_floor(f_mid)
        else:
            refresh_canvas(force=True)
        update_status(f"Selected: {engine.path_nodes[idx].get('Node_info')}")

    def update_status(text):
        engine.status_text = text
        status_label.set_text(text)
        refresh_canvas()

    def toggle_follow_robot(val):
        engine.view_state['follow_robot'] = val

    def update_sidebar_info(idx):
        if idx is None or idx >= len(engine.path_nodes):
            wp_json_display.set_content('=== CURRENT WAYPOINT ===\nSelect a waypoint on the map or via search.')
            prev_node_label.set_text('Previous: None')
            next_node_label.set_text('Next: None')
            photo_img.set_source('')
            photo_msg.set_text('No Photo Available')
            return

        curr_node = engine.path_nodes[idx]
        if 'fix_yaw' not in curr_node:
            curr_node['fix_yaw'] = True
        formatted_json = "=== CURRENT WAYPOINT ===\n" + json.dumps(curr_node, indent=2)
        wp_json_display.set_content(formatted_json)
        update_connected_info()

        # Update neighbors
        prev_str = engine.path_nodes[idx-1].get('Node_info', '') if idx > 0 else 'None'
        next_str = engine.path_nodes[idx+1].get('Node_info', '') if idx < len(engine.path_nodes)-1 else 'None'
        prev_node_label.set_text(f'Previous: {prev_str}')
        next_node_label.set_text(f'Next: {next_str}')

        # Populate editor fields
        node_info_in.set_value(str(curr_node.get('Node_info', '')))
        map_id_in.set_value(curr_node.get('MapID', 0))
        zone_in.set_value(str(curr_node.get('Zone', '')))
        map_name_in.set_value(str(curr_node.get('MapName', '')))
        pos_x_in.set_value(round(curr_node.get('PosX', 0.0), 4))
        pos_y_in.set_value(round(curr_node.get('PosY', 0.0), 4))
        pos_z_in.set_value(round(curr_node.get('PosZ', 0.0), 4))
        yaw_in.set_value(round(curr_node.get('AngleYaw', 0.0), 4))

        gait_select.set_value(engine.gait_rev_map.get(curr_node.get('Gait', 0), 'Walking'))
        nav_select.set_value(engine.nav_mode_rev_map.get(curr_node.get('NavMode', 0), 'Straight'))
        speed_select.set_value(engine.speed_rev_map.get(curr_node.get('Speed', 0), 'Normal'))
        terrain_select.set_value(engine.terrain_rev_map.get(curr_node.get('Terrain', 0), 'Solid'))
        point_info_select.set_value(engine.point_info_rev_map.get(curr_node.get('PointInfo', 0), 'Transition'))
        obs_select.set_value(engine.obs_mode_rev_map.get(curr_node.get('ObsMode', 0), 'Enable'))
        manner_select.set_value(engine.manner_rev_map.get(curr_node.get('Manner', 0), 'Forward'))
        posture_select.set_value(engine.posture_rev_map.get(curr_node.get('Posture', 0), 'Normal'))
        val_fix_yaw = curr_node.get('fix_yaw', True)
        fix_yaw_select.set_value('True' if (val_fix_yaw is True or str(val_fix_yaw).lower() == 'true') else 'False')

        # Inspection photo search
        node_info = curr_node.get('Node_info', '')
        is_inspection = curr_node.get('PointInfo') == 1 or any(kw in str(node_info).lower() for kw in ['thermal', 'leak', 'gauge', 'vibration', 'loto', 'asset'])
        photo_path = engine.find_inspection_photo(node_info)

        if photo_path and os.path.exists(photo_path):
            rel_photo = os.path.relpath(photo_path, os.path.join(engine.script_dir, '../resource'))
            photo_img.set_source(f'/resource/{rel_photo}')
            photo_msg.set_text(f'Inspection Photo: {node_info}')
        elif is_inspection:
            photo_img.set_source('')
            photo_msg.set_text(f"No Photo Found for:\n'{node_info}'")
        else:
            photo_img.set_source('')
            photo_msg.set_text('No Photo Available')

    def save_waypoint_from_editor():
        try:
            push_undo_state()
            cam_ptz = [0.0, 0.0, 0.0]
            if engine.selected_wp_idx is not None and engine.selected_wp_idx < len(engine.path_nodes):
                cam_ptz = engine.path_nodes[engine.selected_wp_idx].get("CamPTZ", [0.0, 0.0, 0.0])

            node = {
                "Node_info": node_info_in.value,
                "MapName": map_name_in.value,
                "Zone": zone_in.value,
                "MapID": int(map_id_in.value),
                "Gait": engine.gait_map[gait_select.value],
                "NavMode": engine.nav_mode_map[nav_select.value],
                "Speed": engine.speed_map[speed_select.value],
                "Terrain": engine.terrain_map[terrain_select.value],
                "PointInfo": engine.point_info_map[point_info_select.value],
                "ObsMode": engine.obs_mode_map[obs_select.value],
                "Manner": engine.manner_map[manner_select.value],
                "Posture": engine.posture_map[posture_select.value],
                "fix_yaw": (fix_yaw_select.value == 'True' or fix_yaw_select.value is True),
                "PosX": float(pos_x_in.value),
                "PosY": float(pos_y_in.value),
                "PosZ": float(pos_z_in.value),
                "AngleYaw": float(yaw_in.value),
                "Value": 0,
                "CamPTZ": cam_ptz
            }

            sel_nid = getattr(engine.node_manager, 'selected_node_id', None)
            if engine.selected_wp_idx is not None:
                engine.path_nodes[engine.selected_wp_idx] = node
                update_status(f"Updated point: {node['Node_info']}")
            elif sel_nid:
                row = engine.node_manager.get_node_by_id(sel_nid)
                if row:
                    if len(row) > 1: row[1] = node_info_in.value
                    if len(row) > 3: row[3] = f"{{{pos_x_in.value},{pos_y_in.value},{pos_z_in.value},{yaw_in.value}}}"
                    if len(row) > 5: row[5] = str(map_id_in.value)
                    if len(row) > 6: row[6] = zone_in.value
                    while len(row) < 8: row.append("0")
                    row[7] = "1" if (fix_yaw_select.value == 'True' or fix_yaw_select.value is True) else "0"
                    engine.node_manager.save_nodes()
                    update_status(f"Updated CSV node [{sel_nid}]")
            elif engine.insert_idx is not None:
                engine.path_nodes.insert(engine.insert_idx, node)
                update_status(f"Inserted point at [{engine.insert_idx}]: {node['Node_info']}")
                engine.insert_idx = None
            else:
                engine.path_nodes.append(node)
                update_status(f"Added new point: {node['Node_info']}")

            json_file = engine.waypoints_file
            if json_file:
                tmp_dir = os.path.join(engine.script_dir, "../tmp")
                if not os.path.exists(tmp_dir):
                    os.makedirs(tmp_dir)

                if "tmp" not in os.path.dirname(json_file):
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    base_name = os.path.splitext(os.path.basename(json_file))[0]
                    json_file = os.path.join(tmp_dir, f"{base_name}_edit_{timestamp}.json")
                    engine.waypoints_file = json_file
                    wp_input.set_value(json_file)

                for i, n in enumerate(engine.path_nodes):
                    n['Value'] = i

                with open(json_file, 'w') as f:
                    json.dump(engine.path_nodes, f, indent=4)
                update_status(f"Saved point: {node['Node_info']} to {os.path.basename(json_file)}")

            engine.precalculate_path_base_maps()
            refresh_canvas()
            refresh_left_sidebar()

        except Exception as e:
            update_status(f"Save Error: {e}")

    def set_edit_mode(mode):
        if engine.edit_mode == mode:
            mode = "none"

        engine.edit_mode = mode
        insert_point_btn.style('background-color: #b71836; color: white; font-weight: bold; border-radius: 6px; width: 120px; height: 35px;')
        insert_line_btn.style('background-color: #b71836; color: white; font-weight: bold; border-radius: 6px; width: 140px; height: 35px;')
        edit_point_btn.style('background-color: #b71836; color: white; font-weight: bold; border-radius: 6px; width: 120px; height: 35px;')
        align_yaw_btn.style('background-color: #b71836; color: white; font-weight: bold; border-radius: 6px; width: 120px; height: 35px;')
        add_path_btn.style('background-color: #b71836; color: white; font-weight: bold; border-radius: 6px; width: 120px; height: 35px;')

        if mode == 'insert':
            insert_point_btn.style('background-color: #90122a; color: white; font-weight: bold; border-radius: 6px; width: 120px; height: 35px;')
            engine.insert_idx = None
            update_status('Append Mode: Click anywhere on map to add point to the end.')
            if engine.goal_pose_mode == 0:
                toggle_goal_pose_mode()
        elif mode == 'insert_line':
            if engine.selected_edge_idx is None:
                update_status('Please select an edge on the map first (Click a line until it turns blue).')
                engine.edit_mode = "none"
                return
            insert_line_btn.style('background-color: #90122a; color: white; font-weight: bold; border-radius: 6px; width: 140px; height: 35px;')
            engine.insert_idx = engine.selected_edge_idx
            update_status(f'Insert Line Mode (Edge {engine.selected_edge_idx} selected): Step 1 - Set position.')
            if engine.goal_pose_mode == 0:
                toggle_goal_pose_mode()
        elif mode == 'edit_point':
            edit_point_btn.style('background-color: #90122a; color: white; font-weight: bold; border-radius: 6px; width: 120px; height: 35px;')
            set_sidebar_mode('editor')
            update_status('Edit Mode: Click an existing waypoint on the map to edit.')
        elif mode == 'align_yaw':
            align_yaw_btn.style('background-color: #90122a; color: white; font-weight: bold; border-radius: 6px; width: 120px; height: 35px;')
            engine.align_step = 1
            engine.align_p1_idx = None
            engine.align_p2_idx = None
            update_status('AlignYaw Mode: Click Point 1 (the point to update).')
        elif mode == 'add_path':
            add_path_btn.style('background-color: #90122a; color: white; font-weight: bold; border-radius: 6px; width: 120px; height: 35px;')
            engine.add_path_step = 1
            engine.add_path_node1 = None
            engine.add_path_node2 = None
            update_status('AddPath Mode: Click Node 1 (Start Node) on the map.')
        elif mode == 'none':
            engine.align_p1_idx = None
            engine.align_p2_idx = None
            engine.add_path_node1 = None
            engine.add_path_node2 = None
            engine.selected_node_pair = []
            engine.selected_edge_idx = None
            if engine.goal_pose_mode != 0:
                engine.goal_pose_mode = 0
                engine.temp_goal = None
                goal_pose_btn.style('background-color: #d1d5db; color: black; min-width: 120px; width: auto; white-space: nowrap; border-radius: 6px;')
            set_sidebar_mode('info')
            update_status('Ready.')

    def update_map_folder(folder):
        if not folder:
            ui.notify("Map folder path is empty.", type='warning')
            return
        try:
            engine.load_map_folder(folder)
            if not engine.maps:
                ui.notify(f"No maps found in: {folder}. (Ensure jueying.yaml & jueying.pgm exist)", type='warning')
                return
            map_input.set_value(folder)
            refresh_floor_buttons()
            refresh_canvas()
            update_status(f"Maps loaded from {os.path.basename(folder)}. Please load Waypoints.")
            ui.notify(f"Maps loaded from {os.path.basename(folder)}", type='positive')
        except Exception as ex:
            print(f"Error loading map folder: {ex}")
            ui.notify(f"Error loading map folder: {ex}", type='negative')

    def reload_waypoints(json_path):
        if not json_path:
            ui.notify("Waypoints JSON path is empty.", type='warning')
            return
        try:
            if engine.load_waypoints_from_file(json_path):
                wp_input.set_value(json_path)
                refresh_floor_buttons()
                refresh_canvas()
                refresh_left_sidebar()
                update_status(f"Loaded {len(engine.path_nodes)} waypoints.")
                ui.notify(f"Loaded {len(engine.path_nodes)} waypoints.", type='positive')
            else:
                ui.notify(f"Failed to load waypoints from {json_path}", type='negative')
        except Exception as ex:
            print(f"Error loading waypoints: {ex}")
            ui.notify(f"Error loading waypoints: {ex}", type='negative')

    def switch_floor(mid):
        if mid == 'ALL':
            engine.show_all_floors = True
            engine.current_map_id = 0
        else:
            engine.show_all_floors = False
            engine.current_map_id = mid
        refresh_floor_buttons()
        engine.precalculate_path_base_maps()
        engine.auto_fit_map_view()
        refresh_canvas(force=True)
        update_status(f"Switched to Floor {'ALL' if getattr(engine, 'show_all_floors', False) else engine.current_map_id + 1}")

    def on_mode_change(mode):
        engine.display_mode = mode
        if engine.maps:
            engine.precalculate_path_base_maps()
            engine.auto_fit_map_view()
            refresh_canvas(force=True)
        update_status(f"Display Mode changed to: {mode}")

    def perform_search(query):
        if not query: return
        query = str(query).strip().lower()
        found_idx = None
        if query.isdigit():
            idx = int(query)
            if 0 <= idx < len(engine.path_nodes): found_idx = idx

        if found_idx is None:
            for i, n in enumerate(engine.path_nodes):
                if query in str(n.get('Node_info', '')).lower():
                    found_idx = i
                    break

        if found_idx is not None:
            engine.selected_wp_idx = found_idx
            update_sidebar_info(found_idx)
            f_mid = engine.path_nodes[found_idx].get('MapID', 0)
            if f_mid in engine.maps and f_mid != engine.current_map_id:
                switch_floor(f_mid)
            else:
                refresh_canvas(force=True)
            update_status(f"Found: {engine.path_nodes[found_idx].get('Node_info')}")
        else:
            update_status(f"Search: '{query}' not found.")

    def toggle_goal_pose_mode():
        if engine.goal_pose_mode == 0:
            engine.goal_pose_mode = 1
            goal_pose_btn.style(replace='background-color: #3a86ff; color: white; min-width: 120px; width: auto; white-space: nowrap; border-radius: 6px;')
            update_status('2D Goal Pose: Step 1 - Click on map to set position.')
        else:
            engine.goal_pose_mode = 0
            engine.temp_goal = None
            goal_pose_btn.style(replace='background-color: #d1d5db; color: black; min-width: 120px; width: auto; white-space: nowrap; border-radius: 6px;')
            update_status('Ready.')
            refresh_canvas()

    def on_map_mouse_event(e):
        # Scale mouse coordinates relative to canvas viewport
        px = e.image_x if e.image_x is not None else 0
        py = e.image_y if e.image_y is not None else 0

        # Calculate map-space coordinates (u_map, v_map) by reversing zoom and offsets
        zoom = engine.view_state['zoom']
        ox = engine.view_state['offset_x']
        oy = engine.view_state['offset_y']
        u_map = (px - ox) / zoom if zoom != 0 else px
        v_map = (py - oy) / zoom if zoom != 0 else py


        # ITEM 4: Left-Click Drag Panning Logic
        if e.type == 'mousedown':
            engine.drag_start_x = px
            engine.drag_start_y = py
            engine.is_dragging = True

            # Handle Edge Selection in Edit Mode or Insert Line Mode
            if (engine.edit_mode == "insert_line" and engine.goal_pose_mode == 0) or (engine.edit_mode == "none" and hasattr(engine, 'edit_controls_visible') and engine.edit_controls_visible):
                edge_idx = engine.get_closest_edge(u_map, v_map, threshold=15 / zoom if zoom != 0 else 15)
                if edge_idx is not None:
                    engine.selected_edge_idx = edge_idx
                    update_status(f"Edge {edge_idx} selected. You can now use InsertPoint2Line.")
                    refresh_canvas(force=True)
                    return

            if engine.goal_pose_mode == 1:
                engine.temp_goal = {'start_u': u_map, 'start_v': v_map, 'current_u': u_map + 20 / (zoom if zoom != 0 else 1), 'current_v': v_map}
                engine.goal_pose_mode = 2
                update_status('2D Goal Pose: Step 2 - Click or drag to set angle.')
                refresh_canvas(force=True)
                return
            elif engine.goal_pose_mode == 2:
                su, sv = engine.temp_goal['start_u'], engine.temp_goal['start_v']
                wx, wy = engine.pixel_to_world(su, sv, engine.current_map_id)
                yaw_screen = -math.atan2(v_map - sv, u_map - su)
                yaw = yaw_screen - engine.get_map_rotation_rad()

                set_sidebar_mode('editor')
                engine.selected_wp_idx = None

                pos_x_in.set_value(round(wx, 4))
                pos_y_in.set_value(round(wy, 4))
                yaw_in.set_value(round(yaw, 4))
                map_id_in.set_value(engine.current_map_id)

                engine.goal_pose_mode = 0
                engine.temp_goal = None
                goal_pose_btn.style(replace='background-color: #d1d5db; color: black; min-width: 120px; width: auto; white-space: nowrap; border-radius: 6px;')
                update_status(f'Pose set at ({wx:.2f}, {wy:.2f}). Fill Node Info and click Save Point.')
                refresh_canvas(force=True)
                return

            # Waypoint click selection
            hit_idx = None
            for i, node in enumerate(engine.path_nodes):
                u, v = engine.world_to_pixel(node['PosX'], node['PosY'], engine.current_map_id)
                if math.hypot(u - u_map, v - v_map) < (25 / (zoom if zoom != 0 else 1)):
                    hit_idx = i
                    break
                    
            # CSV Node click selection
            hit_csv_node = None
            if hit_idx is None:
                for row in engine.node_manager.nodes:
                    if len(row) < 6: continue
                    try:
                        if int(row[5]) != engine.current_map_id and not getattr(engine, 'show_all_floors', False): continue
                        parts = row[3].strip('{}').split(',')
                        x, y = float(parts[0]), float(parts[1])
                        u, v = engine.world_to_pixel(x, y, engine.current_map_id)
                        if math.hypot(u - u_map, v - v_map) < (25 / (zoom if zoom != 0 else 1)):
                            hit_csv_node = row
                            break
                    except Exception:
                        pass

            # CSV Path click selection
            hit_csv_path = None
            if hit_idx is None and hit_csv_node is None:
                node_coords = {}
                for row in engine.node_manager.nodes:
                    if len(row) < 6: continue
                    try:
                        if int(row[5]) == engine.current_map_id or getattr(engine, 'show_all_floors', False):
                            parts = row[3].strip('{}').split(',')
                            node_coords[row[0]] = engine.world_to_pixel(float(parts[0]), float(parts[1]), engine.current_map_id)
                    except Exception:
                        pass
                
                for row in engine.node_manager.paths:
                    if len(row) < 3: continue
                    if row[0] in getattr(engine.node_manager, 'hidden_paths', set()): continue
                    n1, n2 = row[1], row[2]
                    if n1 in node_coords and n2 in node_coords:
                        u1, v1 = node_coords[n1]
                        u2, v2 = node_coords[n2]
                        dist = engine.point_to_line_dist(u_map, v_map, u1, v1, u2, v2)
                        if dist < (15 / (zoom if zoom != 0 else 1)):
                            hit_csv_path = row
                            break

            is_shift = getattr(engine, 'shift_pressed', False)
            if not is_shift and hasattr(e, 'modifiers') and e.modifiers is not None:
                is_shift = ('shift' in e.modifiers) or ('Shift' in e.modifiers)
            if not is_shift and hasattr(e, 'args') and isinstance(e.args, dict):
                is_shift = e.args.get('shiftKey', False)
                
            clicked_node_id = None
            if hit_csv_node is not None:
                clicked_node_id = hit_csv_node[0]
            elif hit_idx is not None:
                clicked_node_id = str(engine.path_nodes[hit_idx].get('Node_info', f'wp_{hit_idx}'))

            if clicked_node_id:
                if is_shift:
                    last_id = getattr(engine, 'last_selected_node_id', None)
                    if last_id and last_id != clicked_node_id:
                        engine.selected_node_pair = [last_id, clicked_node_id]
                        engine.last_selected_node_id = clicked_node_id
                        engine.node_manager.selected_node_id = None
                        update_status(f"Shift Selected Pair: {last_id} -> {clicked_node_id}. Click AddPath to connect.")
                    else:
                        engine.last_selected_node_id = clicked_node_id
                        engine.selected_node_pair = [clicked_node_id]
                        update_status(f"Shift Selected Point 1: [{clicked_node_id}]. Now Shift-click Point 2.")
                    engine.precalculate_path_base_maps()
                else:
                    engine.last_selected_node_id = clicked_node_id
                    engine.selected_node_pair = [clicked_node_id]

            if engine.edit_mode == 'add_path':
                clicked_id = clicked_node_id
                if clicked_id:
                    if getattr(engine, 'add_path_step', 1) == 1:
                        engine.add_path_node1 = clicked_id
                        engine.add_path_step = 2
                        update_status(f"AddPath: Node 1 selected [{clicked_id}]. Click Node 2 (End Node).")
                        refresh_canvas(force=True)
                        return
                    elif engine.add_path_step == 2:
                        push_undo_state()
                        engine.add_path_node2 = clicked_id
                        n1_id = engine.add_path_node1
                        n2_id = engine.add_path_node2
                        
                        p_id = f"path_{len(engine.node_manager.paths)+1}"
                        new_path_row = [p_id, n1_id, n2_id, "1.0", "1", ""]
                        engine.node_manager.paths.append(new_path_row)
                        engine.node_manager.save_paths()
                        
                        engine.precalculate_path_base_maps()
                        refresh_canvas(force=True)
                        refresh_left_sidebar()
                        update_status(f"Added Path [{p_id}]: {n1_id} -> {n2_id}")
                        
                        engine.add_path_step = 1
                        engine.add_path_node1 = None
                        engine.add_path_node2 = None
                        return

            # If in EditPoint mode, first check if user clicked an arrow tip to rotate yaw
            if engine.edit_mode == 'edit_point':
                hit_rotate_json = None
                for i, node in enumerate(engine.path_nodes):
                    val_fix_yaw = node.get('fix_yaw', True)
                    fix_yaw = False if (val_fix_yaw is False or str(val_fix_yaw).lower() in ['0', 'false']) else True
                    if fix_yaw:
                        u, v = engine.world_to_pixel(node['PosX'], node['PosY'], engine.current_map_id)
                        yaw = node.get('AngleYaw', 0) + engine.get_map_rotation_rad()
                        tip_u = u + 15 * math.cos(yaw)
                        tip_v = v - 15 * math.sin(yaw)
                        tip_px = tip_u * zoom + ox
                        tip_py = tip_v * zoom + oy
                        if math.hypot(tip_px - px, tip_py - py) < 25:
                            hit_rotate_json = i
                            break

                if hit_rotate_json is not None:
                    push_undo_state()
                    engine.dragging_node_type = 'rotate_json'
                    engine.dragging_node_target = hit_rotate_json
                    engine.selected_wp_idx = hit_rotate_json
                    update_sidebar_info(hit_rotate_json)
                    update_status(f"Rotating Waypoint [{hit_rotate_json}]... Drag mouse to rotate yaw angle.")
                    return

                hit_rotate_csv = None
                for row in engine.node_manager.nodes:
                    if len(row) < 6: continue
                    fix_yaw_raw = row[7] if len(row) > 7 else "1"
                    fix_yaw = False if str(fix_yaw_raw).lower() in ['0', 'false'] else True
                    if fix_yaw:
                        try:
                            if int(row[5]) != engine.current_map_id and not getattr(engine, 'show_all_floors', False): continue
                            parts = row[3].strip('{}').split(',')
                            x, y, yaw = float(parts[0]), float(parts[1]), float(parts[3])
                            u, v = engine.world_to_pixel(x, y, engine.current_map_id)
                            rot_yaw = yaw + engine.get_map_rotation_rad()
                            tip_u = u + 15 * math.cos(rot_yaw)
                            tip_v = v - 15 * math.sin(rot_yaw)
                            tip_px = tip_u * zoom + ox
                            tip_py = tip_v * zoom + oy
                            if math.hypot(tip_px - px, tip_py - py) < 25:
                                hit_rotate_csv = row[0]
                                break
                        except Exception:
                            pass

                if hit_rotate_csv is not None:
                    push_undo_state()
                    engine.dragging_node_type = 'rotate_csv'
                    engine.dragging_node_target = hit_rotate_csv
                    engine.node_manager.selected_node_id = hit_rotate_csv
                    select_csv_node_by_id(hit_rotate_csv)
                    update_status(f"Rotating CSV Node [{hit_rotate_csv}]... Drag mouse to rotate yaw angle.")
                    return

                # If not rotating arrow tip, check node center for drag position
                if hit_idx is not None:
                    push_undo_state()
                    engine.dragging_node_type = 'json'
                    engine.dragging_node_target = hit_idx
                    engine.selected_wp_idx = hit_idx
                    update_sidebar_info(hit_idx)
                    update_status(f"Dragging Waypoint [{hit_idx}]... Drag to new position.")
                elif hit_csv_node is not None:
                    push_undo_state()
                    engine.dragging_node_type = 'csv'
                    engine.dragging_node_target = hit_csv_node[0]
                    engine.node_manager.selected_node_id = hit_csv_node[0]
                    select_csv_node_by_id(hit_csv_node[0])
                    update_status(f"Dragging CSV Node [{hit_csv_node[0]}]... Drag to new position.")

            if hit_idx is not None:
                if engine.edit_mode == 'align_yaw':
                    if getattr(engine, 'align_step', 1) == 1:
                        engine.align_p1_idx = hit_idx
                        engine.align_step = 2
                        update_status(f"AlignYaw: Point 1 selected [{hit_idx}]. Click Point 2 to align to.")
                        refresh_canvas(force=True)
                        return
                    elif engine.align_step == 2:
                        push_undo_state()
                        engine.align_p2_idx = hit_idx
                        p1 = engine.path_nodes[engine.align_p1_idx]
                        p2 = engine.path_nodes[hit_idx]
                        yaw = math.atan2(p2['PosY'] - p1['PosY'], p2['PosX'] - p1['PosX'])
                        p1['AngleYaw'] = float(yaw)
                        
                        update_status(f"AlignYaw: Updated Point [{engine.align_p1_idx}] yaw to {yaw:.2f} rad. Saving...")
                        
                        json_file = engine.waypoints_file
                        if json_file:
                            with open(json_file, 'w') as f:
                                json.dump(engine.path_nodes, f, indent=4)
                        
                        if engine.selected_wp_idx == engine.align_p1_idx:
                            yaw_in.set_value(round(yaw, 4))
                            
                        engine.precalculate_path_base_maps()
                        
                        # Keep align_p1_idx and align_p2_idx visible for context
                        # Reset align_step so next click starts a new alignment pair
                        engine.align_step = 1
                        refresh_canvas(force=True)
                        return

                engine.selected_wp_idx = hit_idx
                if getattr(engine.node_manager, 'selected_node_id', None) is not None:
                    engine.node_manager._handle_node_click(None, None, handle_sidebar_item_update)
                update_sidebar_info(hit_idx)
                refresh_canvas(force=True)
                update_status(f"Selected Waypoint [{hit_idx}]: {engine.path_nodes[hit_idx].get('Node_info')}")
                
            elif hit_csv_node is not None:
                n_id = hit_csv_node[0]
                if is_shift and len(getattr(engine, 'selected_node_pair', [])) == 2:
                    select_csv_node_by_id(n_id)
                    engine.node_manager.selected_node_id = None
                    engine.precalculate_path_base_maps()
                    refresh_canvas(force=True)
                else:
                    engine.node_manager._handle_node_click(None, n_id, handle_sidebar_item_update)
                    select_csv_node_by_id(n_id)
                    refresh_canvas(force=True)
                
            elif hit_csv_path is not None:
                p_id = hit_csv_path[0]
                engine.node_manager._handle_path_click(None, p_id, handle_sidebar_item_update)
                select_csv_path_by_id(p_id)
                refresh_canvas(force=True)
            else:
                # Clicked empty space on map: deselect all nodes and paths
                engine.selected_wp_idx = None
                if hasattr(engine, 'node_manager'):
                    engine.node_manager.selected_node_id = None
                    engine.node_manager.selected_path_id = None
                engine.selected_node_pair = []
                engine.last_selected_node_id = None
                engine.align_p1_idx = None
                engine.align_p2_idx = None
                engine.selected_edge_idx = None

                set_sidebar_mode('info')
                engine.precalculate_path_base_maps()
                refresh_canvas(force=True)
                update_status('Ready (Deselected all).')

        elif e.type == 'mousemove':
            # Live arrow updates in Goal Pose mode 2
            if engine.goal_pose_mode == 2:
                engine.temp_goal['current_u'] = u_map
                engine.temp_goal['current_v'] = v_map
                refresh_canvas()
            # Live yaw angle rotation in EditPoint mode (dragging arrow tip)
            elif getattr(engine, 'is_dragging', False) and engine.edit_mode == 'edit_point' and (getattr(engine, 'dragging_node_type', '') or '').startswith('rotate_'):
                if engine.dragging_node_type == 'rotate_json':
                    idx = engine.dragging_node_target
                    if 0 <= idx < len(engine.path_nodes):
                        node = engine.path_nodes[idx]
                        u, v = engine.world_to_pixel(node['PosX'], node['PosY'], engine.current_map_id)
                        yaw_screen = -math.atan2(v_map - v, u_map - u)
                        new_yaw = yaw_screen - engine.get_map_rotation_rad()
                        node['AngleYaw'] = float(new_yaw)
                        refresh_canvas()
                elif engine.dragging_node_type == 'rotate_csv':
                    nid = engine.dragging_node_target
                    row = engine.node_manager.get_node_by_id(nid)
                    if row and len(row) > 3:
                        parts = row[3].strip('{}').split(',')
                        x, y = float(parts[0]), float(parts[1])
                        z = parts[2] if len(parts) > 2 else "0"
                        u, v = engine.world_to_pixel(x, y, engine.current_map_id)
                        yaw_screen = -math.atan2(v_map - v, u_map - u)
                        new_yaw = yaw_screen - engine.get_map_rotation_rad()
                        row[3] = f"{{{x:.4f},{y:.4f},{z},{new_yaw:.4f}}}"
                        refresh_canvas()
            # Live point position dragging in EditPoint mode
            elif getattr(engine, 'is_dragging', False) and engine.edit_mode == 'edit_point' and getattr(engine, 'dragging_node_target', None) is not None:
                wx, wy = engine.pixel_to_world(u_map, v_map, engine.current_map_id)
                if engine.dragging_node_type == 'json':
                    idx = engine.dragging_node_target
                    if 0 <= idx < len(engine.path_nodes):
                        engine.path_nodes[idx]['PosX'] = float(wx)
                        engine.path_nodes[idx]['PosY'] = float(wy)
                        refresh_canvas()
                elif engine.dragging_node_type == 'csv':
                    nid = engine.dragging_node_target
                    row = engine.node_manager.get_node_by_id(nid)
                    if row and len(row) > 3:
                        parts = row[3].strip('{}').split(',')
                        z = parts[2] if len(parts) > 2 else "0"
                        yaw = parts[3] if len(parts) > 3 else "0"
                        row[3] = f"{{{wx:.4f},{wy:.4f},{z},{yaw}}}"
                        refresh_canvas()
            # Drag Map to Pan (if not dragging a node and not setting 2D goal pose)
            elif getattr(engine, 'is_dragging', False) and engine.goal_pose_mode == 0:
                dx = px - engine.drag_start_x
                dy = py - engine.drag_start_y
                engine.view_state['offset_x'] += dx
                engine.view_state['offset_y'] += dy
                engine.drag_start_x = px
                engine.drag_start_y = py
                refresh_canvas()

        elif e.type == 'mouseup':
            if engine.edit_mode == 'edit_point' and getattr(engine, 'dragging_node_target', None) is not None:
                dtype = getattr(engine, 'dragging_node_type', '') or ''
                if dtype in ['json', 'rotate_json']:
                    json_file = engine.waypoints_file
                    if json_file and os.path.exists(json_file):
                        with open(json_file, 'w') as f:
                            json.dump(engine.path_nodes, f, indent=4)
                    update_status(f"Point updated and saved to waypoints file.")
                    if engine.selected_wp_idx is not None:
                        update_sidebar_info(engine.selected_wp_idx)
                elif dtype in ['csv', 'rotate_csv']:
                    engine.node_manager.save_nodes()
                    update_status(f"CSV Node updated and saved to nodes.csv.")
                    if engine.node_manager.selected_node_id:
                        select_csv_node_by_id(engine.node_manager.selected_node_id)
                engine.precalculate_path_base_maps()
                engine.dragging_node_target = None
                engine.dragging_node_type = None
            engine.is_dragging = False
            refresh_canvas(force=True)

    # =========================================================================
    # Async Simulation Engine Loop matching simulate_path_back.py logic
    # =========================================================================

    async def run_simulation_step():
        if not engine.sim_running or engine.sim_paused or engine.sim_stop_flag:
            return

        visible_indices = [idx for idx, n in enumerate(engine.path_nodes) if not n.get('_hidden')]
        
        if engine.sim_step_index not in visible_indices:
            next_visible = [idx for idx in visible_indices if idx >= engine.sim_step_index]
            if not next_visible:
                engine.sim_step_index = len(engine.path_nodes)
            else:
                engine.sim_step_index = next_visible[0]

        if not visible_indices or visible_indices.index(engine.sim_step_index) >= len(visible_indices) - 1:
            engine.sim_running = False
            start_btn.enable()
            pause_btn.disable()
            stop_btn.disable()
            map_input.enable()
            folder_load_btn.enable()
            wp_input.enable()
            wp_reload_btn.enable()
            sim_nav_btn.enable()
            update_status('Finished.')
            return

        current_vis_idx = visible_indices.index(engine.sim_step_index)
        i = visible_indices[current_vis_idx]
        next_i = visible_indices[current_vis_idx + 1]

        p1, p2 = engine.path_nodes[i], engine.path_nodes[next_i]
        m1, m2 = p1.get('MapID', 0), p2.get('MapID', 0)

        if m1 != engine.current_map_id:
            engine.current_map_id = m1
            refresh_floor_buttons()

        u1, v1 = engine.world_to_pixel(p1['PosX'], p1['PosY'], m1)
        u2, v2 = engine.world_to_pixel(p2['PosX'], p2['PosY'], m1 if m1 != m2 else m2)

        # Move robot position smoothly based on physics
        # 1 pixel = resolution in meters. So distance in meters = dist_pixels * res
        # v = 1 m/s -> pixels/sec = 1 / res
        res = engine.maps[m1]['resolution'] if m1 in engine.maps else 0.05
        pixels_per_sec = max(engine.sim_speed, 0.1) / res
        dist_per_tick = pixels_per_sec * 0.05 # 20 FPS

        dx, dy = u2 - u1, v2 - v1
        total_dist = math.hypot(dx, dy)
        yaw = math.atan2(-dy, dx)
        
        if total_dist == 0 or engine.sim_progress_dist + dist_per_tick >= total_dist:
            # Reached next point
            engine.robot_pose = {'u': u2, 'v': v2, 'yaw': yaw, 'step': next_i}
            engine.sim_step_index = next_i
            engine.sim_progress_dist = 0.0
            update_sidebar_info(next_i)
            if m1 != m2:
                update_status(f"Transitioning to Floor {m2+1}...")
                engine.current_map_id = m2
                refresh_floor_buttons()
        else:
            engine.sim_progress_dist += dist_per_tick
            ratio = engine.sim_progress_dist / total_dist
            cu = u1 + dx * ratio
            cv = v1 + dy * ratio
            engine.robot_pose = {'u': cu, 'v': cv, 'yaw': yaw, 'step': i}

        update_status(f"State: Moving | Path: {p1.get('Node_info')} -> {p2.get('Node_info')}")

    sim_timer = ui.timer(0.05, run_simulation_step, active=True)

    def start_simulation():
        if not engine.path_nodes:
            ui.notify('No waypoints loaded to simulate.', type='warning')
            return
        engine.sim_running = True
        engine.sim_paused = False
        engine.sim_stop_flag = False
        engine.sim_step_index = 0
        engine.sim_progress_dist = 0.0
        p0 = engine.path_nodes[0]
        u0, v0 = engine.world_to_pixel(p0['PosX'], p0['PosY'], p0.get('MapID', 0))
        engine.robot_pose = {'u': u0, 'v': v0, 'yaw': p0.get('AngleYaw', 0), 'step': 0}
        
        start_btn.disable()
        pause_btn.enable()
        stop_btn.enable()
        map_input.disable()
        folder_load_btn.disable()
        wp_input.disable()
        wp_reload_btn.disable()
        sim_nav_btn.disable()
        update_status('Starting...')

    def toggle_pause():
        if engine.sim_running:
            engine.sim_paused = not engine.sim_paused
            pause_btn.set_text('Play' if engine.sim_paused else 'Pause')
            update_status('Paused.' if engine.sim_paused else 'Running...')

    def stop_simulation():
        engine.sim_running = False
        engine.sim_stop_flag = True
        engine.robot_pose = None
        start_btn.enable()
        pause_btn.disable()
        stop_btn.disable()
        map_input.enable()
        folder_load_btn.enable()
        wp_input.enable()
        wp_reload_btn.enable()
        sim_nav_btn.enable()
        update_status('Stopped.')

    refresh_left_sidebar()

# =============================================================================
# CLI / Main Entry Point
# =============================================================================

def run_headless_simulation(args):
    """Executes headless simulation loop in background without GUI."""
    print("Running headless simulation...")
    engine.map_folder = args.map_folder
    engine.waypoints_file = args.waypoints
    engine.sim_speed = args.speed

    if args.map_folder and os.path.exists(args.map_folder):
        engine.load_map_folder(args.map_folder)
    if args.waypoints and os.path.exists(args.waypoints):
        engine.load_waypoints_from_file(args.waypoints)

    if not engine.path_nodes:
        print("Error: No waypoints loaded for headless simulation.")
        return

    print(f"Simulating {len(engine.path_nodes)} waypoints in headless mode...")
    for i in range(len(engine.path_nodes) - 1):
        p1, p2 = engine.path_nodes[i], engine.path_nodes[i+1]
        print(f"Step [{i+1}/{len(engine.path_nodes)-1}]: {p1.get('Node_info')} -> {p2.get('Node_info')}")
        time.sleep(0.05)
    print("Headless simulation complete.")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_map = os.path.normpath(os.path.join(script_dir, '../resource/maps/map1-nestle'))
    if not os.path.exists(default_map):
        default_map = os.path.normpath(os.path.join(script_dir, '../resource/maps/Nestle-full'))

    default_waypoints = os.path.normpath(os.path.join(script_dir, '../resource/waypoints/final_packing.json'))

    parser = argparse.ArgumentParser(description="X30 GS Path Simulator (NiceGUI)")
    parser.add_argument('--waypoints', type=str, default=default_waypoints, help='Path to JSON file')
    parser.add_argument('--speed', type=int, default=5)
    parser.add_argument('--map_folder', type=str, default=default_map, help='Folder containing map files')
    parser.add_argument('--port', type=int, default=8080, help='Port to run NiceGUI server')
    parser.add_argument('--headless', action='store_true', help='Run headless mode without GUI')
    args = parser.parse_args()

    if args.headless:
        run_headless_simulation(args)
    else:
        engine.map_folder = args.map_folder
        engine.waypoints_file = args.waypoints
        engine.sim_speed = args.speed

        if args.map_folder and os.path.exists(args.map_folder):
            engine.load_map_folder(args.map_folder)
        if args.waypoints and os.path.exists(args.waypoints):
            engine.load_waypoints_from_file(args.waypoints)

        create_nicegui_app()
        print(f"Starting X30 GS Simulator (NiceGUI Web App) on http://localhost:{args.port}")
        ui.run(port=args.port, title="X30 GS Path Simulator", reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()