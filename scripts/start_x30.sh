#!/bin/bash

# ==========================================
# 1. Environment Setup (Crucial for Systemd Service)
# ==========================================
# Load ROS environment
source /opt/ros/noetic/setup.bash
source /home/ysc/gs_ws/devel/setup.bash

# Set ROS Master URI and Python buffering
export ROS_MASTER_URI=http://localhost:11311
export PYTHONUNBUFFERED=1

# Change to the tool's working directory
cd /home/ysc/gs_ws/src/tools/

# ==========================================
# 2. Log Management (7-Day Retention Policy)
# ==========================================
LOG_DIR="/home/ysc/gs_ws/src/tools/x30_logs"
RETENTION_DAYS=7
TIMESTAMP=$(date +"%Y-%m-%d-%H-%M-%S")
LOG_FILE="$LOG_DIR/log${TIMESTAMP}.txt"

mkdir -p "$LOG_DIR"

cleanup_logs() {
    echo "[Cleanup] Checking for logs older than $RETENTION_DAYS days..." >> "$LOG_FILE"
    # Find and delete log files older than 7 days
    find "$LOG_DIR" -name "log*.txt" -type f -mtime +$((RETENTION_DAYS-1)) -exec echo "[Cleanup] Deleting: {}" \; -exec rm -f {} >> "$LOG_FILE" 2>&1
}

# Run log cleanup immediately on startup
cleanup_logs

# ==========================================
# 3. Helper Functions (Non-blocking Delays)
# ==========================================

# Precision delay using Timestamp (Avoids long blocking sleep)
# Usage: delay_seconds <seconds>
delay_seconds() {
    local seconds=$1
    local end_time=$(( $(date +%s) + seconds ))
    
    echo "[Wait] Delaying for $seconds seconds..." | tee -a "$LOG_FILE"
    
    # Loop until the current timestamp reaches the end_time
    while [ $(date +%s) -lt $end_time ]; do
        # Use a very small sleep (0.1s) to keep CPU usage low 
        # while remaining highly responsive
        sleep 0.1
    done
    
    echo "[Ready] Delay finished." | tee -a "$LOG_FILE"
}

# Wait until ROS Master is online (check port 11311)
wait_for_ros() {
    echo "[Wait] Waiting for ROS Master (Port 11311)..." | tee -a "$LOG_FILE"
    while ! nc -z localhost 11311; do   
        sleep 0.5
    done
    echo "[Ready] ROS Master is online." | tee -a "$LOG_FILE"
}

# Run a command in background and log output
run_node() {
    local cmd=$1
    echo "[Exec] $cmd" >> "$LOG_FILE"
    eval "$cmd" 2>&1 | tee -a "$LOG_FILE" &
}

# ==========================================
# 4. Start ROS Nodes (Sequential based on Timers)
# ==========================================
echo "--------------------------------------------------------" | tee -a "$LOG_FILE"
echo " Starting X30 ROS Service at $TIMESTAMP" | tee -a "$LOG_FILE"
echo "--------------------------------------------------------" | tee -a "$LOG_FILE"

# 4.1 Wait for core ROS system
wait_for_ros

# 4.2 Start Data Collector
run_node "roslaunch gs_data_collector gs_data_collecting.launch.xml"
# Replaced wait_for_topic with timestamp delay
delay_seconds 10

# 4.3 Start UDP Bridge
run_node "roslaunch x30_udp_bridge x30_all.launch.xml"
# Replaced wait_for_topic with timestamp delay
delay_seconds 15

# 4.4 Set initial position once timers expire
echo "[Exec] All systems initialized, setting initial position..." | tee -a "$LOG_FILE"
rosrun x30_udp_bridge auto_initial_position.py 2>&1 | tee -a "$LOG_FILE"

# ==========================================
# 5. Keep Service Alive
# ==========================================
echo "[Status] All nodes are running. Monitoring..." >> "$LOG_FILE"
wait