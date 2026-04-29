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
    from PIL import Image, ImageTk, ImageGrab
    import tkinter as tk
    from tkinter import filedialog, ttk
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

class CustomDropdown(ctk.CTkToplevel):
    def __init__(self, master, x, y, sections, width=180):
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(fg_color="#00264d") # Match the navbar color
        self.attributes("-topmost", True)
        
        # Main frame
        self.frame = ctk.CTkFrame(self, fg_color="#00264d", border_color="white", border_width=2, corner_radius=10)
        self.frame.pack(fill="both", expand=True)
        
        total_height = 0
        for section_name, items in sections.items():
            # Section Header
            header = ctk.CTkLabel(self.frame, text=section_name, font=ctk.CTkFont(size=12, weight="bold"), 
                                 text_color="gray70", anchor="w")
            header.pack(fill="x", padx=15, pady=(10, 2))
            total_height += 30
            
            for item_name, command in items:
                btn = ctk.CTkButton(self.frame, text=item_name, fg_color="transparent", 
                                   hover_color="#00366d", anchor="w", height=30,
                                   corner_radius=5, command=lambda c=command: self.select(c))
                btn.pack(fill="x", padx=5, pady=2)
                total_height += 34
            
            # Add separator logic (except after last section)
            if list(sections.keys())[-1] != section_name:
                sep = ctk.CTkFrame(self.frame, height=2, fg_color="white")
                sep.pack(fill="x", padx=10, pady=5)
                total_height += 12
        
        self.geometry(f"{width}x{total_height + 10}+{x}+{y}")
        
        # Close logic
        self.bind("<FocusOut>", lambda e: self.destroy())
        self.after(10, self.focus_force)

    def select(self, command):
        self.destroy()
        if command: command()

