#!/usr/bin/env python3
import os
import csv
import time
import subprocess
import threading
import rospy
from datetime import datetime
from std_srvs.srv import Trigger, TriggerResponse
from x30_udp_bridge.msg import X30Status

# Networking & Topic Configuration
TARGET_IP = "10.112.190.218"
FEEDBACK_TOPIC = "/x30_feedback/state"

# Generate matching dynamic base names using current timestamp
current_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
CSV_FILENAME = f"network_spatial_log_{current_time_str}.csv"
GRAPH_FILENAME = f"network_spatial_log_{current_time_str}.png"

# In-Memory Telemetry History including Z coordinate
spatial_history = {
    "x": [],
    "y": [],
    "z": [],
    "ping": []
}

# Thread Synchronization Locks
latest_coordinates = {"x": 0.0, "y": 0.0, "z": 0.0}
buffer_lock = threading.Lock()
history_lock = threading.Lock()

# Global figure tracking handle for dynamic updates
matplotlib_figure = None

def ros_topic_callback(msg):
    """Asynchronously streams coordinate arrays from ROS into thread-safe memory."""
    global latest_coordinates
    with buffer_lock:
        latest_coordinates["x"] = msg.pos_x
        latest_coordinates["y"] = msg.pos_y
        latest_coordinates["z"] = msg.pos_z

def execute_single_ping(ip_address):
    """
    Executes network ping and returns execution round-trip latency time in ms.
    Blocks the thread until a response is received or it hits the 3-second timeout.
    """
    # -c 1: Send exactly one packet
    # -W 3: Maximum 3 seconds timeout to trap prolonged connection drops
    cmd = ["ping", "-c", "1", "-W", "3", ip_address]
    try:
        raw_output = subprocess.check_output(
            cmd, 
            stderr=subprocess.STDOUT, 
            universal_newlines=True
        )
        for line in raw_output.splitlines():
            if "time=" in line:
                segments = line.split("time=")
                if len(segments) > 1:
                    ms_string = segments[1].split(" ")[0]
                    return float(ms_string)
    except (subprocess.CalledProcessError, ValueError, IndexError):
        return -1.0  # Signal Drop Indicator
    return -1.0

def primary_logging_loop():
    """
    Main execution loop driven STRICTLY by ping results sequentially.
    NO PING_INTERVAL DELAY: Immediately starts the next ping upon completion.
    """
    global latest_coordinates, spatial_history
    
    file_handle = open(CSV_FILENAME, mode='w', newline='')
    csv_writer = csv.writer(file_handle)
    csv_writer.writerow(['timestamp', 'x', 'y', 'z', 'ping'])
    file_handle.flush()
        
    rospy.loginfo(f"Log initialized -> {CSV_FILENAME}")
    rospy.loginfo("Continuous ping monitoring active. Run 'rosservice call /get_latency_graph' to update map.")

    was_offline = False  # Track state to detect exact reconnection moment

    while not rospy.is_shutdown():
        # Step 1: Ping first (Will wait up to 3 seconds if network drops out)
        ping_result = execute_single_ping(TARGET_IP)
        epoch_timestamp = time.time()

        # Step 2: Grab the exact coordinates right after the ping event concludes
        with buffer_lock:
            x_pos = latest_coordinates["x"]
            y_pos = latest_coordinates["y"]
            z_pos = latest_coordinates["z"]

        # Step 3: Append data points locally to in-memory history lists for 3D graphing
        with history_lock:
            spatial_history["x"].append(x_pos)
            spatial_history["y"].append(y_pos)
            spatial_history["z"].append(z_pos)
            spatial_history["ping"].append(ping_result)

        try:
            # Step 4: Stream and save entries straight to the timestamped CSV file
            csv_writer.writerow([epoch_timestamp, x_pos, y_pos, z_pos, ping_result])
            file_handle.flush()

            # Terminal Logging Logic for Field Monitoring
            if ping_result == -1.0:
                rospy.logwarn(f"[DROP] Signal Lost at Coords: ({x_pos:.2f}, {y_pos:.2f}, {z_pos:.2f})")
                was_offline = True
            else:
                if was_offline:
                    # Highlight the exact spike when the network recovers (e.g., 1000ms+)
                    rospy.logerr(f"[RECONNECTED SPIKE] Signal recovered at Coords: ({x_pos:.2f}, {y_pos:.2f}, {z_pos:.2f}) | Ping: {ping_result} ms")
                    was_offline = False
                else:
                    rospy.loginfo(f"Active Path -> Coords: ({x_pos:.2f}, {y_pos:.2f}, {z_pos:.2f}) | Ping: {ping_result} ms")
                
        except Exception as io_error:
            rospy.logerr(f"Disk Write Exception inside main execution loop: {io_error}")

        # NO TIME.SLEEP HERE: Loop repeats immediately to catch the next network state

    file_handle.close()
    rospy.loginfo(f"Telemetry log completed successfully: {CSV_FILENAME}")

