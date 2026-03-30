#!/bin/bash

# This script applies the improvements for SSH stability and system limits.
# Run this script with sudo: sudo bash scripts/apply_ssh_stability.sh

echo "Applying SSH server keepalive settings..."
SSHD_CONFIG="/etc/ssh/sshd_config"
if [ -f "$SSHD_CONFIG" ]; then
    # Backup
    cp "$SSHD_CONFIG" "${SSHD_CONFIG}.bak_$(date +%Y%m%d_%H%M%S)"
    
    # Update ClientAliveInterval
    if grep -q "^#ClientAliveInterval" "$SSHD_CONFIG"; then
        sed -i 's/^#ClientAliveInterval.*/ClientAliveInterval 60/' "$SSHD_CONFIG"
    elif grep -q "^ClientAliveInterval" "$SSHD_CONFIG"; then
        sed -i 's/^ClientAliveInterval.*/ClientAliveInterval 60/' "$SSHD_CONFIG"
    else
        echo "ClientAliveInterval 60" >> "$SSHD_CONFIG"
    fi

    # Update ClientAliveCountMax
    if grep -q "^#ClientAliveCountMax" "$SSHD_CONFIG"; then
        sed -i 's/^#ClientAliveCountMax.*/ClientAliveCountMax 10/' "$SSHD_CONFIG"
    elif grep -q "^ClientAliveCountMax" "$SSHD_CONFIG"; then
        sed -i 's/^ClientAliveCountMax.*/ClientAliveCountMax 10/' "$SSHD_CONFIG"
    else
        echo "ClientAliveCountMax 10" >> "$SSHD_CONFIG"
    fi
    
    echo "Restarting SSH service..."
    systemctl restart ssh
else
    echo "Error: $SSHD_CONFIG not found."
fi

echo "Applying inotify limits..."
SYSCTL_CONF="/etc/sysctl.conf"
if [ -f "$SYSCTL_CONF" ]; then
    # Backup
    cp "$SYSCTL_CONF" "${SYSCTL_CONF}.bak_$(date +%Y%m%d_%H%M%S)"
    
    # Remove existing entries if any
    sed -i '/fs.inotify.max_user_watches/d' "$SYSCTL_CONF"
    sed -i '/fs.inotify.max_user_instances/d' "$SYSCTL_CONF"
    
    # Add new entries
    echo "fs.inotify.max_user_watches=524288" >> "$SYSCTL_CONF"
    echo "fs.inotify.max_user_instances=512" >> "$SYSCTL_CONF"
    
    # Apply changes
    sysctl -p
else
    echo "Error: $SYSCTL_CONF not found."
fi

echo "Stability improvements applied successfully."
