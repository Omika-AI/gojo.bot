#!/bin/bash
# =============================================================================
# Gojo Discord Bot - Management Script
# =============================================================================
# This script helps you start, stop, and manage your Discord bot easily.
#
# Usage:
#   ./manage.sh start    - Start the bot
#   ./manage.sh stop     - Stop the bot
#   ./manage.sh restart  - Restart the bot
#   ./manage.sh status   - Check if bot is running
#   ./manage.sh logs     - View live logs (Ctrl+C to exit)
#   ./manage.sh logs N   - View last N lines of logs
# =============================================================================

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# File paths
PID_FILE="$SCRIPT_DIR/.bot.pid"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/bot.log"

# Colors for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# =============================================================================
# Helper Functions
# =============================================================================

print_status() {
    echo -e "${BLUE}[Gojo Bot]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if bot is currently running
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0  # Running
        else
            # PID file exists but process is not running - clean up
            rm -f "$PID_FILE"
            return 1  # Not running
        fi
    fi
    return 1  # Not running
}

# Get the running bot's PID
get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    fi
}

# =============================================================================
# Main Commands
# =============================================================================

start_bot() {
    print_status "Starting Gojo bot..."

    # Check if already running
    if is_running; then
        print_warning "Bot is already running! (PID: $(get_pid))"
        print_status "Use './manage.sh restart' to restart it."
        return 1
    fi

    # Check if .env file exists
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        print_error ".env file not found!"
        echo ""
        echo "Please create a .env file with your Discord token:"
        echo "  1. Copy the example: cp .env.example .env"
        echo "  2. Edit .env and add your DISCORD_TOKEN"
        echo ""
        return 1
    fi

    # Check if Discord token is set
    if ! grep -q "DISCORD_TOKEN=." "$SCRIPT_DIR/.env" 2>/dev/null; then
        print_error "DISCORD_TOKEN is not set in .env file!"
        echo ""
        echo "Please edit your .env file and add your Discord bot token."
        echo ""
        return 1
    fi

    # Start the bot in the background
    nohup python3 "$SCRIPT_DIR/bot.py" >> "$LOG_FILE" 2>&1 &
    BOT_PID=$!

    # Save the PID
    echo $BOT_PID > "$PID_FILE"

    # Wait a moment and check if it started successfully
    sleep 2

    if is_running; then
        print_success "Bot started successfully! (PID: $BOT_PID)"
        echo ""
        print_status "To view logs: ./manage.sh logs"
        print_status "To stop bot:  ./manage.sh stop"
    else
        print_error "Bot failed to start! Check the logs:"
        echo ""
        tail -20 "$LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop_bot() {
    print_status "Stopping Gojo bot..."

    if ! is_running; then
        print_warning "Bot is not running."
        return 0
    fi

    PID=$(get_pid)

    # Send SIGTERM for graceful shutdown
    kill "$PID" 2>/dev/null

    # Wait for process to stop (max 10 seconds)
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    # Force kill if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        print_warning "Bot didn't stop gracefully, forcing..."
        kill -9 "$PID" 2>/dev/null
    fi

    # Clean up PID file
    rm -f "$PID_FILE"

    print_success "Bot stopped."
}

restart_bot() {
    print_status "Restarting Gojo bot..."
    stop_bot
    sleep 1
    start_bot
}

show_status() {
    echo ""
    echo "====================================="
    echo "       Gojo Bot Status"
    echo "====================================="

    if is_running; then
        PID=$(get_pid)
        echo -e "Status:  ${GREEN}RUNNING${NC}"
        echo "PID:     $PID"
        echo ""

        # Show memory usage if available
        if command -v ps > /dev/null; then
            MEM=$(ps -p "$PID" -o rss= 2>/dev/null | awk '{printf "%.1f MB", $1/1024}')
            echo "Memory:  $MEM"
        fi

        # Show uptime if available
        if command -v ps > /dev/null; then
            UPTIME=$(ps -p "$PID" -o etime= 2>/dev/null | xargs)
            echo "Uptime:  $UPTIME"
        fi
    else
        echo -e "Status:  ${RED}STOPPED${NC}"
    fi

    echo ""
    echo "Log file: $LOG_FILE"
    echo "====================================="
    echo ""
}

show_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        print_warning "No log file found yet. Start the bot first!"
        return 1
    fi

    LINES=${1:-0}  # Default to 0 (meaning follow/live)

    if [ "$LINES" -gt 0 ] 2>/dev/null; then
        # Show last N lines
        print_status "Showing last $LINES lines of logs:"
        echo "-------------------------------------"
        tail -n "$LINES" "$LOG_FILE"
    else
        # Follow logs in real-time
        print_status "Showing live logs (Press Ctrl+C to exit):"
        echo "-------------------------------------"
        tail -f "$LOG_FILE"
    fi
}

show_help() {
    echo ""
    echo "====================================="
    echo "   Gojo Bot - Management Script"
    echo "====================================="
    echo ""
    echo "Usage: ./manage.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start     Start the bot in the background"
    echo "  stop      Stop the running bot"
    echo "  restart   Restart the bot (stop + start)"
    echo "  status    Check if the bot is running"
    echo "  logs      View live logs (Ctrl+C to exit)"
    echo "  logs N    View last N lines of logs"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./manage.sh start      # Start the bot"
    echo "  ./manage.sh status     # Check status"
    echo "  ./manage.sh logs 50    # View last 50 log lines"
    echo ""
}

# =============================================================================
# Main Script Entry Point
# =============================================================================

case "${1:-}" in
    start)
        start_bot
        ;;
    stop)
        stop_bot
        ;;
    restart)
        restart_bot
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "${2:-0}"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        if [ -n "${1:-}" ]; then
            print_error "Unknown command: $1"
        fi
        show_help
        exit 1
        ;;
esac