# --- Graphics Rendering & 3D Service Handling ---

def plot_and_save_latency_graph():
    """Renders and updates the spatial 3D scatter latency topography plot."""
    global matplotlib_figure
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  

    with history_lock:
        x_data = list(spatial_history["x"])
        y_data = list(spatial_history["y"])
        z_data = list(spatial_history["z"])
        ping_data = list(spatial_history["ping"])

    if not x_data:
        rospy.logwarn("Trajectory array is currently empty. Cannot update 3D map graph.")
        return False

    if matplotlib_figure is None or not plt.fignum_exists(matplotlib_figure.number):
        matplotlib_figure = plt.figure(figsize=(12, 9))
    else:
        matplotlib_figure.clear()

    ax = matplotlib_figure.add_subplot(111, projection='3d')

    x_connected = [x_data[i] for i in range(len(ping_data)) if ping_data[i] != -1.0]
    y_connected = [y_data[i] for i in range(len(ping_data)) if ping_data[i] != -1.0]
    z_connected = [z_data[i] for i in range(len(ping_data)) if ping_data[i] != -1.0]
    ping_connected = [ping_data[i] for i in range(len(ping_data)) if ping_data[i] != -1.0]

    x_dropped = [x_data[i] for i in range(len(ping_data)) if ping_data[i] == -1.0]
    y_dropped = [y_data[i] for i in range(len(ping_data)) if ping_data[i] == -1.0]
    z_dropped = [z_data[i] for i in range(len(ping_data)) if ping_data[i] == -1.0]

    if len(x_connected) > 0:
        scatter = ax.scatter(x_connected, y_connected, z_connected, c=ping_connected, 
                             cmap='jet', edgecolor='none', alpha=0.8, s=40, label='Connected Signal')
        cbar = matplotlib_figure.colorbar(scatter, ax=ax, pad=0.1)
        cbar.set_label('Network Latency (ms)', rotation=275, labelpad=15)

    if len(x_dropped) > 0:
        ax.scatter(x_dropped, y_dropped, z_dropped, color='red', marker='X', s=150, 
                   edgecolor='black', depthshade=False, label='Absolute Dead Zone (Drop)')

    ax.set_title(f"3D Spatial Network Latency Topography Map ({TARGET_IP})", fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel("Robot Position X (meters)", fontsize=10, labelpad=10)
    ax.set_ylabel("Robot Position Y (meters)", fontsize=10, labelpad=10)
    ax.set_zlabel("Robot Position Z (meters)", fontsize=10, labelpad=10)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper right')
    
    ax.view_init(elev=25, azim=-60)

    plt.savefig(GRAPH_FILENAME, bbox_inches='tight', dpi=150)
    rospy.loginfo(f"Updated 3D plot graph image file saved: {GRAPH_FILENAME}")

    plt.show(block=False)
    plt.pause(0.1)
    return True

def handle_graph_service(request):
    """ROS Service Callback mapping structural data to Trigger service responses."""
    rospy.loginfo("Service request received: Refreshing and saving 3D topology plot map...")
    success_state = plot_and_save_latency_graph()
    
    response = TriggerResponse()
    response.success = success_state
    if success_state:
        response.message = f"3D Graph updated and image exported to: {GRAPH_FILENAME}"
    else:
        response.message = "Failed to update 3D graph. No location values collected inside buffer."
    return response

if __name__ == '__main__':
    try:
        rospy.init_node('spatial_network_analyzer', anonymous=True)
        rospy.Subscriber(FEEDBACK_TOPIC, X30Status, ros_topic_callback)
        rospy.Service('/get_latency_graph', Trigger, handle_graph_service)
        
        primary_logging_loop()
        
    except rospy.ROSInterruptException:
        rospy.loginfo("Performance analysis platform cleanly closed.")