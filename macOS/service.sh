#!/bin/bash
# =============================================================================
# Reptilia Habitat Service Manager for macOS
# =============================================================================
#
# Usage:
#   ./service.sh install    - Install and start the service
#   ./service.sh uninstall  - Stop and remove the service
#   ./service.sh start      - Start the service
#   ./service.sh stop       - Stop the service
#   ./service.sh restart    - Restart the service
#   ./service.sh status     - Check service status
#   ./service.sh logs       - View service logs (live)
#   ./service.sh errors     - View error logs (live)
#
# =============================================================================

SERVICE_NAME="com.reptilia.habitat"
PLIST_FILE="com.reptilia.habitat.plist"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SOURCE="${SCRIPT_DIR}/${PLIST_FILE}"
PLIST_DEST="$HOME/Library/LaunchAgents/${PLIST_FILE}"
LOG_FILE="$HOME/Library/Logs/reptilia-habitat.log"
ERROR_LOG="$HOME/Library/Logs/reptilia-habitat-error.log"
VENV_DIR="${SCRIPT_DIR}/.venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

case "$1" in
    install)
        echo -e "${YELLOW}Installing Reptilia Habitat Service...${NC}"

        # Check for virtual environment
        if [ ! -d "$VENV_DIR" ]; then
            echo -e "${YELLOW}Creating virtual environment...${NC}"
            python3 -m venv "$VENV_DIR"
            echo -e "${YELLOW}Installing dependencies...${NC}"
            "$VENV_DIR/bin/pip" install --upgrade pip
            "$VENV_DIR/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt"
        fi

        # Verify venv has required packages
        if ! "$VENV_DIR/bin/python" -c "import pymongo, astral, bleak" 2>/dev/null; then
            echo -e "${YELLOW}Installing missing dependencies...${NC}"
            "$VENV_DIR/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt"
        fi

        # Create LaunchAgents directory if it doesn't exist
        mkdir -p "$HOME/Library/LaunchAgents"

        # Copy plist file
        cp "$PLIST_SOURCE" "$PLIST_DEST"

        # Load the service
        launchctl load "$PLIST_DEST"

        echo -e "${GREEN}Service installed and started!${NC}"
        echo ""
        echo "Logs: $LOG_FILE"
        echo "Errors: $ERROR_LOG"
        echo ""
        echo "Run './service.sh status' to check if it's running"
        ;;

    uninstall)
        echo -e "${YELLOW}Uninstalling Reptilia Habitat Service...${NC}"

        # Unload the service
        launchctl unload "$PLIST_DEST" 2>/dev/null

        # Remove plist file
        rm -f "$PLIST_DEST"

        echo -e "${GREEN}Service uninstalled!${NC}"
        ;;

    start)
        echo -e "${YELLOW}Starting Reptilia Habitat Service...${NC}"
        launchctl start "$SERVICE_NAME"
        echo -e "${GREEN}Service started!${NC}"
        ;;

    stop)
        echo -e "${YELLOW}Stopping Reptilia Habitat Service...${NC}"
        launchctl stop "$SERVICE_NAME"
        echo -e "${GREEN}Service stopped!${NC}"
        ;;

    restart)
        echo -e "${YELLOW}Restarting Reptilia Habitat Service...${NC}"
        launchctl stop "$SERVICE_NAME"
        sleep 2
        launchctl start "$SERVICE_NAME"
        echo -e "${GREEN}Service restarted!${NC}"
        ;;

    status)
        echo -e "${YELLOW}Reptilia Habitat Service Status:${NC}"
        echo ""

        # Check if plist is installed
        if [ -f "$PLIST_DEST" ]; then
            echo -e "Installed: ${GREEN}Yes${NC}"
        else
            echo -e "Installed: ${RED}No${NC}"
            echo "Run './service.sh install' to install"
            exit 1
        fi

        # Check if running
        if launchctl list | grep -q "$SERVICE_NAME"; then
            PID=$(launchctl list | grep "$SERVICE_NAME" | awk '{print $1}')
            if [ "$PID" != "-" ] && [ -n "$PID" ]; then
                echo -e "Running: ${GREEN}Yes (PID: $PID)${NC}"
            else
                echo -e "Running: ${YELLOW}Loaded but not running${NC}"
            fi
        else
            echo -e "Running: ${RED}No${NC}"
        fi

        # Show last log entries
        echo ""
        echo "Last 5 log entries:"
        echo "-------------------"
        if [ -f "$LOG_FILE" ]; then
            tail -5 "$LOG_FILE"
        else
            echo "(no logs yet)"
        fi
        ;;

    logs)
        echo -e "${YELLOW}Viewing Reptilia Habitat logs (Ctrl+C to exit)...${NC}"
        echo ""
        tail -f "$LOG_FILE"
        ;;

    errors)
        echo -e "${YELLOW}Viewing Reptilia Habitat error logs (Ctrl+C to exit)...${NC}"
        echo ""
        tail -f "$ERROR_LOG"
        ;;

    *)
        echo "Reptilia Habitat Service Manager"
        echo ""
        echo "Usage: $0 {install|uninstall|start|stop|restart|status|logs|errors}"
        echo ""
        echo "Commands:"
        echo "  install    - Install and start the service (runs at login)"
        echo "  uninstall  - Stop and remove the service"
        echo "  start      - Start the service"
        echo "  stop       - Stop the service"
        echo "  restart    - Restart the service"
        echo "  status     - Check if service is running"
        echo "  logs       - View service logs (live)"
        echo "  errors     - View error logs (live)"
        exit 1
        ;;
esac
