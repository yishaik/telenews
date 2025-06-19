#!/bin/bash
# Tel-Insights Service Runner for Unix/Linux/macOS
# This script runs Tel-Insights services with proper Python path setup

# Check if service name is provided
if [ $# -eq 0 ]; then
    echo "Tel-Insights Service Runner"
    echo "============================="
    echo ""
    echo "Usage: ./run_service.sh <service_name>"
    echo ""
    echo "Available services:"
    echo "  aggregator      - Telegram message aggregator"
    echo "  ai-analysis     - AI analysis service"
    echo "  smart-analysis  - Smart analysis MCP server"
    echo "  alerting        - Telegram bot service"
    echo ""
    echo "Examples:"
    echo "  ./run_service.sh aggregator"
    echo "  ./run_service.sh ai-analysis"
    echo "  ./run_service.sh smart-analysis"
    echo "  ./run_service.sh alerting"
    exit 1
fi

SERVICE_NAME=$1

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Set Python path to include src directory
export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"

echo "🚀 Starting $SERVICE_NAME service..."
echo "📂 Working directory: $SCRIPT_DIR"
echo "🐍 Python path includes: $SCRIPT_DIR/src"
echo ""

# Run the service using the Python runner
python3 "$SCRIPT_DIR/run_service.py" "$SERVICE_NAME" 