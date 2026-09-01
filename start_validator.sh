#!/bin/bash

# Launcher script for Robotics CAT Inspection Result Validator Web App

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
VALIDATOR_DIR="$SCRIPT_DIR/inspection_validator"

PORT=8088

echo "=========================================================="
echo " Starting Robotics CAT Inspection Result Validator Web App "
echo "=========================================================="

python3 "$VALIDATOR_DIR/server.py" "$PORT"
