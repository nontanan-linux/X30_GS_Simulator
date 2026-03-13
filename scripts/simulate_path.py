import json
import yaml
import cv2
import numpy as np
import argparse
import os
import math
import time
import threading

try:
    import customtkinter as ctk
    from PIL import Image, ImageTk
    import tkinter as tk
    from tkinter import filedialog, ttk
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

class SimulationApp(ctk.CTk if HAS_GUI else object):
    def __init__(self, args):
        self.args = args
        self.app_quit_flag = False
        self.sim_stop_flag = False
        self.is_paused = False
        self.sim_thread = None
        self.out = None
        self.selected_wp_idx = None
        self.goal_pose_mode = 0  # 0: Off, 1: Select Pos, 2: Select Yaw
        self.temp_goal = None  # {start_u, start_v, current_u, current_v}

        # Load robot config
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.robot_config = {'length_m': 1.0, 'width_m': 0.46}
        config_path = os.path.join(script_dir, '../config/robot_config.yaml')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    cfg = yaml.safe_load(f)
                    if cfg and 'robot' in cfg:
                        self.robot_config.update(cfg['robot'])
            except Exception as e:
                print(f"Error loading robot config: {e}")

        # Load robot image
        robot_img_rel = self.robot_config.get('image_path', '../resource/gs_cat_robot.png')
        robot_img_path = os.path.normpath(os.path.join(script_dir, robot_img_rel))
        if os.path.exists(robot_img_path):
            self.robot_img_raw = cv2.imread(robot_img_path, cv2.IMREAD_UNCHANGED)
        else:
            print(f"Warning: Robot image {robot_img_path} not found.")
            self.robot_img_raw = None
        
        if HAS_GUI and not args.headless:
            super().__init__()
            ctk.set_appearance_mode("Dark")
            self.title("Robot Path Simulation")
            
            # Set window icon
            try:
                icon_rel = self.robot_config.get('icon_path', '../resource/gs_cat_robot.png')
                icon_path = os.path.normpath(os.path.join(script_dir, icon_rel))
                if os.path.exists(icon_path):
                    pil_icon = Image.open(icon_path)
                    # Resize to a standard icon size to prevent X11 BadLength error
                    pil_icon = pil_icon.resize((64, 64), Image.LANCZOS)
                    self.gui_icon = ImageTk.PhotoImage(pil_icon)
                    self.iconphoto(False, self.gui_icon)
            except Exception as e:
                print(f"Warning: Could not set window icon: {e}")
            
            # Start large screen
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            self.window_w = sw - 100
            self.window_h = sh - 100
            self.geometry(f"{self.window_w}x{self.window_h}+50+50")
            self.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            self.setup_ui()
            self.bind_events()
        
        # View state
        self.view_state = {
            'zoom': 1.0,
            'offset_x': 0,
            'offset_y': 0,
            'dragging': False,
            'drag_start_x': 0,
            'drag_start_y': 0,
            'default_zoom': 1.0,
            'default_offset_x': 0,
            'default_offset_y': 0,
            'follow_robot': True
        }
        
        self.maps = {} # type: dict[int, dict]
        self.current_map_id = 0
        self.path_nodes = []
        self.base_maps = {}  # Initialize base_maps here to prevent AttributeError
        
        # Load Splash Image
        splash_path = os.path.join(script_dir, '../resource/maps/picture/edit/Nestle_layout_00.png')
        if os.path.exists(splash_path):
            self.splash_img = cv2.imread(splash_path, cv2.IMREAD_COLOR)
        else:
            self.splash_img = np.zeros((800, 1200, 3), dtype=np.uint8)
        
        if not args.headless:
            # Do NOT auto-load map and waypoints for GUI mode, just render splash
            self.last_frame = self.splash_img
            if HAS_GUI:
                self.after(100, self.render_splash_screen)
            
        else:
            self.load_map_folder(args.map_folder)
            if args.waypoints and os.path.exists(args.waypoints):
                self.load_waypoints_from_file(args.waypoints)
                self.run_simulation_loop(0)
            else:
                print("Error: No waypoints file specified for headless mode.")

    def setup_ui(self):
        # Top panel for controls
        self.control_frame = ctk.CTkFrame(self, height=140)
        self.control_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        # Row 1: Map Folder
        self.map_row = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        self.map_row.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(self.map_row, text="Map Dir:").pack(side="left", padx=5)
        self.folder_var = ctk.StringVar(value=self.args.map_folder)
        self.folder_entry = ctk.CTkEntry(self.map_row, textvariable=self.folder_var, width=250)
        self.folder_entry.pack(side="left", padx=5)
        self.folder_browse_btn = ctk.CTkButton(self.map_row, text="Browse...", width=80, command=self.browse_folder)
        self.folder_browse_btn.pack(side="left", padx=5)
        self.folder_load_btn = ctk.CTkButton(self.map_row, text="Update Map", width=80, command=self.on_folder_change)
        self.folder_load_btn.pack(side="left", padx=5)

        # Row 2: Waypoints
        self.wp_row = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        self.wp_row.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(self.wp_row, text="Waypoints File:").pack(side="left", padx=5)
        self.json_path_var = ctk.StringVar(value="")
        self.wp_entry = ctk.CTkEntry(self.wp_row, textvariable=self.json_path_var, width=250)
        self.wp_entry.pack(side="left", padx=5)
        self.wp_browse_btn = ctk.CTkButton(self.wp_row, text="Select JSON...", width=100, command=self.browse_json)
        self.wp_browse_btn.pack(side="left", padx=5)
        self.wp_reload_btn = ctk.CTkButton(self.wp_row, text="Reload", width=60, command=self.reload_waypoints)
        self.wp_reload_btn.pack(side="left", padx=5)
        
        self.wp_var = ctk.StringVar(value="Start from WP")
        self.wp_menu = ctk.CTkOptionMenu(self.wp_row, values=["No waypoints loaded"], variable=self.wp_var, width=200)
        self.wp_menu.pack(side="left", padx=5)
        
        # Row 3: Simulation Controls
        self.sim_row = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        self.sim_row.pack(fill="x", padx=10, pady=5)

        self.start_btn = ctk.CTkButton(self.sim_row, text="Start", fg_color="green", hover_color="darkgreen", command=self.start_simulation, width=60)
        self.start_btn.pack(side="left", padx=5)
        
        self.play_pause_btn = ctk.CTkButton(self.sim_row, text="Pause", command=self.toggle_pause, state="disabled", width=60)
        self.play_pause_btn.pack(side="left", padx=5)
        
        self.stop_btn = ctk.CTkButton(self.sim_row, text="Stop", fg_color="red", hover_color="darkred", command=self.stop_simulation, state="disabled", width=60)
        self.stop_btn.pack(side="left", padx=5)
        
        self.reset_view_btn = ctk.CTkButton(self.sim_row, text="Reset View", command=self.reset_view, width=80)
        self.reset_view_btn.pack(side="left", padx=5)
        
        self.goal_pose_btn = ctk.CTkButton(self.sim_row, text="2D Goal Pose", command=self.toggle_goal_pose_mode, width=100, fg_color="gray70", text_color="black")
        self.goal_pose_btn.pack(side="left", padx=5)
        
        self.follow_var = ctk.BooleanVar(value=True)
        self.follow_cb = ctk.CTkCheckBox(self.sim_row, text="Follow Robot", variable=self.follow_var, command=self.on_follow_toggle, state="disabled")
        self.follow_cb.pack(side="left", padx=10)
        
        self.status_label = ctk.CTkLabel(self.sim_row, text="Ready. Please load a Map Directory and a Waypoints JSON.")
        self.status_label.pack(side="left", padx=15)
        
        self.toggle_sidebar_btn = ctk.CTkButton(self.sim_row, text="Sidebar >", width=80, command=self.toggle_sidebar)
        self.toggle_sidebar_btn.pack(side="right", padx=5)
        self.sidebar_visible = True
        
        # Main container for Canvas and Sidebar
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Use PanedWindow for resizable sidebar
        self.paned_window = ttk.PanedWindow(self.main_container, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill="both", expand=True)
        
        # Canvas for map
        self.canvas_frame = ctk.CTkFrame(self.paned_window, fg_color="transparent")
        self.canvas = ctk.CTkCanvas(self.canvas_frame, bg="black", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.paned_window.add(self.canvas_frame, weight=1)
        
        # Sidebar for info
        self.sidebar = ctk.CTkFrame(self.paned_window, width=450)
        self.sidebar.pack_propagate(False)
        self.paned_window.add(self.sidebar, weight=0)
        
        ctk.CTkLabel(self.sidebar, text="Waypoint Information", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        # Search row
        self.search_row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.search_row.pack(fill="x", padx=10, pady=5)
        
        self.search_entry = ctk.CTkEntry(self.search_row, placeholder_text="Name or Index...", width=180)
        self.search_entry.pack(side="left", padx=(0, 5))
        self.search_entry.bind("<Return>", lambda e: self.perform_search())
        
        self.search_btn = ctk.CTkButton(self.search_row, text="Search", width=60, command=self.perform_search)
        self.search_btn.pack(side="left")
        
        self.info_text = ctk.CTkTextbox(self.sidebar, width=280, height=250)
        self.info_text.pack(padx=10, pady=5, fill="both", expand=True)
        self.info_text.configure(state="disabled")
        
        self.info_label = ctk.CTkLabel(self.sidebar, text="Click a waypoint to see details.", wraplength=250)
        self.info_label.pack(pady=5, padx=10)
        
        # Label to show inspection image
        self.image_label = ctk.CTkLabel(self.sidebar, text="")
        self.image_label.pack(pady=5, padx=10, fill="both", expand=False)

    def update_sidebar(self, idx):
        if idx is None or idx >= len(self.path_nodes):
            self.info_text.configure(state="normal")
            self.info_text.delete("1.0", "end")
            self.info_text.configure(state="disabled")
            self.info_label.configure(text="No waypoint selected.")
            return

        current_node = self.path_nodes[idx]
        
        # Build info text
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        
        # --- Previous Waypoint ---
        self.info_text.insert("end", "=== PREVIOUS WAYPOINT ===\n", "header")
        if idx > 0:
            prev = self.path_nodes[idx-1]
            p_name = prev.get('Node_info', 'N/A')
            p_info = (f"Name: {p_name}\n"
                      f"X: {prev.get('PosX'):.2f} | Y: {prev.get('PosY'):.2f}\n"
                      f"Yaw: {prev.get('AngleYaw', 0):.2f}\n"
                      f"MapID: {prev.get('MapID', 0)} | Posture: {prev.get('Posture', 'N/A')}\n\n")
            self.info_text.insert("end", p_info)
        else:
            self.info_text.insert("end", "None (Start node)\n\n")

        # --- Current Waypoint (Full JSON) ---
        self.info_text.insert("end", "=== CURRENT WAYPOINT ===\n", "header")
        self.info_text.insert("end", json.dumps(current_node, indent=2) + "\n\n")
        
        # --- Next Waypoint ---
        self.info_text.insert("end", "=== NEXT WAYPOINT ===\n", "header")
        if idx < len(self.path_nodes) - 1:
            nxt = self.path_nodes[idx+1]
            n_name = nxt.get('Node_info', 'N/A')
            n_info = (f"Name: {n_name}\n"
                      f"X: {nxt.get('PosX'):.2f} | Y: {nxt.get('PosY'):.2f}\n"
                      f"Yaw: {nxt.get('AngleYaw', 0):.2f}\n"
                      f"MapID: {nxt.get('MapID', 0)} | Posture: {nxt.get('Posture', 'N/A')}\n")
            self.info_text.insert("end", n_info)
        else:
            self.info_text.insert("end", "None (End node)\n")

        self.info_text.tag_config("header", foreground="#3a86ff") # Blue color for headers
        self.info_text.configure(state="disabled")
        
        info = f"Index: {idx}\nName: {current_node.get('Node_info')}\nFloor: {current_node.get('MapID',0)+1}"
        self.info_label.configure(text=info)
        
        # Load and display inspection image if available
        self.image_label.configure(image="", text="") # Clear previous
        
        node_info = current_node.get('Node_info', '')
        if node_info and isinstance(node_info, str):
            # Look for matching file in resource/maps/picture
            pic_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../resource/maps/picture')
            matched_file = None
            if os.path.exists(pic_dir):
                for f in os.listdir(pic_dir):
                    if f.lower().endswith(('.png', '.jpg', '.jpeg')) and node_info.lower() in f.lower():
                        matched_file = os.path.join(pic_dir, f)
                        break
            
            if matched_file:
                try:
                    pil_img = Image.open(matched_file)
                    # Resize to fit sidebar (width ~400)
                    basewidth = 400
                    wpercent = (basewidth / float(pil_img.size[0]))
                    hsize = int((float(pil_img.size[1]) * float(wpercent)))
                    pil_img = pil_img.resize((basewidth, hsize), Image.Resampling.LANCZOS)
                    
                    img_tk = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(basewidth, hsize))
                    self.image_label.configure(image=img_tk, text="")
                    self.image_label.image = img_tk  # keep reference
                except Exception as e:
                    print(f"Error loading image {matched_file}: {e}")
                    self.image_label.configure(text="Error loading image.")
            else:
                self.image_label.configure(text="")
        else:
            self.image_label.configure(text="")

    def clear_sidebar_image(self):
        if hasattr(self, 'image_label'):
            self.image_label.configure(image="", text="")

    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.paned_window.forget(self.sidebar)
            self.toggle_sidebar_btn.configure(text="< Sidebar")
            self.sidebar_visible = False
        else:
            self.paned_window.add(self.sidebar, weight=0)
            self.toggle_sidebar_btn.configure(text="Sidebar >")
            self.sidebar_visible = True

    def toggle_goal_pose_mode(self):
        if self.goal_pose_mode == 0:
            self.goal_pose_mode = 1
            self.goal_pose_btn.configure(fg_color="#3a86ff", text_color="white")
            self.status_label.configure(text="2D Goal Pose: Step 1 - Click on map to set position.")
        else:
            self.goal_pose_mode = 0
            self.temp_goal = None
            self.goal_pose_btn.configure(fg_color="gray70", text_color="black")
            self.status_label.configure(text="Ready.")
            if hasattr(self, 'last_frame'):
                self.update_canvas(self.last_frame)

    def perform_search(self):
        query = self.search_entry.get().strip().lower()
        if not query: return
        
        found_idx = None
        # Try index first
        if query.isdigit():
            idx = int(query)
            if 0 <= idx < len(self.path_nodes):
                found_idx = idx
        
        # Try name search if not found by index
        if found_idx is None:
            for i, node in enumerate(self.path_nodes):
                name = str(node.get('Node_info', '')).lower()
                if query in name:
                    found_idx = i
                    break
        
        if found_idx is not None:
            self.selected_wp_idx = found_idx
            self.update_sidebar(found_idx)
            
            # Switch map if needed
            found_mid = self.path_nodes[found_idx].get('MapID', 0)
            if found_mid != self.current_map_id:
                self.switch_to_map(found_mid)
            
            # Re-render to show highlight
            if hasattr(self, 'last_frame'):
                self.update_canvas(self.last_frame)
            
            # Set focus back to search or map? 
            # Letting it be for now.
            self.status_label.configure(text=f"Found: {self.path_nodes[found_idx].get('Node_info')}")
        else:
            self.status_label.configure(text=f"Search: '{query}' not found.")

    def on_follow_toggle(self):
        self.view_state['follow_robot'] = self.follow_var.get()
        if hasattr(self, 'last_frame'):
            self.update_canvas(self.last_frame)

    def bind_events(self):
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<B1-Motion>", self.on_mouse_move)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        
        # Windows/Linux mouse wheel
        self.canvas.bind("<Button-4>", self.on_mouse_wheel) 
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel) 
        
        self.bind("<KeyPress>", self.on_key_press)

    def load_map_folder(self, folder):
        print(f"Loading map folder: {folder}")
        self.maps = {}
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Determine based on single image or multifloor
        if folder == '' or 'Nestle-full' in folder:
            try:
                yaml_path = os.path.join(script_dir, '../resource/maps/Nestle-full.yaml')
                with open(yaml_path, 'r') as f: config = yaml.safe_load(f)
                img_path = os.path.join(script_dir, '../resource/maps/picture/edit/Nestle-full-edit02.pgm')
                if not os.path.exists(img_path):
                    img_path = os.path.join(script_dir, '../resource/maps/Nestle-full.pgm')
                img = cv2.imread(img_path, cv2.IMREAD_COLOR)
                self.maps[0] = {
                    'image': img,
                    'resolution': config['resolution'],
                    'origin': config['origin'],
                    'height': img.shape[0],
                    'width': img.shape[1]
                }
            except Exception as e:
                print("Failed to load default map:", e)
        else:
            # Multifloor logic: MapID 0 -> jueying, MapID 1 -> jueying2, MapID 2 -> jueying3
            # In your data, sometimes MapID == 2 for floor 2...
            # A common map is MapID 0 = 1st floor, MapID 1 = 2nd floor, MapID 2 = 3rd floor
            # Let's map 0 -> jueying, 1 -> jueying2, 2 -> jueying3, and ALSO handle fallback if they used 2 for floor 2.
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
                            'width': img.shape[1]
                        }
                    except Exception as e:
                        print(f"Error loading {yaml_path}: {e}")

            # Special case for NestleCat points which use MapID=2 for 2nd floor 
            # (wet_zone_12-2.json uses MapID: 2 for 2nd floor, so if 1 doesn't exist but 2 does, that's fine,
            # but if jueying2 is floor 2, we might want to map both ID 1 and 2 to jueying2.pgm just in case)
            if 1 in self.maps and 2 not in self.maps:
                self.maps[2] = self.maps[1]
                
        if not self.maps:
            print("No valid maps found!")
            if HAS_GUI and not self.args.headless and hasattr(self, 'status_label'): 
                self.status_label.configure(text=f"Error loading maps from {folder}")
            return
            
        self.current_map_id = 0 if 0 in self.maps else list(self.maps.keys())[0]
        if HAS_GUI and not self.args.headless:
            self.status_label.configure(text=f"Maps loaded from {os.path.basename(folder)}. Please load Waypoints.")

    def on_folder_change(self):
        folder = self.folder_var.get()
        if self.sim_thread and self.sim_thread.is_alive():
            self.stop_simulation()
        self.load_map_folder(folder)
        if hasattr(self, 'json_path_var') and getattr(self, 'json_path_var').get() and self.maps:
            self.load_waypoints_from_file(self.json_path_var.get())
        elif self.maps:
            self.switch_to_map(self.current_map_id)
            self.render_initial_map()

    def world_to_pixel(self, x, y, map_id):
        m = self.maps[map_id]
        res = m['resolution']
        ox, oy = m['origin'][:2]
        u = (x - ox) / res
        v = m['height'] - (y - oy) / res
        return u, v

    def pixel_to_world(self, u, v, map_id):
        m = self.maps[map_id]
        res = m['resolution']
        ox, oy = m['origin'][:2]
        x = u * res + ox
        y = (m['height'] - v) * res + oy
        return x, y

    def precalculate_path_base_maps(self):
        # We need a base map pre-drawn for each map layer
        self.base_maps = {}
        
        # Color palette for floors (BGR)
        # Floor 0: Blue/Orange, Floor 1: Green/Yellow, Floor 2: Red/Cyan, Floor 3+: Purple/Gray
        floor_colors = [
            [(250, 206, 135), (0, 165, 255)],  # Flr 1: Via (Light Blue), Inspect (Orange)
            [(150, 255, 150), (0, 200, 0)],    # Flr 2: Via (Light Green), Inspect (Green)
            [(200, 200, 255), (0, 0, 255)],    # Flr 3: Via (Pink), Inspect (Red)
            [(255, 200, 255), (200, 0, 200)],  # Flr 4: Via (Light Purple), Inspect (Purple)
        ]

        for mid, m in self.maps.items():
            b_map = m['image'].copy()
            
            # Draw lines and points for ALL floors
            for i in range(len(self.path_nodes)-1):
                p1 = self.path_nodes[i]
                p2 = self.path_nodes[i+1]
                m1 = p1.get('MapID', 0)
                m2 = p2.get('MapID', 0)
                
                # Draw lines ONLY if both points are on the current displayed floor mid
                if m1 == mid and m2 == mid:
                    u1, v1 = self.world_to_pixel(p1['PosX'], p1['PosY'], mid)
                    u2, v2 = self.world_to_pixel(p2['PosX'], p2['PosY'], mid)
                    cv2.line(b_map, (int(u1), int(v1)), (int(u2), int(v2)), (200, 200, 200), 2)
                    
            # Draw waypoints for ALL floors on this map (for context)
            for node in self.path_nodes:
                node_mid = node.get('MapID', 0)
                u, v = self.world_to_pixel(node['PosX'], node['PosY'], mid)
                
                name = node['Node_info'].lower()
                p_info = node.get('PointInfo', 0)
                keywords = ['acoustic', 'visual', 'thermal', 'loto', 'leaked', 'vibration', 'asset', 'charge']
                is_inspection = (any(kw in name for kw in keywords) and 'via' not in name) or p_info == 1
                
                palette = floor_colors[node_mid % len(floor_colors)]
                color = palette[1] if is_inspection else palette[0]
                
                # Draw waypoint as arrow
                yaw = node.get('AngleYaw', 0)
                arrow_len = 15
                end_u = int(u + arrow_len * math.cos(yaw))
                end_v = int(v - arrow_len * math.sin(yaw))
                
                # If the waypoint is on ANOTHER floor, draw it slightly smaller or transparent (outline only)
                if node_mid == mid:
                    cv2.circle(b_map, (int(u), int(v)), 4, color, -1)
                    cv2.arrowedLine(b_map, (int(u), int(v)), (end_u, end_v), color, 2, tipLength=0.4)
                else:
                    # Ghost waypoint from another floor
                    cv2.circle(b_map, (int(u), int(v)), 2, color, 1)
                    cv2.line(b_map, (int(u), int(v)), (end_u, end_v), color, 1)
                    
            self.base_maps[mid] = b_map

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=".")
        if folder:
            self.folder_var.set(folder)
            self.on_folder_change()

    def browse_json(self):
        file_path = filedialog.askopenfilename(initialdir=".", filetypes=[("JSON files", "*.json")])
        if file_path:
            self.json_path_var.set(file_path)
            self.load_waypoints_from_file(file_path)

    def reload_waypoints(self):
        file_path = self.json_path_var.get()
        if file_path:
            self.load_waypoints_from_file(file_path)
        else:
            self.status_label.configure(text="No waypoint file selected to reload.")

    def load_waypoints_from_file(self, json_file):
        if not self.maps: 
            print("Please load Map Dir first.")
            return
        
        if not os.path.exists(json_file):
            print(f"Error: {json_file} not found.")
            if HAS_GUI and not self.args.headless and hasattr(self, 'status_label'):
                self.status_label.configure(text=f"Error: {json_file} not found.")
            return

        print(f"Loading {json_file}...")
        with open(json_file, 'r') as f:
            waypoints = json.load(f)

        start_idx = 0
        for i, node in enumerate(waypoints):
            if 'charge' in str(node.get('Node_info', '')).lower():
                start_idx = i
                break
                
        self.path_nodes = []
        for i in range(start_idx, len(waypoints)):
            node = waypoints[i]
            if 'test' not in str(node.get('Node_info', '')).lower():
                self.path_nodes.append(node)

        if not self.path_nodes:
            print("No valid waypoints found in file.")
            if HAS_GUI and not self.args.headless and hasattr(self, 'status_label'):
                self.status_label.configure(text="No valid waypoints found.")
            return

        # Build list of points so UI dropdown is populated
        wp_names = []
        for i, node in enumerate(self.path_nodes):
            flr = f"(Flr {node.get('MapID',0)+1})"
            wp_names.append(f"{i}: {node['Node_info']} {flr}")
            
        if not self.args.headless and HAS_GUI:
            try:
                self.wp_menu.configure(values=wp_names)
                self.wp_var.set(wp_names[0])
                self.follow_cb.configure(state="normal")
            except: pass
            
        self.precalculate_path_base_maps()

        # Set initial map
        if self.maps:
            self.switch_to_map(self.path_nodes[0].get('MapID', 0))
            self.render_initial_map()
        else:
            if HAS_GUI and not self.args.headless:
                self.status_label.configure(text=f"Loaded {len(self.path_nodes)} waypoints. Waiting for a valid Map Folder to be loaded.")

    def switch_to_map(self, map_id):
        if map_id not in self.maps:
            map_id = list(self.maps.keys())[0]
            
        self.current_map_id = map_id
        m = self.maps[map_id]
        
        if not self.args.headless and HAS_GUI:
            # Only auto-reset view if NOT following robot and NOT in simulation
            is_simulating = self.sim_thread and self.sim_thread.is_alive()
            if not self.view_state['follow_robot'] and not is_simulating:
                initial_zoom = min(self.window_w / m['width'], self.window_h / m['height'])
                self.view_state['zoom'] = initial_zoom
                self.view_state['offset_x'] = (self.window_w - m['width'] * initial_zoom) / 2
                self.view_state['offset_y'] = (self.window_h - m['height'] * initial_zoom) / 2
                self.view_state['default_zoom'] = initial_zoom
                self.view_state['default_offset_x'] = self.view_state['offset_x']
                self.view_state['default_offset_y'] = self.view_state['offset_y']



    def render_splash_screen(self):
        if hasattr(self, 'splash_img'):
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            if cw <= 1 and ch <= 1:
                # If window hasn't laid out yet, retry
                self.after(100, self.render_splash_screen)
                return
            
            # Resize image to fill canvas (no black borders)
            img = cv2.resize(self.splash_img, (cw, ch), interpolation=cv2.INTER_AREA)
            
            disp_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(disp_rgb)
            img_tk = ImageTk.PhotoImage(image=pil_img)
            self.canvas.create_image(0, 0, anchor="nw", image=img_tk)
            self.canvas.image = img_tk  # Keep reference

    def render_initial_map(self):
        if self.current_map_id in self.base_maps:
            ui_frame = self.base_maps[self.current_map_id].copy()
        elif self.maps and self.current_map_id in self.maps:
            ui_frame = self.maps[self.current_map_id]['image'].copy()
        else:
            return
        
        json_file = self.json_path_var.get() if 'json_path_var' in self.__dict__ else self.args.waypoints
        json_name = os.path.basename(json_file) if json_file else "None"
        
        if self.path_nodes:
            p = self.path_nodes[0]
            mu = p.get('MapID', 0)
            if mu == self.current_map_id:
                u, v = self.world_to_pixel(p['PosX'], p['PosY'], mu)
                yaw = p.get('AngleYaw', 0)
                self.draw_robot(ui_frame, u, v, yaw)

        self.last_frame = ui_frame
        self.update_canvas(ui_frame)

    def toggle_pause(self):
        if self.sim_thread and self.sim_thread.is_alive():
            self.is_paused = not self.is_paused
            self.play_pause_btn.configure(text="Play" if self.is_paused else "Pause")
            self.status_label.configure(text="Paused." if self.is_paused else "Running...")

    def stop_simulation(self):
        self.sim_stop_flag = True
        self.is_paused = False
        if self.out:
            self.out.release()
            self.out = None
        self.start_btn.configure(state="normal")
        
        # Reset selection to the first waypoint (Charge)
        if self.path_nodes and hasattr(self, 'wp_menu'):
            try:
                vals = self.wp_menu.cget("values")
                if vals:
                    self.wp_var.set(vals[0])
            except: pass
        self.folder_entry.configure(state="normal")
        self.folder_browse_btn.configure(state="normal")
        self.folder_load_btn.configure(state="normal")
        self.wp_entry.configure(state="normal")
        self.wp_browse_btn.configure(state="normal")
        self.wp_reload_btn.configure(state="normal")
        self.wp_menu.configure(state="normal")
        self.play_pause_btn.configure(state="disabled", text="Pause")
        self.stop_btn.configure(state="disabled")
        self.status_label.configure(text="Stopped.")
        self.render_initial_map()

    def start_simulation(self):
        if not self.base_maps: return
        if self.sim_thread and self.sim_thread.is_alive():
            return
            
        selected_wp_str = self.wp_var.get()
        start_idx = 0
        if ':' in selected_wp_str:
            try:
                start_idx = int(selected_wp_str.split(':')[0])
            except ValueError:
                pass

        self.sim_stop_flag = False
        self.is_paused = False
        
        # Switch to start map
        start_mid = self.path_nodes[start_idx].get('MapID', 0)
        self.switch_to_map(start_mid)
        
        # Disable controls while running
        self.start_btn.configure(state="disabled")
        self.folder_entry.configure(state="disabled")
        self.folder_browse_btn.configure(state="disabled")
        self.folder_load_btn.configure(state="disabled")
        self.wp_entry.configure(state="disabled")
        self.wp_browse_btn.configure(state="disabled")
        self.wp_reload_btn.configure(state="disabled")
        self.wp_menu.configure(state="disabled")
        self.play_pause_btn.configure(state="normal", text="Pause")
        self.stop_btn.configure(state="normal")
        self.status_label.configure(text="Starting...")

        json_name = os.path.basename(self.json_path_var.get()).replace(".json", "")
        output_video = self.args.output if self.args.output else f'simulation_{json_name}.mp4'
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        # The writer resolution must be fixed. 
        # But maps might be different sizes! Let's pick the max dimensions or layer 0.
        out_w = max(m['width'] for m in self.maps.values())
        out_h = max(m['height'] for m in self.maps.values())
        self.out = cv2.VideoWriter(output_video, fourcc, 30.0, (out_w, out_h))

        self.sim_thread = threading.Thread(target=self.run_simulation_loop, args=(start_idx,), daemon=True)
        self.sim_thread.start()

    def reset_view(self):
        self.view_state['zoom'] = self.view_state['default_zoom']
        self.view_state['offset_x'] = self.view_state['default_offset_x']
        self.view_state['offset_y'] = self.view_state['default_offset_y']
        if hasattr(self, 'last_frame'):
            self.update_canvas(self.last_frame)

    def apply_view_transform(self, frame, cw, ch):
        M = np.float32([
            [self.view_state['zoom'], 0, self.view_state['offset_x']],
            [0, self.view_state['zoom'], self.view_state['offset_y']]
        ])
        return cv2.warpAffine(frame, M, (cw, ch))

    def on_closing(self):
        self.app_quit_flag = True
        self.sim_stop_flag = True
        if self.out:
            self.out.release()
        self.destroy()

    def on_mouse_down(self, event):
        # Hit detection for waypoints
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        
        # Inverse transform: Screen -> Image Pixel
        img_x = (event.x - self.view_state['offset_x']) / self.view_state['zoom']
        img_y = (event.y - self.view_state['offset_y']) / self.view_state['zoom']
        
        if self.goal_pose_mode == 1:
            self.temp_goal = {'start_u': img_x, 'start_v': img_y, 'current_u': img_x, 'current_v': img_y}
            self.goal_pose_mode = 2
            self.status_label.configure(text="2D Goal Pose: Step 2 - Move mouse to aim, click to confirm.")
            if hasattr(self, 'last_frame'):
                self.update_canvas(self.last_frame)
            return
        elif self.goal_pose_mode == 2:
            # Confirm Goal Pose
            su, sv = self.temp_goal['start_u'], self.temp_goal['start_v']
            cu, cv = img_x, img_y
            
            x, y = self.pixel_to_world(su, sv, self.current_map_id)
            yaw = -math.atan2(cv - sv, cu - su) # Screen space y is inverted
            
            # Display results
            self.info_text.configure(state="normal")
            self.info_text.delete("1.0", "end")
            self.info_text.insert("end", "=== MANUALLY SELECTED GOAL ===\n", "header")
            self.info_text.insert("end", f"X: {x:.4f}\nY: {y:.4f}\nYaw (rad): {yaw:.4f}\nYaw (deg): {math.degrees(yaw):.2f}\n")
            self.info_text.insert("end", f"MapID: {self.current_map_id}\n")
            self.info_text.tag_config("header", foreground="#3a86ff")
            self.info_text.configure(state="disabled")
            
            self.status_label.configure(text=f"Goal Set: X={x:.2f}, Y={y:.2f}, Yaw={yaw:.2f}")
            
            self.goal_pose_mode = 0
            self.temp_goal = None
            self.goal_pose_btn.configure(fg_color="gray70", text_color="black")
            
            if hasattr(self, 'last_frame'):
                self.update_canvas(self.last_frame)
            return

        hit_found = False
        for i, node in enumerate(self.path_nodes):
            if node.get('MapID', 0) == self.current_map_id:
                u, v = self.world_to_pixel(node['PosX'], node['PosY'], self.current_map_id)
                dist = math.hypot(u - img_x, v - img_y)
                # Detection radius adjusted by zoom (approx 10 pixels in screen space)
                if dist < 10 / self.view_state['zoom']:
                    self.selected_wp_idx = i
                    self.update_sidebar(i)
                    hit_found = True
                    if hasattr(self, 'last_frame'):
                        self.update_canvas(self.last_frame)
                    break
        
        if not hit_found:
            self.view_state['dragging'] = True
            self.view_state['drag_start_x'] = event.x
            self.view_state['drag_start_y'] = event.y

    def on_mouse_up(self, event):
        self.view_state['dragging'] = False

    def on_mouse_move(self, event):
        img_x = (event.x - self.view_state['offset_x']) / self.view_state['zoom']
        img_y = (event.y - self.view_state['offset_y']) / self.view_state['zoom']

        if self.goal_pose_mode == 2 and self.temp_goal:
            self.temp_goal['current_u'] = img_x
            self.temp_goal['current_v'] = img_y
            if hasattr(self, 'last_frame'):
                self.update_canvas(self.last_frame)
            return

        if self.view_state['dragging']:
            # Manual pan disables follow mode
            if self.view_state['follow_robot']:
                self.view_state['follow_robot'] = False
                self.follow_var.set(False)
                
            dx = event.x - self.view_state['drag_start_x']
            dy = event.y - self.view_state['drag_start_y']
            self.view_state['offset_x'] += dx
            self.view_state['offset_y'] += dy
            self.view_state['drag_start_x'] = event.x
            self.view_state['drag_start_y'] = event.y
            if hasattr(self, 'last_frame'):
                self.update_canvas(self.last_frame)

    def on_mouse_wheel(self, event):
        x = event.x
        y = event.y
        zoom_factor = 1.0
        if hasattr(event, 'num'): 
            if event.num == 4: zoom_factor = 1.1
            elif event.num == 5: zoom_factor = 1 / 1.1
        if hasattr(event, 'delta'):
            if event.delta > 0: zoom_factor = 1.1
            elif event.delta < 0: zoom_factor = 1 / 1.1
            
        if zoom_factor != 1.0:
            self.view_state['offset_x'] = x - (x - self.view_state['offset_x']) * zoom_factor
            self.view_state['offset_y'] = y - (y - self.view_state['offset_y']) * zoom_factor
            self.view_state['zoom'] *= zoom_factor
            if hasattr(self, 'last_frame'):
                self.update_canvas(self.last_frame)

    def on_key_press(self, event):
        key = event.keysym.lower() if hasattr(event, 'keysym') else ""
        if key == 'q' or key == 'escape':
            self.on_closing()
        elif key == 'r':
            self.reset_view()
        elif key == 'f':
            self.attributes("-fullscreen", not self.attributes("-fullscreen"))
        elif key == 'space':
            if self.sim_thread and self.sim_thread.is_alive():
                self.toggle_pause()
        elif key == 'equal' or key == 'plus':
            self.view_state['offset_x'] = self.window_w/2 - (self.window_w/2 - self.view_state['offset_x']) * 1.1
            self.view_state['offset_y'] = self.window_h/2 - (self.window_h/2 - self.view_state['offset_y']) * 1.1
            self.view_state['zoom'] *= 1.1
            if hasattr(self, 'last_frame'): self.update_canvas(self.last_frame)
        elif key == 'minus':
            self.view_state['offset_x'] = self.window_w/2 - (self.window_w/2 - self.view_state['offset_x']) / 1.1
            self.view_state['offset_y'] = self.window_h/2 - (self.window_h/2 - self.view_state['offset_y']) / 1.1
            self.view_state['zoom'] /= 1.1
            if hasattr(self, 'last_frame'): self.update_canvas(self.last_frame)
        elif key == 'w': 
            self.view_state['offset_y'] += 50
            if hasattr(self, 'last_frame'): self.update_canvas(self.last_frame)
        elif key == 's': 
            self.view_state['offset_y'] -= 50
            if hasattr(self, 'last_frame'): self.update_canvas(self.last_frame)
        elif key == 'a': 
            self.view_state['offset_x'] += 50
            if hasattr(self, 'last_frame'): self.update_canvas(self.last_frame)
        elif key == 'd': 
            self.view_state['offset_x'] -= 50
            if hasattr(self, 'last_frame'): self.update_canvas(self.last_frame)

    # --- Simulation Logic ---

    def render_frame_func(self, u, v, yaw, i, status_text, write_frame=True):
        if self.app_quit_flag or self.sim_stop_flag: return False
        
        while self.is_paused and not (self.app_quit_flag or self.sim_stop_flag):
            time.sleep(0.1)
        if self.app_quit_flag or self.sim_stop_flag: return False

        # Build frame from the active layer's precomputed base map
        frame = self.base_maps[self.current_map_id].copy()
        
        # Add dynamic history lines for points on the same layer
        for j in range(i):
            p1 = self.path_nodes[j]
            p2 = self.path_nodes[j+1]
            if p1.get('MapID',0) == self.current_map_id and p2.get('MapID',0) == self.current_map_id:
                u1, v1 = self.world_to_pixel(p1['PosX'], p1['PosY'], self.current_map_id)
                u2, v2 = self.world_to_pixel(p2['PosX'], p2['PosY'], self.current_map_id)
                cv2.line(frame, (int(u1), int(v1)), (int(u2), int(v2)), (0, 255, 0), 3)

        if i < len(self.path_nodes) - 1:
            p1 = self.path_nodes[i]
            p2 = self.path_nodes[i+1]
            if p1.get('MapID',0) == self.current_map_id and p2.get('MapID',0) == self.current_map_id:
                u1, v1 = self.world_to_pixel(p1['PosX'], p1['PosY'], self.current_map_id)
                cv2.line(frame, (int(u1), int(v1)), (int(u), int(v)), (0, 255, 0), 3)
            move_text = f"{self.path_nodes[i]['Node_info']} -> {self.path_nodes[i+1]['Node_info']}"
        else:
            move_text = "Finished"

        # Draw robot
        if self.robot_img_raw is not None:
            self.draw_robot(frame, u, v, yaw)
        else:
            radius = 15
            cv2.circle(frame, (int(u), int(v)), radius, (0, 255, 255), -1)
            cv2.circle(frame, (int(u), int(v)), radius, (0, 0, 0), 2)
            end_u = int(u + radius * 1.5 * math.cos(yaw))
            end_v = int(v - radius * 1.5 * math.sin(yaw))
            cv2.line(frame, (int(u), int(v)), (end_u, end_v), (0, 0, 255), 3)

        cv2.putText(frame, f"State: {status_text} | Path: {move_text}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        cv2.putText(frame, f"Waypoints: {len(self.path_nodes)} | Layer: {self.current_map_id}", (50, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        cv2.putText(frame, "Controls: [Scroll] Zoom | [Drag] Pan | [Space] Pause", (50, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

        self.last_frame = frame
        
        if write_frame and self.out:
            # We must output a video frame of exactly the video writer's size
            out_w, out_h = self.out.get(cv2.CAP_PROP_FRAME_WIDTH), self.out.get(cv2.CAP_PROP_FRAME_HEIGHT)
            out_w, out_h = int(out_w), int(out_h)
            h, w = frame.shape[:2]
            
            # Pad or crop to fit the writer bounds
            if w == out_w and h == out_h:
                self.out.write(frame)
            else:
                out_frame = np.zeros((out_h, out_w, 3), dtype=np.uint8)
                out_frame[0:min(h, out_h), 0:min(w, out_w)] = frame[0:min(h, out_h), 0:min(w, out_w)]
                self.out.write(out_frame)

        if not self.args.headless and HAS_GUI:
            try:
                self.status_label.configure(text=f"State: {status_text} | {move_text}")
            except:
                pass
            self.update_canvas(frame, u, v)
            time.sleep(1.0/30.0)
            
        return True

    def draw_robot(self, frame, u, v, yaw):
        m = self.maps[self.current_map_id]
        res = m['resolution']
        
        # Target size in pixels from config
        target_w = int(self.robot_config.get('length_m', 1.0) / res)
        target_h = int(self.robot_config.get('width_m', 0.46) / res)
        
        # Resize and Rotate
        resized = cv2.resize(self.robot_img_raw, (target_w, target_h))
        
        # Rotation (yaw is in radians, convert to degrees CCW for OpenCV)
        angle_deg = math.degrees(yaw)
        rot_mat = cv2.getRotationMatrix2D((target_w/2, target_h/2), angle_deg, 1.0)
        
        # Calculation for bounding box of rotated image to avoid clipping
        cos = np.abs(rot_mat[0, 0])
        sin = np.abs(rot_mat[0, 1])
        new_w = int((target_h * sin) + (target_w * cos))
        new_h = int((target_h * cos) + (target_w * sin))
        
        rot_mat[0, 2] += (new_w / 2) - (target_w / 2)
        rot_mat[1, 2] += (new_h / 2) - (target_h / 2)
        
        rotated = cv2.warpAffine(resized, rot_mat, (new_w, new_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0,0))
        
        # Overlay with alpha channel
        y1, y2 = int(v - new_h/2), int(v + new_h - new_h/2)
        x1, x2 = int(u - new_w/2), int(u + new_w - new_w/2)
        
        # Clip to frame boundaries
        fh, fw = frame.shape[:2]
        if y1 < 0 or y2 > fh or x1 < 0 or x2 > fw:
            # We need to crop 'rotated' and adjust y1, y2, x1, x2
            ry1, ry2 = max(0, -y1), new_h - max(0, y2 - fh)
            rx1, rx2 = max(0, -x1), new_w - max(0, x2 - fw)
            y1, y2 = max(0, y1), min(fh, y2)
            x1, x2 = max(0, x1), min(fw, x2)
            if ry1 >= ry2 or rx1 >= rx2: return
            rotated = rotated[ry1:ry2, rx1:rx2]
        
        alpha = rotated[:, :, 3] / 255.0
        for c in range(3):
            frame[y1:y2, x1:x2, c] = (1.0 - alpha) * frame[y1:y2, x1:x2, c] + alpha * rotated[:, :, c]

    def update_canvas(self, frame, robot_u=None, robot_v=None):
        try:
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            if cw < 50: cw = self.window_w
            if ch < 50: ch = self.window_h

            # If follow mode is ON, update offsets to center the robot
            if self.view_state['follow_robot'] and robot_u is not None and robot_v is not None:
                self.view_state['offset_x'] = cw / 2 - robot_u * self.view_state['zoom']
                self.view_state['offset_y'] = ch / 2 - robot_v * self.view_state['zoom']

            disp_frame = self.apply_view_transform(frame, cw, ch)
            
            # Draw highlight for selected waypoint
            if self.selected_wp_idx is not None:
                node = self.path_nodes[self.selected_wp_idx]
                if node.get('MapID', 0) == self.current_map_id:
                    u, v = self.world_to_pixel(node['PosX'], node['PosY'], self.current_map_id)
                    # Convert to screen space
                    sc_x = int(u * self.view_state['zoom'] + self.view_state['offset_x'])
                    sc_y = int(v * self.view_state['zoom'] + self.view_state['offset_y'])
                    cv2.circle(disp_frame, (sc_x, sc_y), 15, (0, 0, 255), 2)
                    cv2.circle(disp_frame, (sc_x, sc_y), 2, (0, 0, 255), -1)

            # Draw temporary goal pose arrow
            if self.temp_goal:
                su, sv = self.temp_goal['start_u'], self.temp_goal['start_v']
                cu, cv = self.temp_goal['current_u'], self.temp_goal['current_v']
                
                # Limit world-space length to 2.0 meters
                if self.maps:
                    m = self.maps[self.current_map_id]
                    res = m['resolution']
                    dist_px = math.hypot(cu - su, cv - sv)
                    dist_world = dist_px * res
                    
                    if dist_world > 2.0:
                        max_px = 2.0 / res
                        ratio = max_px / dist_px
                        cu = su + (cu - su) * ratio
                        cv = sv + (cv - sv) * ratio

                # Convert to screen space
                sx_scr = int(su * self.view_state['zoom'] + self.view_state['offset_x'])
                sy_scr = int(sv * self.view_state['zoom'] + self.view_state['offset_y'])
                cx_scr = int(cu * self.view_state['zoom'] + self.view_state['offset_x'])
                cy_scr = int(cv * self.view_state['zoom'] + self.view_state['offset_y'])
                
                cv2.circle(disp_frame, (sx_scr, sy_scr), 5, (0, 255, 0), -1)
                dist_scr = math.hypot(cx_scr - sx_scr, cy_scr - sy_scr)
                if dist_scr > 5:
                    cv2.arrowedLine(disp_frame, (sx_scr, sy_scr), (cx_scr, cy_scr), (0, 255, 0), 3, tipLength=0.3)

            disp_rgb = cv2.cvtColor(disp_frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(disp_rgb)
            img_tk = ImageTk.PhotoImage(image=pil_img)
            
            if not hasattr(self.canvas, 'image_item'):
                self.canvas.image_item = self.canvas.create_image(0, 0, anchor="nw", image=img_tk)
            else:
                self.canvas.itemconfig(self.canvas.image_item, image=img_tk)
            self.canvas.image = img_tk
        except Exception as e:
            pass

    def run_simulation_loop(self, start_idx=0):
        if not self.path_nodes: return
        
        def shortest_angle_diff(target, current):
            diff = (target - current) % (2 * math.pi)
            if diff > math.pi: diff -= 2 * math.pi
            return diff
            
        current_yaw = self.path_nodes[start_idx].get('AngleYaw', 0)
        
        # Initial render and sidebar update
        if HAS_GUI and not self.args.headless:
            self.after(0, self.update_sidebar, start_idx)
            
        # Get initial robot position for rendering
        p_start = self.path_nodes[start_idx]
        u_start, v_start = self.world_to_pixel(p_start['PosX'], p_start['PosY'], p_start.get('MapID', 0))
        if not self.render_frame_func(u_start, v_start, current_yaw, start_idx, "Starting"): return

        for i in range(start_idx, len(self.path_nodes)-1):
            if self.app_quit_flag or self.sim_stop_flag: break
            
            p1 = self.path_nodes[i]
            p2 = self.path_nodes[i+1]
            
            m1 = p1.get('MapID', 0)
            m2 = p2.get('MapID', 0)
            
            # Switch map layer if needed
            if m1 != self.current_map_id:
                self.switch_to_map(m1)
                
            u1, v1 = self.world_to_pixel(p1['PosX'], p1['PosY'], m1)
            u2, v2 = self.world_to_pixel(p2['PosX'], p2['PosY'], m2)
            
            # If changing floor, just jump to the start of the next floor or do a fake transition
            if m1 != m2:
                # Elevator simulation
                if not self.render_frame_func(u1, v1, current_yaw, i, f"Changing to Floor {m2+1}"): break
                for t in range(30): # Wait 1 sec
                     if not self.render_frame_func(u1, v1, current_yaw, i, "Elevator..."): break
                self.switch_to_map(m2)
                if not self.render_frame_func(u2, v2, current_yaw, i, f"Arrived Floor {m2+1}"): break
                continue

            dist = math.hypot(u2-u1, v2-v1)
            # Use fixed pixel steps so speed is consistent across resolutions
            steps = max(int(dist / self.args.speed), 1)
            path_yaw = math.atan2(-(v2-v1), u2-u1)
            
            # Phase 1: Turn
            diff = shortest_angle_diff(path_yaw, current_yaw)
            turn_steps = max(int(abs(diff) / 0.1), 1)
            if abs(diff) > 0.05:
                for t in range(turn_steps):
                    current_yaw += diff / turn_steps
                    if not self.render_frame_func(u1, v1, current_yaw, i, "Turning to Path"): break
                        
            # Phase 2: Move
            for t in range(1, steps+1):
                u = u1 + (u2-u1)*t/steps
                v = v1 + (v2-v1)*t/steps
                if not self.render_frame_func(u, v, current_yaw, i, "Moving"): break
                    
            # Phase 3: Inspect
            name = p2['Node_info'].lower()
            p_info = p2.get('PointInfo', 0)
            keywords = ['acoustic', 'visual', 'thermal', 'loto', 'leaked', 'vibration', 'asset', 'charge']
            if (any(kw in name for kw in keywords) and 'via' not in name) or p_info == 1:
                target_yaw = p2.get('AngleYaw', 0)
                diff = shortest_angle_diff(target_yaw, current_yaw)
                turn_steps = max(int(abs(diff) / 0.1), 1)
                
                if abs(diff) > 0.05:
                    for t in range(turn_steps):
                        current_yaw += diff / turn_steps
                        if not self.render_frame_func(u2, v2, current_yaw, i, "Aligning (Inspect)"): break
                        
                # Update sidebar safely after aligning
                if HAS_GUI and not self.args.headless:
                    self.after(0, self.update_sidebar, i + 1)
                            
                for t in range(45): # Wait 1.5 seconds at 30fps
                    if not self.render_frame_func(u2, v2, current_yaw, i, "Inspecting..."): break
                
                # Take image away before moving to next
                if HAS_GUI and not self.args.headless:
                    self.after(0, self.clear_sidebar_image)
            else:
                # Arrived at a normal via point
                if HAS_GUI and not self.args.headless:
                    self.after(0, self.update_sidebar, i + 1)
                    self.after(0, self.clear_sidebar_image)

        if not (self.app_quit_flag or self.sim_stop_flag):
            last_p = self.path_nodes[-1]
            last_m = last_p.get('MapID', 0)
            if last_m != self.current_map_id:
                self.switch_to_map(last_m)
                
            u, v = self.world_to_pixel(last_p['PosX'], last_p['PosY'], last_m)
            
            for _ in range(60):
                if not self.render_frame_func(u, v, current_yaw, len(self.path_nodes)-1, "Completed"):
                    break
            
            if not self.args.headless and HAS_GUI:
                try:
                    self.play_pause_btn.configure(state="disabled")
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    self.folder_entry.configure(state="normal")
                    self.folder_browse_btn.configure(state="normal")
                    self.folder_load_btn.configure(state="normal")
                    self.wp_entry.configure(state="normal")
                    self.wp_browse_btn.configure(state="normal")
                    self.wp_menu.configure(state="normal")
                    self.status_label.configure(text="Finished.")
                except:
                    pass

        if self.out: 
            self.out.release()
            self.out = None
        print("Simulation loop finished.")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_map = os.path.join(script_dir, '../resource/maps/Nestle-full')
    default_waypoints = os.path.join(script_dir, '../resource/waypoints/wet_zone_3.json')
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--waypoints', type=str, default=default_waypoints, help='Path to JSON file')
    parser.add_argument('--speed', type=int, default=5)
    parser.add_argument('--output', type=str, default='')
    parser.add_argument('--map_folder', type=str, default=default_map, help='Folder containing jueying*.pgm and yaml')
    parser.add_argument('--headless', action='store_true')
    args = parser.parse_args()

    app = SimulationApp(args)
    if not args.headless and HAS_GUI:
        app.mainloop()

if __name__ == '__main__':
    main()
