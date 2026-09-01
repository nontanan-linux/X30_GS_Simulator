# X30 GS Simulator

A GUI-based Robot Simulator designed for path simulation and waypoint management. This tool is specifically tailored for Nestle Purina layouts, supporting multi-floor environments, inspection point detection, and sequential waypoint reordering.

## Key Features

- **Web-Based Interactive GUI**: Real-time simulation of robot movement accessible directly from a modern web browser via NiceGUI.
- **Local File Management**: Interactive web file uploader for local map images and JSON files, with browser download support for easy import/export.
- **Multi-floor Support**: Seamlessly switch between different floors (`MapID` 0, 1, 2, etc.) within the same simulation session.
- **Waypoint Management**: Load, edit, and visualize waypoint sequences and metadata from JSON files.
- **Inspection Point Detection**: Automatically identifies points (acoustic, visual, thermal, etc.) and performs simulated "inspections" (robot stops and rotates).
- **2D Goal Pose**: Set arbitrary goal positions and orientations directly on the interactive map canvas with smooth zoom and panning.
- **Dijkstra Path Planner**: Built-in pathfinding plugin to calculate and visualize the shortest route between any two nodes on the map.
- **Sidebar Information**: Detailed real-time data on current, previous, and next waypoints, including inspection images if available.

## Prerequisites

- Python 3.x
- Modern web browser (Chrome, Edge, Firefox) to access the UI
- Python library dependencies (listed in `requirements.txt`)

You can install the Python dependencies using pip:
```bash
pip install -r requirements.txt
```


## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/nontanan-linux/X30_GS_Simulator.git
   cd X30_GS_Simulator
   ```
2. Ensure you have the required dependencies installed.

## Usage

### Running the Simulator

To start the simulator with the GUI:
```bash
python3 scripts/simulate_path.py
```

To run in **headless mode** (no GUI, just recording):
```bash
python3 scripts/simulate_path.py --headless --map_folder resource/maps/ --waypoints resource/waypoints/wet_zone_12-1x.json
```

### GUI Controls

- **Mouse Left Click & Drag**: Pan the map.
- **Mouse Wheel**: Zoom in and out.
- **Sidebar >**: Toggle the waypoint information sidebar.
- **Update Map**: Load or refresh the map directory.
- **Select JSON...**: Load a new waypoint sequence.
- **Reload**: Refresh the waypoint data from the currently loaded JSON file.
- **Start / Stop**: Control the simulation playback.
- **2D Goal Pose**: Select this tool, then click on the map to set a position and drag to set the orientation.

**GUI Usage:**
1. Access the planner by clicking the **Planner** button in the top navigation bar, or selecting **Planner View** in the right sidebar.
2. Specify the **Start Node** and **Target Node** by typing their ID/Name, or by selecting a node on the map and clicking **From Map**.
3. (Optional) Check **Go Home Mission**. If checked, the path ignores inspection tasks (treating all nodes as via points) and unlocks heading calculation for Level 1 nodes.
4. Click **🚀 Calculate Dijkstra Path**.
5. The optimal route is visualized instantly as a solid green line on the map (with a green start ring and red target ring). 
   - **Action Points** are highlighted with **Magenta** circles and arrows.
   - **Via Points** are highlighted with **Orange** circles and arrows.
6. The sidebar console displays detailed trajectory steps, including per-leg distances and total accumulated distance.
7. Click **Export Calculated Path** to save the generated trajectory to `resource/path/calc_tracect.json` for deployment.

**Standalone CLI Usage:**
The planner can also be executed headlessly from the terminal to calculate and export routes without opening the simulator GUI:
```bash
python3 scripts/dijkstra_planner.py --start 'nofr' --end 'ChargeIn-final' --nodes resource/nodes.csv --paths resource/paths.csv --export output_route.json
```

## Project Structure

```text
X30_GS_Simulator/
├── config/             # Configuration files for the robot and simulation
├── resource/           # Static assets and database files
│   ├── docs/           # Documentation and architecture details
│   ├── maps/           # Map files (.pgm, .yaml)
│   ├── path/           # Waypoint paths (.json)
│   ├── nodes.csv       # Node database
│   └── paths.csv       # Edge topology
└── scripts/            # Main simulation and utility scripts
```

## Waypoint Naming Convention

- `viaN`: Sequential via points.
- `viaN_..._crawl`: Crawl points integrated into the sequence.
- `via_2h_...` / `via-h2-...`: Special waypoints excluded from sequential renumbering.
- Inspection points are identified by keywords in `Node_info` (e.g., `acoustic`, `visual`, `thermal`) or `PointInfo: 1`.

## Documentation

- [Dynamic Path Planning System for Robotics Cat](resource/docs/DynamicPlanning.md): Detailed software requirements, logical architecture, and mathematical models.
---
*Developed for internal use in Nestle Purina robotics projects.*
