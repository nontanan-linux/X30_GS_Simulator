# X30 GS Simulator

A GUI-based Robot Simulator designed for path simulation and waypoint management. This tool is specifically tailored for Nestle Purina layouts, supporting multi-floor environments, inspection point detection, and sequential waypoint reordering.

## Key Features

- **Interactive GUI**: Real-time simulation of robot movement on 2D maps.
- **Multi-floor Support**: Seamlessly switch between different floors (`MapID` 0, 1, 2, etc.) within the same simulation session.
- **Waypoint Management**: Load, reload, and visualize waypoint sequences from JSON files.
- **Inspection Point Detection**: Automatically identifies points (acoustic, visual, thermal, etc.) and performs simulated "inspections" (robot stops and rotates).
- **2D Goal Pose**: Set arbitrary goal positions and orientations directly on the map.
- **Simulation Recording**: Automatically records the simulation session to a `.mp4` video file.
- **Sidebar Information**: Detailed real-time data on current, previous, and next waypoints, including inspection images if available.

## Prerequisites

- Python 3.x
- Dependencies:
  - `customtkinter` (for modern GUI)
  - `Pillow` (PIL) (for image processing)
  - `opencv-python` (cv2)
  - `numpy`
  - `pyyaml`

You can install the dependencies using pip:
```bash
pip install customtkinter Pillow opencv-python numpy pyyaml
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

## Project Structure

- `scripts/`: Contains the main simulation script (`simulate_path.py`) and various utility scripts for waypoint processing.
- `resource/`: Contains map files (`.pgm`, `.yaml`), waypoints (`.json`), and robot assets.
- `config/`: Configuration files for the robot and simulation environment.

## Waypoint Naming Convention

- `viaN`: Sequential via points.
- `viaN_..._crawl`: Crawl points integrated into the sequence.
- `via_2h_...` / `via-h2-...`: Special waypoints excluded from sequential renumbering.
- Inspection points are identified by keywords in `Node_info` (e.g., `acoustic`, `visual`, `thermal`) or `PointInfo: 1`.

---
*Developed for internal use in Nestle Purina robotics projects.*
