#!/bin/bash
# Tel-Insights Project Runner (Shell Script Version)
# Simple script to run the Tel-Insights project services

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_PATH="$PROJECT_ROOT/src"

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                      TEL-INSIGHTS                            ║"
    echo "║                 Project Runner v2.0                          ║"
    echo "║           Telegram News Aggregation & Analysis              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Check if Python 3.9+ is available
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed or not in PATH"
        return 1
    fi
    
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    print_status "Python version: $python_version"
    
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"; then
        print_error "Python 3.9+ required. Current: $python_version"
        return 1
    fi
    
    return 0
}

# Check if virtual environment exists and activate it
check_venv() {
    if [ -d "$PROJECT_ROOT/venv" ]; then
        print_info "Activating virtual environment..."
        source "$PROJECT_ROOT/venv/bin/activate"
        print_status "Virtual environment activated"
    else
        print_warning "Virtual environment not found. Using system Python."
        print_info "Consider creating one with: python3 -m venv venv"
    fi
}

# Check if .env file exists
check_env() {
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        print_error ".env file not found"
        print_warning "Copy config.env.template to .env and configure it"
        return 1
    fi
    print_status "Environment configuration found"
    return 0
}

# Check if requirements are installed
check_requirements() {
    if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        print_info "Checking Python dependencies..."
        if ! python3 -c "
import pkg_resources
import sys

def check_requirements():
    with open('$PROJECT_ROOT/requirements.txt', 'r') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    missing = []
    for req in requirements:
        try:
            pkg_resources.require(req)
        except:
            missing.append(req.split('==')[0])
    
    if missing:
        print('Missing packages:', ', '.join(missing))
        sys.exit(1)
    else:
        print('All dependencies satisfied')

check_requirements()
"; then
            print_status "All Python dependencies are installed"
        else
            print_error "Some dependencies are missing"
            print_info "Install with: pip install -r requirements.txt"
            return 1
        fi
    fi
    return 0
}

# Initialize database
init_database() {
    print_info "Initializing database..."
    export PYTHONPATH="$SRC_PATH:$PYTHONPATH"
    
    if python3 -c "
from src.shared.database import init_db
try:
    init_db()
    print('Database initialized successfully')
except Exception as e:
    print(f'Database initialization failed: {e}')
    exit(1)
"; then
        print_status "Database initialized"
    else
        print_error "Database initialization failed"
        return 1
    fi
    return 0
}

# Run a single service
run_service() {
    local service_name="$1"
    local module=""
    
    case "$service_name" in
        "aggregator")
            module="aggregator.main"
            ;;
        "ai-analysis")
            module="ai_analysis.main"
            ;;
        "smart-analysis")
            module="smart_analysis.main"
            ;;
        "alerting")
            module="alerting.main"
            ;;
        *)
            print_error "Unknown service: $service_name"
            echo "Available services: aggregator, ai-analysis, smart-analysis, alerting"
            return 1
            ;;
    esac
    
    print_info "Starting $service_name service..."
    export PYTHONPATH="$SRC_PATH:$PYTHONPATH"
    cd "$PROJECT_ROOT"
    
    python3 -m "$module"
}

# Run all services in parallel
run_all_services() {
    print_info "Starting all services..."
    
    # Array to store background process PIDs
    declare -a pids
    
    # Start services in background
    services=("aggregator" "ai-analysis" "smart-analysis" "alerting")
    
    for service in "${services[@]}"; do
        print_info "Starting $service..."
        run_service "$service" &
        pids+=($!)
        sleep 2  # Give each service time to start
    done
    
    print_status "All services started!"
    print_info "Process IDs: ${pids[*]}"
    print_warning "Press Ctrl+C to stop all services"
    
    # Function to cleanup background processes
    cleanup() {
        print_warning "Stopping all services..."
        for pid in "${pids[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid"
            fi
        done
        wait
        print_status "All services stopped"
        exit 0
    }
    
    # Set trap for cleanup on script exit
    trap cleanup SIGINT SIGTERM
    
    # Wait for all background processes
    wait
}

# Show usage information
show_usage() {
    echo "Tel-Insights Project Runner (Shell Script)"
    echo "=========================================="
    echo
    echo "Usage:"
    echo "  $0                           # Run all services"
    echo "  $0 <service_name>           # Run specific service"
    echo "  $0 init                     # Initialize database only"
    echo "  $0 check                    # Run checks only"
    echo
    echo "Available services:"
    echo "  aggregator      - Telegram message aggregator"
    echo "  ai-analysis     - AI analysis service"
    echo "  smart-analysis  - Smart analysis MCP server"
    echo "  alerting        - Telegram bot service"
    echo
    echo "Examples:"
    echo "  $0"
    echo "  $0 aggregator"
    echo "  $0 init"
}

# Run preflight checks
run_checks() {
    print_info "Running preflight checks..."
    echo
    
    check_python || exit 1
    check_venv
    check_env || exit 1
    check_requirements || exit 1
    
    echo
    print_status "All checks passed!"
    return 0
}

# Main script logic
main() {
    print_banner
    
    case "${1:-all}" in
        "check")
            run_checks
            ;;
        "init")
            run_checks
            init_database
            ;;
        "aggregator"|"ai-analysis"|"smart-analysis"|"alerting")
            run_checks
            init_database
            run_service "$1"
            ;;
        "all"|"")
            run_checks
            init_database
            run_all_services
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        *)
            print_error "Unknown command: $1"
            echo
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@" 