class CreateWaypointPopup(ctk.CTkToplevel):
    def __init__(self, master, on_create, on_cancel):
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(fg_color="#ffffff")
        self.attributes("-topmost", True)
        
        # Border Frame
        self.main_frame = ctk.CTkFrame(self, fg_color="#ffffff", corner_radius=15, border_width=2, border_color="#00264d")
        self.main_frame.pack(fill="both", expand=True)
        
        # Header
        self.header = ctk.CTkLabel(self.main_frame, text="Create Waypoints", font=ctk.CTkFont(size=18, weight="bold"), text_color="#00264d")
        self.header.pack(pady=(20, 10), padx=20)
        
        # Body
        self.input_label = ctk.CTkLabel(self.main_frame, text="Filename:", text_color="black")
        self.input_label.pack(pady=(10, 0), padx=20, anchor="w")
        self.input_field = ctk.CTkEntry(self.main_frame, placeholder_text="e.g. mission_01", width=300, height=40, text_color="black", fg_color="white")
        self.input_field.pack(pady=(5, 20), padx=20)
        
        # Footer
        self.footer = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.footer.pack(pady=(0, 20), padx=20, fill="x")
        
        self.cancel_btn = ctk.CTkButton(self.footer, text="Cancel", fg_color="gray70", hover_color="gray60", text_color="black", command=on_cancel)
        self.cancel_btn.pack(side="left", padx=(0, 10), expand=True, fill="x")
        
        self.create_btn = ctk.CTkButton(self.footer, text="Create", fg_color="#00264d", hover_color="#00366d", text_color="white", command=lambda: on_create(self.input_field.get()))
        self.create_btn.pack(side="left", padx=(10, 0), expand=True, fill="x")
        
        # Center the popup
        self.update_idletasks()
        w = 350
        h = 250
        x = master.winfo_rootx() + (master.winfo_width() // 2) - (w // 2)
        y = master.winfo_rooty() + (master.winfo_height() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        
        self.input_field.focus_force()

class SimulationApp(ctk.CTk if HAS_GUI else object):
    def __init__(self, args):
        self.args = args
        self.app_quit_flag = False
        self.sim_stop_flag = False
        self.is_paused = False
        self.sim_thread = None
        self.selected_wp_idx = None
        self.goal_pose_mode = 0  # 0: Off, 1: Select Pos, 2: Select Yaw
        self.temp_goal = None  # {start_u, start_v, current_u, current_v}
        self.file_menu = None
        self.create_menu = None
        self.insert_idx = None
        self.selected_edge_idx = None
        self.dragging_wp_idx = None
        self.rotating_wp_idx = None

        # Load robot & map config
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.robot_config = {'length_m': 1.0, 'width_m': 0.46}
        self.map_config = {'use_default': False, 'default_path': ''}
        
        config_path = os.path.join(script_dir, '../config/robot_config.yaml')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    cfg = yaml.safe_load(f)
                    if cfg:
                        if 'robot' in cfg:
                            self.robot_config.update(cfg['robot'])
                        if 'map' in cfg:
                            self.map_config.update(cfg['map'])
            except Exception as e:
                print(f"Error loading config: {e}")

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
            self.title("")
            self.overrideredirect(False)
            
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
            'follow_robot': False
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
        
        # Handle Default Map Loading
        if self.map_config.get('use_default', False):
            dpath = self.map_config.get('default_path', '')
            if dpath:
                full_dpath = os.path.normpath(os.path.join(script_dir, '..', dpath))
                if os.path.exists(full_dpath):
                    self.load_map_folder(full_dpath)
                    if not args.headless and HAS_GUI:
                        self.folder_var.set(full_dpath)

        # Create TakeScreen directory
        self.takescreen_dir = os.path.join(script_dir, '../TakeScreen')
        if not os.path.exists(self.takescreen_dir):
            os.makedirs(self.takescreen_dir)
            print(f"Created directory: {self.takescreen_dir}")

        if not args.headless:
            # If no map was auto-loaded, just render splash
            if not self.maps:
                self.last_frame = self.splash_img
                if HAS_GUI:
                    self.after(100, self.render_splash_screen)
            else:
                self.switch_to_map(self.current_map_id)
                self.render_initial_map()
            
        else:
            if not self.maps:
                self.load_map_folder(args.map_folder)
                
            if args.waypoints and os.path.exists(args.waypoints):
                self.load_waypoints_from_file(args.waypoints)
                self.run_simulation_loop(0)
            else:
                print("Error: No waypoints file specified for headless mode.")

    def show_file_menu(self, event=None):
        if self.file_menu and self.file_menu.winfo_exists():
            self.file_menu.destroy()
            self.file_menu = None
            return
        
        # Calculate position below the "File" button
        btn = self.menu_buttons["File"]
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height() + 5
        
        sections = {
            "Import": [
                ("Import Map", self.browse_folder),
                ("Import Waypoints", self.browse_json)
            ],
            "Export": [
                ("Export Waypoints", self.export_waypoints),
                ("Export as Image", self.export_as_image)
            ]
        }
        
        self.file_menu = CustomDropdown(self, x, y, sections, width=200)

    def show_create_menu(self, event=None):
        if self.create_menu and self.create_menu.winfo_exists():
            self.create_menu.destroy()
            self.create_menu = None
            return
        
        # Calculate position below the "Create" button
        btn = self.menu_buttons["Create"]
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height() + 5
        
        sections = {
            "Waypoints": [
                ("Create Waypoint", self.open_create_waypoint_popup)
            ]
        }
        
        self.create_menu = CustomDropdown(self, x, y, sections, width=180)

    def open_create_waypoint_popup(self):
        if not self.maps:
            self.status_label.configure(text="Error: Please load Map Directory before creating waypoints.")
            return

        # Create Overlay (Semi-transparent)
        self.overlay = ctk.CTkToplevel(self)
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-alpha", 0.1) # Much lighter
        self.overlay.configure(fg_color="black")
        
        # Match main window geometry
        x = self.winfo_rootx()
        y = self.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()
        self.overlay.geometry(f"{w}x{h}+{x}+{y}")
        self.overlay.wait_visibility() # Ensure it's ready for alpha on Linux
        self.overlay.lift()
        
        # Create Popup
        self.popup = CreateWaypointPopup(self, self.on_create_waypoint, self.close_create_waypoint_popup)
        self.popup.lift()

    def close_create_waypoint_popup(self):
        if hasattr(self, 'popup'):
            self.popup.destroy()
        if hasattr(self, 'overlay'):
            self.overlay.destroy()

    def on_create_waypoint(self, filename):
        if not filename:
            self.status_label.configure(text="Error: Filename cannot be empty.")
            return
        
        if not filename.endswith(".json"):
            filename += ".json"
            
        script_dir = os.path.dirname(os.path.abspath(__file__))
        tmp_dir = os.path.join(script_dir, "../tmp")
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
            
        file_path = os.path.join(tmp_dir, filename)
        
        try:
            with open(file_path, 'w') as f:
                json.dump([], f, indent=4)
            
            self.status_label.configure(text=f"Created new waypoint file: {filename}")
            
            # Update UI
            self.json_path_var.set(file_path)
            self.load_waypoints_from_file(file_path)
            
            # Close popup
            self.close_create_waypoint_popup()
            
            # Auto-show sidebar and clear for first point
            self.ensure_sidebar_visible()
            self.set_sidebar_mode("editor")
            self.clear_editor_for_new_point()
            
        except Exception as e:
            self.status_label.configure(text=f"Error creating file: {e}")


    def setup_ui(self):
        # Layer 1: Top Navbar (Branded Color)
        self.navbar_top = ctk.CTkFrame(self, height=60, fg_color="#00264d", corner_radius=0)
        self.navbar_top.pack(fill="x")
        
        # Menu Buttons (Dark Blue Background, White Border)
        self.menu_buttons = {}
        menu_items = ["File", "Create", "Edit", "View", "Simulate"]
        for item in menu_items:
            if item == "File":
                cmd = self.show_file_menu
            elif item == "Create":
                cmd = self.show_create_menu
            elif item == "Simulate":
                cmd = self.start_simulation
            elif item == "Edit":
                cmd = self.toggle_edit_controls
            elif item == "View":
                cmd = self.show_view_menu
            else:
                cmd = None
            btn = ctk.CTkButton(self.navbar_top, text=item, width=90, height=35, 
                               fg_color="#00264d", border_color="white", border_width=2,
                               text_color="white", corner_radius=10, 
                               font=ctk.CTkFont(size=15, weight="bold"),
                               command=cmd)
            btn.pack(side="left", padx=10, pady=12)
            self.menu_buttons[item] = btn
            
            # File menu is now click-only per user request

        # Logo Placeholder (Right Side) - Replacement with Image
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "..", "resource", "gensurv-logo.jpg")
            if os.path.exists(logo_path):
                raw_img = Image.open(logo_path)
                # Resize to fit height (60px navbar - padding)
                h = 40
                w = int(raw_img.width * (h / raw_img.height))
                self.logo_img = ctk.CTkImage(light_image=raw_img, dark_image=raw_img, size=(w, h))
                logo_label = ctk.CTkLabel(self.navbar_top, image=self.logo_img, text="")
            else:
                logo_label = ctk.CTkLabel(self.navbar_top, text="GENSURV ROBOTICS", 
                                         text_color="white", font=ctk.CTkFont(size=14, weight="bold"))
        except Exception as e:
            print(f"Logo error: {e}")
            logo_label = ctk.CTkLabel(self.navbar_top, text="GENSURV ROBOTICS", 
                                     text_color="white", font=ctk.CTkFont(size=14, weight="bold"))
        
        logo_label.pack(side="right", padx=20)

        # Layer 2: White Strip (Now contains controls)
        self.navbar_bottom = ctk.CTkFrame(self, fg_color="white", corner_radius=0)
        self.navbar_bottom.pack(fill="x")
        
        # Add blue bottom border to Layer 2
        self.navbar_bottom_border = ctk.CTkFrame(self, height=2, fg_color="#002b5b", corner_radius=0)
        self.navbar_bottom_border.pack(fill="x")

        # Row 1: Map Folder
        self.map_row = ctk.CTkFrame(self.navbar_bottom, height=1, fg_color="transparent")
        self.map_row.pack(fill="x", padx=10, pady=(5, 1))
        
        ctk.CTkLabel(self.map_row, text="Map Dir:", text_color="black").pack(side="left", padx=5)
        self.folder_var = ctk.StringVar(value=self.args.map_folder)
        self.folder_entry = ctk.CTkEntry(self.map_row, textvariable=self.folder_var, width=300)
        self.folder_entry.pack(side="left", padx=5)
        self.folder_load_btn = ctk.CTkButton(self.map_row, text="Update Map", width=100, command=self.on_folder_change)
        self.folder_load_btn.pack(side="left", padx=5)

        # Row 2: Waypoints
        self.wp_row = ctk.CTkFrame(self.navbar_bottom, height=1, fg_color="transparent")
        self.wp_row.pack(fill="x", padx=10, pady=1)
        
        ctk.CTkLabel(self.wp_row, text="Waypoints File:", text_color="black").pack(side="left", padx=5)
        self.json_path_var = ctk.StringVar(value="")
        self.wp_entry = ctk.CTkEntry(self.wp_row, textvariable=self.json_path_var, width=500)
        self.wp_entry.pack(side="left", padx=5)
        self.wp_reload_btn = ctk.CTkButton(self.wp_row, text="Reload", width=80, command=self.reload_waypoints)
        self.wp_reload_btn.pack(side="left", padx=5)
        
        # Row 3: Simulation Controls
        self.sim_row = ctk.CTkFrame(self.navbar_bottom, height=1, fg_color="transparent")
        self.sim_row.pack(fill="x", padx=10, pady=1)

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
        
        self.follow_var = ctk.BooleanVar(value=False)
        self.follow_cb = ctk.CTkCheckBox(self.sim_row, text="Follow Robot", variable=self.follow_var, command=self.on_follow_toggle, state="disabled", text_color="black")
        self.follow_cb.pack(side="left", padx=10)
        
        self.status_label = ctk.CTkLabel(self.sim_row, text="Ready. Please load a Map Directory and a Waypoints JSON.", text_color="black")
        self.status_label.pack(side="left", padx=15)
        
        self.toggle_sidebar_btn = ctk.CTkButton(self.sim_row, text="Sidebar >", width=80, 
                                                fg_color="#2D2D2D", hover_color="darkred",
                                                command=self.toggle_sidebar)
        self.toggle_sidebar_btn.pack(side="right", padx=5)
        self.sidebar_visible = True

        self.floor_row = ctk.CTkFrame(self.navbar_bottom, height=1, fg_color="transparent")
        self.floor_row.pack(fill="x", padx=10, pady=(0, 3))
        self.floor_buttons = {}

        # Row 5: Edit Controls (Initially Hidden)
        self.edit_controls_row = ctk.CTkFrame(self.navbar_bottom, height=1, fg_color="transparent")
        self.edit_controls_visible = False
        self.edit_mode = "none" # "none", "insert", "edit_point"

        self.insert_point_btn = ctk.CTkButton(self.edit_controls_row, text="InsertPoint", width=120, height=35,
                                              fg_color="#b71836", hover_color="#90122a", text_color="white",
                                              command=lambda: self.set_edit_mode("insert"))
        self.insert_point_btn.pack(side="left", padx=5, pady=5)

        self.insert_line_btn = ctk.CTkButton(self.edit_controls_row, text="InsertPoint2Line", width=140, height=35,
                                              fg_color="#b71836", hover_color="#90122a", text_color="white",
                                              command=lambda: self.set_edit_mode("insert_line"))
        self.insert_line_btn.pack(side="left", padx=5, pady=5)

        self.edit_point_btn = ctk.CTkButton(self.edit_controls_row, text="EditPoint", width=120, height=35,
                                            fg_color="#b71836", hover_color="#90122a", text_color="white",
                                            command=lambda: self.set_edit_mode("edit_point"))
        self.edit_point_btn.pack(side="left", padx=5, pady=5)
        
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
        
        # Sidebar for info (Exact Template 02 Style: #b71836 + Black Text)
        self.sidebar = ctk.CTkFrame(self.paned_window, width=450, fg_color="#b71836", corner_radius=0)
        self.sidebar.pack_propagate(False)
        self.paned_window.add(self.sidebar, weight=0)
        
        ctk.CTkLabel(self.sidebar, text="Waypoint Information", 
                     text_color="#000000",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(10, 5))
        
        # Search row
        self.search_row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.search_row.pack(fill="x", padx=20, pady=2)
        
        self.search_entry = ctk.CTkEntry(self.search_row, placeholder_text="Name or Index...", 
                                         width=250, height=35,
                                         fg_color="#b71836", border_color="#00264d", border_width=3,
                                         text_color="#000000", placeholder_text_color="#333333",
                                         corner_radius=0)
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_entry.bind("<Return>", lambda e: self.perform_search())
        
        self.search_btn = ctk.CTkButton(self.search_row, text="Search", width=80, height=35,
                                       fg_color="#00264d", hover_color="#001a35",
                                       text_color="#FFFFFF", corner_radius=5,
                                       command=self.perform_search)
        self.search_btn.pack(side="left")
        
        # Suble Separator Line (Black for high contrast on Red)
        ctk.CTkFrame(self.sidebar, height=2, fg_color="#000000").pack(fill="x", padx=20, pady=10)
        
        # --- Mode 1: Informational (Original) ---
        self.info_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.info_frame.pack(fill="both", expand=True)
        
        self.info_text = ctk.CTkTextbox(self.info_frame, width=400, height=300,
                                        fg_color="#b71836", text_color="#000000",
                                        border_color="#00264d", border_width=2,
                                        font=ctk.CTkFont(size=14, weight="bold"),
                                        corner_radius=0)
        self.info_text.pack(padx=20, pady=5, fill="both", expand=True)
        self.info_text.configure(state="disabled")

        # Inspection Photo Frame (Initially Hidden)
        self.image_frame = ctk.CTkFrame(self.info_frame, fg_color="#FFFFFF", border_width=2, border_color="#00264d")
        
        self.image_label = ctk.CTkLabel(self.image_frame, text="No Photo Available", 
                                        text_color="black", font=ctk.CTkFont(size=12, weight="bold"))
        self.image_label.pack(fill="both", expand=True)

        # --- Mode 2: Editor (Waypoint Editor) ---
        self.editor_master_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        # Note: editor_master_frame is packed only when in editor mode
        
        # Waypoint Editor Container (Scrollable)
        self.editor_frame = ctk.CTkScrollableFrame(self.editor_master_frame, fg_color="#b71836", corner_radius=0, 
                                                 scrollbar_button_color="#00264d",
                                                 scrollbar_button_hover_color="#00366d")
        self.editor_frame.pack(padx=10, pady=5, fill="both", expand=True)

        self.editor_fields = {}
        
        # 1. Coordinates Group
        self.editor_fields["PosX"] = self.create_editor_field("PosX")
        self.editor_fields["PosY"] = self.create_editor_field("PosY")
        self.editor_fields["PosZ"] = self.create_editor_field("PosZ", "0.0")
        self.editor_fields["AngleYaw"] = self.create_editor_field("AngleYaw (Yaw)")

        # 2. Node Info Group
        self.editor_fields["Node_info"] = self.create_editor_field("Node Info", "Waypoint_1")
        self.editor_fields["MapID"] = self.create_editor_field("Map ID", "0")
        self.editor_fields["MapName"] = self.create_editor_field("Map Name", "1st_floor")
        self.editor_fields["Zone"] = self.create_editor_field("Zone", "wet1")

        # 3. Dropdowns
        
        self.gait_map = {"Walking": 0, "Off-Road": 1, "Slope": 2, "Perceptual Stair": 4, "Multi-Frame Stair": 6, "Multi-Frame 45 Stair": 7}
        self.editor_fields["Gait"] = self.create_editor_dropdown("Gait", list(self.gait_map.keys()))

        self.nav_mode_map = {"Straight": 0, "Auto": 1}
        self.editor_fields["NavMode"] = self.create_editor_dropdown("Nav Mode", list(self.nav_mode_map.keys()))

        self.speed_map = {"Normal": 0, "Low": 1, "High": 2}
        self.editor_fields["Speed"] = self.create_editor_dropdown("Speed", list(self.speed_map.keys()))

        self.terrain_map = {"Solid": 0, "Grid": 1, "Multi-Frame": 3}
        self.editor_fields["Terrain"] = self.create_editor_dropdown("Terrain", list(self.terrain_map.keys()))

        self.point_info_map = {"Transition": 0, "Task": 1, "Standing": 2, "Charge": 3}
        self.editor_fields["PointInfo"] = self.create_editor_dropdown("Point Info", list(self.point_info_map.keys()))

        self.obs_mode_map = {"Enable": 0, "Disable": 1}
        self.editor_fields["ObsMode"] = self.create_editor_dropdown("Obs Mode", list(self.obs_mode_map.keys()))

        self.manner_map = {"Forward": 0, "Backward": 1}
        self.editor_fields["Manner"] = self.create_editor_dropdown("Manner", list(self.manner_map.keys()))

        self.posture_map = {"Normal": 0, "Crawl": 1}
        self.editor_fields["Posture"] = self.create_editor_dropdown("Posture", list(self.posture_map.keys()))

        # Reverse maps for updating UI from data
        self.gait_rev_map = {v: k for k, v in self.gait_map.items()}
        self.nav_mode_rev_map = {v: k for k, v in self.nav_mode_map.items()}
        self.speed_rev_map = {v: k for k, v in self.speed_map.items()}
        self.terrain_rev_map = {v: k for k, v in self.terrain_map.items()}
        self.point_info_rev_map = {v: k for k, v in self.point_info_map.items()}
        self.obs_mode_rev_map = {v: k for k, v in self.obs_mode_map.items()}
        self.manner_rev_map = {v: k for k, v in self.manner_map.items()}
        self.posture_rev_map = {v: k for k, v in self.posture_map.items()}

        # Save Button
        self.save_point_btn = ctk.CTkButton(self.editor_master_frame, text="Save Point", height=50,
                                           fg_color="#00264d", hover_color="#001a35",
                                           text_color="#FFFFFF", corner_radius=10,
                                           font=ctk.CTkFont(size=16, weight="bold"),
                                           command=self.save_waypoint_to_list)
        self.save_point_btn.pack(pady=20, padx=20, fill="x")

        self.sidebar_mode = "info" # "info" or "editor"

    def create_editor_section(self, title):
        label = ctk.CTkLabel(self.editor_frame, text=f"-- {title} --", font=ctk.CTkFont(weight="bold"), text_color="#000000")
        label.pack(pady=(10, 5))

    def create_editor_field(self, label_text, default_val=""):
        frame = ctk.CTkFrame(self.editor_frame, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(frame, text=label_text, text_color="#000000", width=120, anchor="w").pack(side="left")
        entry = ctk.CTkEntry(frame, height=30, fg_color="#FFFFFF", text_color="#000000", border_color="#00264d")
        entry.insert(0, default_val)
        entry.pack(side="left", fill="x", expand=True)
        return entry

    def create_editor_dropdown(self, label_text, options):
        frame = ctk.CTkFrame(self.editor_frame, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(frame, text=label_text, text_color="#000000", width=120, anchor="w").pack(side="left")
        dropdown = ctk.CTkOptionMenu(frame, values=options, fg_color="#00264d", button_color="#00264d", 
                                     button_hover_color="#00366d", text_color="white", height=30)
        dropdown.pack(side="left", fill="x", expand=True)
        return dropdown

    def save_waypoint_to_list(self):
        try:
            # Collect data
            # Determine CamPTZ: keep existing if editing, else use default
            cam_ptz = [0.0, 0.0, 0.0]
            if self.selected_wp_idx is not None and self.selected_wp_idx < len(self.path_nodes):
                cam_ptz = self.path_nodes[self.selected_wp_idx].get("CamPTZ", [0.0, 0.0, 0.0])

            node = {
                "Node_info": self.editor_fields["Node_info"].get(),
                "MapName": self.editor_fields["MapName"].get(),
                "Zone": self.editor_fields["Zone"].get(),
                "MapID": int(self.editor_fields["MapID"].get()),
                "Gait": self.gait_map[self.editor_fields["Gait"].get()],
                "NavMode": self.nav_mode_map[self.editor_fields["NavMode"].get()],
                "Speed": self.speed_map[self.editor_fields["Speed"].get()],
                "Terrain": self.terrain_map[self.editor_fields["Terrain"].get()],
                "PointInfo": self.point_info_map[self.editor_fields["PointInfo"].get()],
                "ObsMode": self.obs_mode_map[self.editor_fields["ObsMode"].get()],
                "Manner": self.manner_map[self.editor_fields["Manner"].get()],
                "Posture": self.posture_map[self.editor_fields["Posture"].get()],
                "PosX": float(self.editor_fields["PosX"].get()),
                "PosY": float(self.editor_fields["PosY"].get()),
                "PosZ": float(self.editor_fields["PosZ"].get()),
                "AngleYaw": float(self.editor_fields["AngleYaw"].get()),
                "Value": 0,
                "CamPTZ": cam_ptz
            }
            
            # Add or Update
            if self.selected_wp_idx is not None:
                self.path_nodes[self.selected_wp_idx] = node
                self.status_label.configure(text=f"Updated point: {node['Node_info']}")
            elif hasattr(self, 'insert_idx') and self.insert_idx is not None:
                self.path_nodes.insert(self.insert_idx, node)
                self.status_label.configure(text=f"Inserted new point: {node['Node_info']}")
                self.insert_idx = None # Reset
            else:
                self.path_nodes.append(node)
                self.status_label.configure(text=f"Added new point: {node['Node_info']}")
            
            # Save to file (Sandboxing: always save to tmp to protect originals)
            json_file = self.json_path_var.get()
            if json_file:
                # Determine tmp path
                script_dir = os.path.dirname(os.path.abspath(__file__))
                tmp_dir = os.path.join(script_dir, "../tmp")
                if not os.path.exists(tmp_dir):
                    os.makedirs(tmp_dir)
                
                # If not already in a 'tmp' folder, redirect
                if "tmp" not in os.path.dirname(json_file):
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    base_name = os.path.splitext(os.path.basename(json_file))[0]
                    filename = f"{base_name}_edit_{timestamp}.json"
                    json_file = os.path.join(tmp_dir, filename)
                    self.json_path_var.set(json_file) # Update UI to reflect the "Live" file in tmp
                    self.status_label.configure(text=f"Protection: Redirected save to {json_file}")

                # Re-index Value for all nodes sequentially before saving
                for i, n in enumerate(self.path_nodes):
                    n['Value'] = i

                with open(json_file, 'w') as f:
                    json.dump(self.path_nodes, f, indent=4)
                self.status_label.configure(text=f"Saved point: {node['Node_info']} to {os.path.basename(json_file)}")
            
            # Refresh visualization
            self.precalculate_path_base_maps()
            self.render_initial_map()
            
        except Exception as e:
            self.status_label.configure(text=f"Save Error: {e}")
        
        
        # Inspection Photo Frame (Initially Hidden)
        self.image_frame = ctk.CTkFrame(self.sidebar, fg_color="#b71836", corner_radius=0)
        # self.image_frame is not packed yet
        
        self.image_label = ctk.CTkLabel(self.image_frame, text="")
        self.image_label.pack(fill="both", expand=True)

    def set_sidebar_mode(self, mode):
        self.sidebar_mode = mode
        if mode == "info":
            self.editor_master_frame.pack_forget()
            self.info_frame.pack(fill="both", expand=True)
        else:
            self.info_frame.pack_forget()
            self.editor_master_frame.pack(fill="both", expand=True)

    def update_sidebar(self, idx):
        # Reset Layout
        if hasattr(self, 'image_frame'):
            self.image_frame.pack_forget()
        
        if idx is None or idx >= len(self.path_nodes):
            if self.sidebar_mode == "info":
                self.info_text.configure(state="normal")
                self.info_text.delete("1.0", "end")
                self.info_text.configure(state="disabled")
            return

        current_node = self.path_nodes[idx]
        
        if self.sidebar_mode == "info":
            # --- Informational View ---
            self.info_text.configure(state="normal")
            self.info_text.delete("1.0", "end")
            self.info_text.insert("end", "=== CURRENT WAYPOINT ===\n", "header")
            self.info_text.insert("end", json.dumps(current_node, indent=2) + "\n\n")
            
            # Neighbors
            if idx > 0:
                prev = self.path_nodes[idx-1]
                self.info_text.insert("end", f"Previous: {prev.get('Node_info')}\n")
            if idx < len(self.path_nodes) - 1:
                nxt = self.path_nodes[idx+1]
                self.info_text.insert("end", f"Next: {nxt.get('Node_info')}\n")

            self.info_text.tag_config("header", foreground="#00264d")
            self.info_text.configure(state="disabled")

            # Image logic
            pic_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../resource/maps/picture')
            node_info = current_node.get('Node_info', '')
            matched_file = None
            if os.path.exists(pic_dir) and node_info:
                for f in os.listdir(pic_dir):
                    if f.lower().endswith(('.png', '.jpg', '.jpeg')) and node_info.lower() in f.lower():
                        matched_file = os.path.join(pic_dir, f)
                        break
            
            if matched_file:
                try:
                    pil_img = Image.open(matched_file)
                    max_w, max_h = 380, 450
                    curr_w, curr_h = pil_img.size
                    ratio = min(max_w / curr_w, max_h / curr_h)
                    new_w, new_h = int(curr_w * ratio), int(curr_h * ratio)
                    pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    img_tk = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(new_w, new_h))
                    self.image_label.configure(image=img_tk, text="")
                    self.image_label.image = img_tk
                    self.image_frame.pack(pady=20, padx=20, fill="both", expand=True)
                except: pass
        else:
            # --- Editor View ---
            self.populate_editor_fields(current_node)

    def populate_editor_fields(self, node):
        self.editor_fields["Node_info"].delete(0, "end")
        self.editor_fields["Node_info"].insert(0, str(node.get("Node_info", "")))
        self.editor_fields["MapID"].delete(0, "end")
        self.editor_fields["MapID"].insert(0, str(node.get("MapID", 0)))
        self.editor_fields["MapName"].delete(0, "end")
        self.editor_fields["MapName"].insert(0, str(node.get("MapName", "")))
        self.editor_fields["Zone"].delete(0, "end")
        self.editor_fields["Zone"].insert(0, str(node.get("Zone", "")))
        self.editor_fields["PosX"].delete(0, "end")
        self.editor_fields["PosX"].insert(0, f"{node.get('PosX', 0):.4f}")
        self.editor_fields["PosY"].delete(0, "end")
        self.editor_fields["PosY"].insert(0, f"{node.get('PosY', 0):.4f}")
        self.editor_fields["PosZ"].delete(0, "end")
        self.editor_fields["PosZ"].insert(0, f"{node.get('PosZ', 0):.4f}")
        self.editor_fields["AngleYaw"].delete(0, "end")
        self.editor_fields["AngleYaw"].insert(0, f"{node.get('AngleYaw', 0):.4f}")

        # Dropdowns
        self.editor_fields["Gait"].set(self.gait_rev_map.get(node.get("Gait", 0), "Walking"))
        self.editor_fields["NavMode"].set(self.nav_mode_rev_map.get(node.get("NavMode", 0), "Straight"))
        self.editor_fields["Speed"].set(self.speed_rev_map.get(node.get("Speed", 0), "Normal"))
        self.editor_fields["Terrain"].set(self.terrain_rev_map.get(node.get("Terrain", 0), "Solid"))
        self.editor_fields["PointInfo"].set(self.point_info_rev_map.get(node.get("PointInfo", 0), "Transition"))
        self.editor_fields["ObsMode"].set(self.obs_mode_rev_map.get(node.get("ObsMode", 0), "Enable"))
        self.editor_fields["Manner"].set(self.manner_rev_map.get(node.get("Manner", 0), "Forward"))
        self.editor_fields["Posture"].set(self.posture_rev_map.get(node.get("Posture", 0), "Normal"))

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

    def toggle_edit_controls(self, event=None):
        if self.edit_controls_visible:
            self.edit_controls_row.pack_forget()
            self.edit_controls_visible = False
            self.set_edit_mode("none")
            self.menu_buttons["Edit"].configure(fg_color="#00264d")
        else:
            self.edit_controls_row.pack(fill="x", padx=10, pady=1)
            self.edit_controls_visible = True
            self.menu_buttons["Edit"].configure(fg_color="#001a35") # Darker when active

    def set_edit_mode(self, mode):
        if self.edit_mode == mode:
            mode = "none" # Toggle off if same clicked
        
        self.edit_mode = mode
        
        # Reset colors
        self.insert_point_btn.configure(fg_color="#b71836")
        self.insert_line_btn.configure(fg_color="#b71836")
        self.edit_point_btn.configure(fg_color="#b71836")
        
        if mode == "insert":
            self.insert_point_btn.configure(fg_color="#90122a")
            self.status_label.configure(text="Append Mode: Click anywhere on map to add point to the end.")
            self.insert_idx = None
            if self.goal_pose_mode == 0:
                self.toggle_goal_pose_mode()
        if mode == "insert_line":
            if self.selected_edge_idx is None:
                self.status_label.configure(text="Please select an edge on the map first (Click a line until it turns blue).")
                self.insert_line_btn.configure(fg_color="#b71836")
                self.edit_mode = "none"
                return
            
            self.insert_line_btn.configure(fg_color="#90122a")
            self.status_label.configure(text=f"Insert Line Mode (Edge {self.selected_edge_idx} selected): Step 1 - Set position.")
            self.insert_idx = self.selected_edge_idx
            if self.goal_pose_mode == 0:
                self.toggle_goal_pose_mode()
        elif mode == "edit_point":
            self.edit_point_btn.configure(fg_color="#90122a")
            # Switch sidebar mode
            self.ensure_sidebar_visible()
            self.set_sidebar_mode("editor")
            self.status_label.configure(text="Edit Mode: Click an existing waypoint on the map to edit.")
        elif mode == "none":
            # Reset modes if necessary
            self.selected_edge_idx = None
            if self.goal_pose_mode != 0:
                self.goal_pose_mode = 0
                self.temp_goal = None
                self.goal_pose_btn.configure(fg_color="gray70", text_color="black")
            self.set_sidebar_mode("info")
            self.status_label.configure(text="Ready.")

    def ensure_sidebar_visible(self):
        if not self.sidebar_visible:
            self.toggle_sidebar()

    def clear_editor_for_new_point(self, name=None):
        self.selected_wp_idx = None # Deselect
        for entry in self.editor_fields.values():
            if isinstance(entry, ctk.CTkEntry):
                entry.delete(0, "end")
        
        # Set defaults
        if name: self.editor_fields["Node_info"].insert(0, name)
        else: self.editor_fields["Node_info"].insert(0, f"Waypoint_{len(self.path_nodes)+1}")
        
        self.editor_fields["MapID"].insert(0, str(self.current_map_id))
        self.editor_fields["MapName"].insert(0, "1st_floor") # Default or dynamic?
        self.editor_fields["Zone"].insert(0, "wet1")
        self.editor_fields["PosZ"].insert(0, "0.0")
        
        # Reset dropdowns to first option
        self.editor_fields["Gait"].set("Walking")
        self.editor_fields["NavMode"].set("Straight")
        self.editor_fields["Speed"].set("Normal")
        self.editor_fields["Terrain"].set("Solid")
        self.editor_fields["PointInfo"].set("Transition")
        self.editor_fields["ObsMode"].set("Enable")
        self.editor_fields["Manner"].set("Forward")
        self.editor_fields["Posture"].set("Normal")

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
        self.update_floor_selector()
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
                
                # Draw all segments of the global path on every map (no MapID gating)
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
                
                # Always draw solid waypoint as arrow (separation by color only)
                cv2.circle(b_map, (int(u), int(v)), 4, color, -1)
                cv2.arrowedLine(b_map, (int(u), int(v)), (end_u, end_v), color, 2, tipLength=0.4)
                    
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

    def export_waypoints(self):
        if not self.path_nodes:
            self.status_label.configure(text="No waypoints to export.")
            return
        file_path = filedialog.asksaveasfilename(initialdir=".", 
                                               defaultextension=".json",
                                               filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(self.path_nodes, f, indent=4)
                self.status_label.configure(text=f"Exported to {os.path.basename(file_path)}")
            except Exception as e:
                self.status_label.configure(text=f"Export failed: {e}")

    def export_as_image(self):
        if not hasattr(self, 'last_frame') or self.last_frame is None:
            self.status_label.configure(text="No map image to export.")
            return
        file_path = filedialog.asksaveasfilename(initialdir=".", 
                                               defaultextension=".png",
                                               filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg")])
        if file_path:
            try:
                cv2.imwrite(file_path, self.last_frame)
                self.status_label.configure(text=f"Image saved to {os.path.basename(file_path)}")
            except Exception as e:
                self.status_label.configure(text=f"Save failed: {e}")

    def show_view_menu(self, event=None):
        if hasattr(self, 'view_menu') and self.view_menu and self.view_menu.winfo_exists():
            self.view_menu.destroy()
            self.view_menu = None
            return
        
        # Calculate position below the "View" button
        btn = self.menu_buttons.get("View")
        if not btn: return
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height() + 5
        
        sections = {
            "Capture": [
                ("Take UI Screenshot", self.screenshot_ui)
            ],
            "Layout": [
                ("Reset View", self.reset_view),
                ("Toggle Sidebar", self.toggle_sidebar)
            ]
        }
        
        self.view_menu = CustomDropdown(self, x, y, sections, width=200)

    def screenshot_ui(self):
        # Determine current window position and size
        try:
            x = self.winfo_rootx()
            y = self.winfo_rooty()
            w = self.winfo_width()
            h = self.winfo_height()
            
            # Offset to skip the blue top navbar (height=60)
            navbar_height = self.navbar_top.winfo_height()
            
            # Bounding box for ImageGrab: (left, top, right, bottom)
            # We add navbar_height to the top coordinate
            bbox = (x, y + navbar_height, x + w, y + h)
            
            file_path = filedialog.asksaveasfilename(initialdir=".", 
                                                   defaultextension=".png",
                                                   title="Save UI Screenshot",
                                                   filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg")])
            if file_path:
                # Give a small delay for the file dialog to disappear from screen
                self.update()
                time.sleep(0.3)
                
                # Capture the screen area
                # Note: On some Linux setups, this might require 'scrot'
                screenshot = ImageGrab.grab(bbox=bbox)
                screenshot.save(file_path)
                self.status_label.configure(text=f"UI Screenshot saved to {os.path.basename(file_path)}")
        except Exception as e:
            self.status_label.configure(text=f"Screenshot failed: {e}")
            print(f"Screenshot Error: {e}")

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

        self.path_nodes = waypoints # Keep all points exactly as they are in the JSON

        if not self.path_nodes:
            print("No valid waypoints found in file.")
            if HAS_GUI and not self.args.headless and hasattr(self, 'status_label'):
                self.status_label.configure(text="No valid waypoints found.")
            return

        # Build list of points so UI dropdown is populated
        if not self.args.headless and HAS_GUI:
            try:
                self.status_label.configure(text=f"Loaded {len(self.path_nodes)} waypoints.")
                self.follow_cb.configure(state="normal")
            except: pass
            
        self.precalculate_path_base_maps()

        # Set initial map
        if self.maps:
            self.switch_to_map(self.path_nodes[0].get('MapID', 0))
            self.render_initial_map()
            self.update_floor_selector()
        else:
            if HAS_GUI and not self.args.headless:
                self.status_label.configure(text=f"Loaded {len(self.path_nodes)} waypoints. Waiting for a valid Map Folder to be loaded.")

    def update_floor_selector(self):
        if not HAS_GUI or self.args.headless: return
        
        # Clear existing buttons
        for btn in self.floor_buttons.values():
            btn.destroy()
        self.floor_buttons = {}
        
        if not self.maps: return
        
        # Clear existing label if it exists to prevent duplicates
        for widget in self.floor_row.winfo_children():
            if isinstance(widget, ctk.CTkLabel) and (widget.cget("text") == "Manual Floor:" or widget.cget("text") == "Floor"):
                widget.destroy()
        
        ctk.CTkLabel(self.floor_row, text="Manual Floor:", text_color="black").pack(side="left", padx=5)
        
        for mid in sorted(self.maps.keys()):
            # Use display name (Floor 1, Floor 2...) or Map index
            btn_text = f"Floor {mid + 1}"
            btn = ctk.CTkButton(self.floor_row, text=btn_text, width=80, height=28,
                               fg_color="gray80", text_color="black",
                               command=lambda m=mid: self.on_floor_btn_click(m))
            btn.pack(side="left", padx=3)
            self.floor_buttons[mid] = btn
            
        # Highlight current
        if self.current_map_id in self.floor_buttons:
            self.floor_buttons[self.current_map_id].configure(fg_color="#00264d", text_color="white")

    def on_floor_btn_click(self, map_id):
        self.switch_to_map(map_id)
        self.render_initial_map() # Force re-render of current state on this floor

    def switch_to_map(self, map_id):
        if map_id not in self.maps:
            map_id = list(self.maps.keys())[0]
            
        self.current_map_id = map_id
        m = self.maps[map_id]
        
        # Highlight floor buttons if they exist
        for mid, btn in self.floor_buttons.items():
            if mid == map_id:
                btn.configure(fg_color="#00264d", text_color="white")
            else:
                btn.configure(fg_color="gray80", text_color="black")

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

    def finalize_simulation(self, status="Finished."):
        self.sim_stop_flag = True
        self.is_paused = False
        
        # Reset GUI controls
        self.start_btn.configure(state="normal")
        self.play_pause_btn.configure(state="disabled", text="Pause")
        self.stop_btn.configure(state="disabled")
        
        self.folder_entry.configure(state="normal")
        self.folder_load_btn.configure(state="normal")
        self.wp_entry.configure(state="normal")
        self.wp_reload_btn.configure(state="normal")
        
        if hasattr(self, 'menu_buttons'):
            if 'Simulate' in self.menu_buttons:
                self.menu_buttons['Simulate'].configure(state="normal")
        
        self.status_label.configure(text=status)
        self.render_initial_map()

    def stop_simulation(self):
        self.finalize_simulation(status="Stopped.")
        
        # Reset selection to the first waypoint (Charge)
        # (Selection menu removed, always starts from 0)
        pass

    def start_simulation(self):
        if not self.base_maps: return
        if self.sim_thread and self.sim_thread.is_alive():
            return
            
        start_idx = 0

        self.sim_stop_flag = False
        self.is_paused = False
        
        # Switch to start map
        start_mid = self.path_nodes[start_idx].get('MapID', 0)
        self.switch_to_map(start_mid)
        
        # Disable controls while running
        self.start_btn.configure(state="disabled")
        self.folder_entry.configure(state="disabled")
        self.folder_load_btn.configure(state="disabled")
        self.wp_entry.configure(state="disabled")
        self.wp_reload_btn.configure(state="disabled")
        self.play_pause_btn.configure(state="normal", text="Pause")
        self.stop_btn.configure(state="normal")
        if hasattr(self, 'menu_buttons') and 'Simulate' in self.menu_buttons:
            self.menu_buttons['Simulate'].configure(state="disabled")
        self.status_label.configure(text="Starting...")

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
        self.destroy()

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
            p1 = self.path_nodes[i]
            p2 = self.path_nodes[i+1]
            u1, v1 = self.world_to_pixel(p1['PosX'], p1['PosY'], self.current_map_id)
            u2, v2 = self.world_to_pixel(p2['PosX'], p2['PosY'], self.current_map_id)
            
            dist = self.point_to_line_dist(px, py, u1, v1, u2, v2)
            if dist < min_dist:
                min_dist = dist
                best_idx = i + 1 # Insert between i and i+1
        return best_idx

    def on_mouse_down(self, event):
        # Hit detection for waypoints
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        
        # Inverse transform: Screen -> Image Pixel
        img_x = (event.x - self.view_state['offset_x']) / self.view_state['zoom']
        img_y = (event.y - self.view_state['offset_y']) / self.view_state['zoom']
        
        if (self.edit_mode == "insert_line" and self.goal_pose_mode == 0) or (self.edit_mode == "none" and self.edit_controls_visible):
            # Try to select an edge
            idx = self.get_closest_edge(img_x, img_y)
            if idx is not None:
                self.selected_edge_idx = idx
                self.status_label.configure(text=f"Edge {idx} selected. You can now use InsertPoint2Line.")
                if hasattr(self, 'last_frame'): self.update_canvas(self.last_frame)
                return
            else:
                if self.edit_mode == "insert_line":
                    self.status_label.configure(text="Please click directly on a line between points to insert.")
                    return
                # If none mode, maybe deselect?
                if self.selected_edge_idx is not None:
                    self.selected_edge_idx = None
                    if hasattr(self, 'last_frame'): self.update_canvas(self.last_frame)

        if self.edit_mode == "insert" and self.goal_pose_mode == 0:
            # Mode set to append
            self.insert_idx = None
            self.toggle_goal_pose_mode()
            return

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
            
            # Display results in Sidebar Editor
            self.ensure_sidebar_visible()
            self.set_sidebar_mode("editor")
            self.selected_wp_idx = None # Ensure we are creating a NEW one based on this pose
            
            self.editor_fields["PosX"].delete(0, "end")
            self.editor_fields["PosX"].insert(0, f"{x:.4f}")
            self.editor_fields["PosY"].delete(0, "end")
            self.editor_fields["PosY"].insert(0, f"{y:.4f}")
            self.editor_fields["AngleYaw"].delete(0, "end")
            self.editor_fields["AngleYaw"].insert(0, f"{yaw:.4f}")
            self.editor_fields["MapID"].delete(0, "end")
            self.editor_fields["MapID"].insert(0, str(self.current_map_id))
            
            # Prompt user to fill Node Info and Save
            self.status_label.configure(text=f"Pose Set. Fill 'Node Info' in Sidebar and click 'Save Point'.")
            
            self.goal_pose_mode = 0
            self.temp_goal = None
            self.goal_pose_btn.configure(fg_color="gray70", text_color="black")
            
            if hasattr(self, 'last_frame'):
                self.update_canvas(self.last_frame)
            return

        hit_found = False
        for i, node in enumerate(self.path_nodes):
            u, v = self.world_to_pixel(node['PosX'], node['PosY'], self.current_map_id)
            dist_center = math.hypot(u - img_x, v - img_y)
            
            # 1. Check if we hit the arrow tip (for rotation) in EditMode
            if self.edit_mode == "edit_point":
                yaw = node.get('AngleYaw', 0)
                arrow_len = 15
                tip_u = u + arrow_len * math.cos(yaw)
                tip_v = v - arrow_len * math.sin(yaw)
                dist_tip = math.hypot(tip_u - img_x, tip_v - img_y)
                
                if dist_tip < 10 / self.view_state['zoom']:
                    self.rotating_wp_idx = i
                    self.selected_wp_idx = i
                    self.update_sidebar(i)
                    self.status_label.configure(text=f"Rotating Waypoint {i}...")
                    hit_found = True
                    break

            # 2. Check if we hit the waypoint center (for dragging or selection)
            if dist_center < 10 / self.view_state['zoom']:
                self.selected_wp_idx = i
                self.update_sidebar(i)
                hit_found = True
                
                # Start dragging if in edit mode
                if self.edit_mode == "edit_point":
                    self.dragging_wp_idx = i
                    self.status_label.configure(text=f"Dragging Waypoint {i}...")
                
                if hasattr(self, 'last_frame'):
                    self.update_canvas(self.last_frame)
                break
        
        if not hit_found:
            if not self.maps: return # Disable panning if no map loaded
            
            # LOCK PANNING: If any edit mode is active, do not allow map dragging
            if self.edit_mode != "none":
                return
            
            self.view_state['dragging'] = True
            self.view_state['drag_start_x'] = event.x
            self.view_state['drag_start_y'] = event.y

    def on_mouse_up(self, event):
        self.view_state['dragging'] = False
        if self.dragging_wp_idx is not None:
            self.status_label.configure(text=f"Repositioned Waypoint {self.dragging_wp_idx}")
            self.dragging_wp_idx = None
        if self.rotating_wp_idx is not None:
            self.status_label.configure(text=f"Rotated Waypoint {self.rotating_wp_idx}")
            self.rotating_wp_idx = None

    def on_mouse_move(self, event):
        img_x = (event.x - self.view_state['offset_x']) / self.view_state['zoom']
        img_y = (event.y - self.view_state['offset_y']) / self.view_state['zoom']

        if self.goal_pose_mode == 2 and self.temp_goal:
            self.temp_goal['current_u'] = img_x
            self.temp_goal['current_v'] = img_y
            if hasattr(self, 'last_frame'):
                self.update_canvas(self.last_frame)
            return

        if self.rotating_wp_idx is not None:
            # Update waypoint orientation based on vector from center to mouse
            node = self.path_nodes[self.rotating_wp_idx]
            u, v = self.world_to_pixel(node['PosX'], node['PosY'], self.current_map_id)
            
            dx = img_x - u
            dy = v - img_y # Image Y is inverted
            
            new_yaw = math.atan2(dy, dx)
            node['AngleYaw'] = new_yaw
            
            # Update sidebar field in real-time
            self.editor_fields["AngleYaw"].delete(0, "end")
            self.editor_fields["AngleYaw"].insert(0, f"{new_yaw:.4f}")
            
            if hasattr(self, 'last_frame'):
                self.precalculate_path_base_maps()
                self.render_initial_map()
            return

        if self.dragging_wp_idx is not None:
            # Update waypoint position in world coordinates
            wx, wy = self.pixel_to_world(img_x, img_y, self.current_map_id)
            node = self.path_nodes[self.dragging_wp_idx]
            node['PosX'] = wx
            node['PosY'] = wy
            
            # Update sidebar fields in real-time
            self.editor_fields["PosX"].delete(0, "end")
            self.editor_fields["PosX"].insert(0, f"{wx:.4f}")
            self.editor_fields["PosY"].delete(0, "end")
            self.editor_fields["PosY"].insert(0, f"{wy:.4f}")
            
            if hasattr(self, 'last_frame'):
                self.precalculate_path_base_maps() # Re-bake waypoints into base maps
                self.render_initial_map()          # Re-draw the base map to canvas
            return

        if self.view_state['dragging']:
            if not self.maps: return
            
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
        if not self.maps: return # Disable zoom if no map loaded
        
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
        if key == 'escape':
            self.on_closing()
        elif key == 'f':
            self.attributes("-fullscreen", not self.attributes("-fullscreen"))
        
        if not self.maps: return # Interaction guards
        
        if key == 'r':
            self.reset_view()
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
            u1, v1 = self.world_to_pixel(p1['PosX'], p1['PosY'], self.current_map_id)
            u2, v2 = self.world_to_pixel(p2['PosX'], p2['PosY'], self.current_map_id)
            cv2.line(frame, (int(u1), int(v1)), (int(u2), int(v2)), (0, 255, 0), 3)

        if i < len(self.path_nodes) - 1:
            p1 = self.path_nodes[i]
            p2 = self.path_nodes[i+1]
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
        
        if self.maps:
            controls = "Controls: [Scroll] Zoom | [Drag] Pan | [Space] Pause"
        else:
            controls = "Controls: [Space] Pause"
        cv2.putText(frame, controls, (50, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

        self.last_frame = frame
        
        # No video output

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
                u, v = self.world_to_pixel(node['PosX'], node['PosY'], self.current_map_id)
                sc_x = int(u * self.view_state['zoom'] + self.view_state['offset_x'])
                sc_y = int(v * self.view_state['zoom'] + self.view_state['offset_y'])
                cv2.circle(disp_frame, (sc_x, sc_y), 15, (0, 0, 255), 2)
                cv2.circle(disp_frame, (sc_x, sc_y), 2, (0, 0, 255), -1)

            # Draw highlight for selected edge (Blue: #00264d -> BGR: (77, 38, 0))
            if self.selected_edge_idx is not None and self.selected_edge_idx < len(self.path_nodes):
                idx = self.selected_edge_idx
                p1 = self.path_nodes[idx-1]
                p2 = self.path_nodes[idx]
                u1, v1 = self.world_to_pixel(p1['PosX'], p1['PosY'], self.current_map_id)
                u2, v2 = self.world_to_pixel(p2['PosX'], p2['PosY'], self.current_map_id)
                
                sx1 = int(u1 * self.view_state['zoom'] + self.view_state['offset_x'])
                sy1 = int(v1 * self.view_state['zoom'] + self.view_state['offset_y'])
                sx2 = int(u2 * self.view_state['zoom'] + self.view_state['offset_x'])
                sy2 = int(v2 * self.view_state['zoom'] + self.view_state['offset_y'])
                
                cv2.line(disp_frame, (sx1, sy1), (sx2, sy2), (77, 38, 0), 4) # Thicker blue line

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
            
            # If changing floor, drive to the transition point on the CURRENT map first
            if m1 != m2:
                u2, v2 = self.world_to_pixel(p2['PosX'], p2['PosY'], m1)
            else:
                u2, v2 = self.world_to_pixel(p2['PosX'], p2['PosY'], m2)

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
                msg = f"Approaching Transition (Flr {m2+1})" if m1 != m2 else "Moving"
                if not self.render_frame_func(u, v, current_yaw, i, msg): break
                
            # Phase 2.5: Handle Map Switch (Elevator/Stairs)
            if m1 != m2:
                for t in range(30): # Wait 1 sec
                     if not self.render_frame_func(u2, v2, current_yaw, i, f"Transitioning to Floor {m2+1}..."): break
                self.switch_to_map(m2)
                # Find new pixel coords on the NEW map to show arrival
                u2, v2 = self.world_to_pixel(p2['PosX'], p2['PosY'], m2)
                if not self.render_frame_func(u2, v2, current_yaw, i, f"Arrived Floor {m2+1}"): break

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
                    # Take screenshot at the middle of inspection
                    if t == 22:
                        if HAS_GUI and not self.args.headless:
                            self.take_ui_screenshot(p2['Node_info'])
                
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
                self.after(0, lambda: self.finalize_simulation(status="Finished."))
        else:
            # If stopped/quit, ensure cleanup is done
            pass

        print("Simulation loop finished.")

    def take_ui_screenshot(self, point_name):
        try:
            # Get window geometry (must be called from main thread or handled carefully)
            # Since we are in the sim thread, we use a simple approach with PIL.ImageGrab
            # If the simulator is the active window, ImageGrab.grab() should capture it.
            # However, specify the box if possible.
            
            # Sanitise filename
            safe_name = "".join([c for c in point_name if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
            save_path = os.path.join(self.takescreen_dir, f"{safe_name}.jpg")
            
            # Get the bounding box of the main window
            x = self.winfo_rootx()
            y = self.winfo_rooty()
            w = self.winfo_width()
            h = self.winfo_height()
            
            # Take screenshot of the window region
            screenshot = ImageGrab.grab(bbox=(x, y, x+w, y+h))
            screenshot.save(save_path, "JPEG", quality=85)
            # print(f"Screenshot saved: {save_path}")
        except Exception as e:
            print(f"Error taking screenshot: {e}")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_map = os.path.join(script_dir, '../resource/maps/Nestle-full')
    default_waypoints = os.path.join(script_dir, '../resource/waypoints/wet_zone_3.json')
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--waypoints', type=str, default=default_waypoints, help='Path to JSON file')
    parser.add_argument('--speed', type=int, default=5)
    parser.add_argument('--map_folder', type=str, default=default_map, help='Folder containing jueying*.pgm and yaml')
    parser.add_argument('--headless', action='store_true')
    args = parser.parse_args()

    app = SimulationApp(args)
    if not args.headless and HAS_GUI:
        app.mainloop()

if __name__ == '__main__':
    main()
