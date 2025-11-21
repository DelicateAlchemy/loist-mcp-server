#!/bin/bash
# Cloud SQL Instance Management Script
# Helps start/stop Cloud SQL instances to save costs during development

set -e

PROJECT_ID="loist-music-library"
INSTANCE_NAME="loist-music-library-db"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to check instance status
check_status() {
    local state=$(gcloud sql instances describe "$INSTANCE_NAME" \
        --format="value(state)" \
        --project="$PROJECT_ID" 2>/dev/null || echo "NOT_FOUND")
    
    local activation=$(gcloud sql instances describe "$INSTANCE_NAME" \
        --format="value(settings.activationPolicy)" \
        --project="$PROJECT_ID" 2>/dev/null || echo "UNKNOWN")
    
    echo "$state|$activation"
}

# Function to display current status
show_status() {
    print_info "Checking Cloud SQL instance status..."
    
    local status=$(check_status)
    local state=$(echo "$status" | cut -d'|' -f1)
    local activation=$(echo "$status" | cut -d'|' -f2)
    
    if [ "$state" = "NOT_FOUND" ]; then
        print_error "Instance '$INSTANCE_NAME' not found in project '$PROJECT_ID'"
        exit 1
    fi
    
    echo ""
    echo "Instance: $INSTANCE_NAME"
    echo "State: $state"
    echo "Activation Policy: $activation"
    echo ""
    
    if [ "$state" = "RUNNABLE" ]; then
        print_warning "Instance is RUNNING (costing ~£1.67-2.67/day)"
        echo "  To stop: ./scripts/manage-cloud-sql.sh stop"
    elif [ "$state" = "STOPPED" ] || [ "$activation" = "NEVER" ]; then
        print_success "Instance is STOPPED (only paying for storage ~£0.10-0.20/month)"
        echo "  To start: ./scripts/manage-cloud-sql.sh start"
    else
        print_warning "Instance is in state: $state"
    fi
}

# Function to stop instance
stop_instance() {
    print_info "Stopping Cloud SQL instance '$INSTANCE_NAME'..."
    
    local status=$(check_status)
    local state=$(echo "$status" | cut -d'|' -f1)
    
    if [ "$state" = "STOPPED" ]; then
        print_warning "Instance is already stopped"
        return 0
    fi
    
    gcloud sql instances patch "$INSTANCE_NAME" \
        --activation-policy=NEVER \
        --project="$PROJECT_ID" \
        --quiet
    
    print_success "Instance stop initiated"
    print_info "Instance will stop in a few minutes"
    print_info "While stopped, you only pay for storage (~£0.10-0.20/month)"
    print_info "Use './scripts/manage-cloud-sql.sh status' to check when it's stopped"
}

# Function to start instance
start_instance() {
    print_info "Starting Cloud SQL instance '$INSTANCE_NAME'..."
    
    local status=$(check_status)
    local state=$(echo "$status" | cut -d'|' -f1)
    
    if [ "$state" = "RUNNABLE" ]; then
        print_warning "Instance is already running"
        return 0
    fi
    
    gcloud sql instances patch "$INSTANCE_NAME" \
        --activation-policy=ALWAYS \
        --project="$PROJECT_ID" \
        --quiet
    
    print_success "Instance start initiated"
    print_info "Instance will be ready in 2-3 minutes"
    print_warning "Instance is now costing ~£1.67-2.67/day"
    print_info "Waiting for instance to be ready..."
    
    gcloud sql instances wait "$INSTANCE_NAME" \
        --project="$PROJECT_ID" \
        --timeout=300
    
    print_success "Instance is now RUNNABLE and ready to use"
}

# Function to show usage
show_usage() {
    echo "Cloud SQL Instance Management"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  status    Show current instance status (default)"
    echo "  stop      Stop the instance (saves ~£50-80/month)"
    echo "  start     Start the instance (takes 2-3 minutes)"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0              # Show status"
    echo "  $0 status       # Show status"
    echo "  $0 stop         # Stop instance"
    echo "  $0 start        # Start instance"
    echo ""
    echo "Cost Information:"
    echo "  Running:  ~£50-80/month (~£1.67-2.67/day)"
    echo "  Stopped:   ~£0.10-0.20/month (storage only)"
    echo "  Savings:  ~£50-80/month when stopped"
    echo ""
    echo "For development, use local Docker Compose instead:"
    echo "  docker-compose up -d  # Uses local PostgreSQL (FREE)"
}

# Main script logic
case "${1:-status}" in
    status)
        show_status
        ;;
    stop)
        stop_instance
        ;;
    start)
        start_instance
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac

