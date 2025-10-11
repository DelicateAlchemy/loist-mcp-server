#!/bin/bash

# Google Cloud SQL PostgreSQL Instance Creation Script
# Task 2.2.2: Set up Google Cloud SQL PostgreSQL instance with appropriate tier

set -e  # Exit on any error

# Configuration variables
PROJECT_ID="${GCP_PROJECT_ID:-loist-music-library}"
INSTANCE_ID="loist-music-library-db"
DATABASE_NAME="music_library"
REGION="us-central1"
ZONE="us-central1-a"
MACHINE_TYPE="db-custom-1-3840"
STORAGE_TYPE="SSD"
STORAGE_SIZE="20"
ROOT_PASSWORD="${DB_ROOT_PASSWORD:-$(openssl rand -base64 32)}"
APP_USER="music_library_user"
APP_PASSWORD="${DB_APP_PASSWORD:-$(openssl rand -base64 32)}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if gcloud is installed and authenticated
check_prerequisites() {
    log "Checking prerequisites..."
    
    if ! command -v gcloud &> /dev/null; then
        error "gcloud CLI is not installed. Please install it first: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        error "No active gcloud authentication found. Please run 'gcloud auth login'"
        exit 1
    fi
    
    # Set the project
    gcloud config set project "$PROJECT_ID"
    log "Using project: $PROJECT_ID"
    
    success "Prerequisites check passed"
}

# Check if instance already exists
check_instance_exists() {
    log "Checking if instance already exists..."
    
    if gcloud sql instances describe "$INSTANCE_ID" --quiet 2>/dev/null; then
        warning "Instance $INSTANCE_ID already exists"
        read -p "Do you want to continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "Exiting..."
            exit 0
        fi
    else
        log "Instance $INSTANCE_ID does not exist, proceeding with creation"
    fi
}

# Create the Cloud SQL instance
create_instance() {
    log "Creating Cloud SQL PostgreSQL instance..."
    
    gcloud sql instances create "$INSTANCE_ID" \
        --database-version=POSTGRES_15 \
        --tier="$MACHINE_TYPE" \
        --zone="$ZONE" \
        --storage-type="$STORAGE_TYPE" \
        --storage-size="${STORAGE_SIZE}GB" \
        --storage-auto-increase \
        --backup-start-time=03:00 \
        --maintenance-window-day=SUN \
        --maintenance-window-hour=04 \
        --retained-backups-count=7 \
        --retained-transaction-log-days=7 \
        --enable-point-in-time-recovery \
        --deletion-protection \
        --quiet
    
    success "Instance $INSTANCE_ID created successfully"
}

# Set root password
set_root_password() {
    log "Setting root password..."
    
    gcloud sql users set-password postgres \
        --instance="$INSTANCE_ID" \
        --password="$ROOT_PASSWORD" \
        --quiet
    
    success "Root password set successfully"
}

# Create application database
create_database() {
    log "Creating application database: $DATABASE_NAME"
    
    gcloud sql databases create "$DATABASE_NAME" \
        --instance="$INSTANCE_ID" \
        --quiet
    
    success "Database $DATABASE_NAME created successfully"
}

# Create application user
create_app_user() {
    log "Creating application user: $APP_USER"
    
    gcloud sql users create "$APP_USER" \
        --instance="$INSTANCE_ID" \
        --password="$APP_PASSWORD" \
        --quiet
    
    success "Application user $APP_USER created successfully"
}

# Configure database flags for performance
configure_database_flags() {
    log "Configuring database performance flags..."
    
    gcloud sql instances patch "$INSTANCE_ID" \
        --database-flags="shared_buffers=1GB,work_mem=4MB,maintenance_work_mem=64MB,effective_cache_size=2GB,random_page_cost=1.1,max_connections=100,log_min_duration_statement=1000,log_statement=all,log_connections=on,log_disconnections=on" \
        --quiet
    
    success "Database performance flags configured"
}

# Get connection information
get_connection_info() {
    log "Retrieving connection information..."
    
    # Get the connection name
    CONNECTION_NAME=$(gcloud sql instances describe "$INSTANCE_ID" --format="value(connectionName)")
    
    # Get the public IP
    PUBLIC_IP=$(gcloud sql instances describe "$INSTANCE_ID" --format="value(ipAddresses[0].ipAddress)")
    
    # Get the private IP (if available)
    PRIVATE_IP=$(gcloud sql instances describe "$INSTANCE_ID" --format="value(ipAddresses[1].ipAddress)" 2>/dev/null || echo "N/A")
    
    success "Connection information retrieved"
    
    echo ""
    echo "=========================================="
    echo "  CLOUD SQL INSTANCE CREATED SUCCESSFULLY"
    echo "=========================================="
    echo ""
    echo "Instance Details:"
    echo "  Instance ID: $INSTANCE_ID"
    echo "  Connection Name: $CONNECTION_NAME"
    echo "  Public IP: $PUBLIC_IP"
    echo "  Private IP: $PRIVATE_IP"
    echo "  Region: $REGION"
    echo "  Zone: $ZONE"
    echo "  Machine Type: $MACHINE_TYPE"
    echo "  Storage: ${STORAGE_SIZE}GB $STORAGE_TYPE"
    echo ""
    echo "Database Details:"
    echo "  Database Name: $DATABASE_NAME"
    echo "  Root User: postgres"
    echo "  Root Password: $ROOT_PASSWORD"
    echo "  App User: $APP_USER"
    echo "  App Password: $APP_PASSWORD"
    echo ""
    echo "Connection Strings:"
    echo "  Cloud SQL Proxy: $CONNECTION_NAME"
    echo "  Direct (Public IP): postgresql://$APP_USER:$APP_PASSWORD@$PUBLIC_IP:5432/$DATABASE_NAME"
    echo "  Cloud SQL Proxy: postgresql://$APP_USER:$APP_PASSWORD@localhost:5432/$DATABASE_NAME"
    echo ""
    echo "Next Steps:"
    echo "  1. Save the passwords securely"
    echo "  2. Configure your application to use these credentials"
    echo "  3. Run database migrations"
    echo "  4. Test the connection"
    echo ""
}

# Create environment file
create_env_file() {
    log "Creating environment file..."
    
    cat > .env.database << EOF
# Database Configuration
DB_HOST=$CONNECTION_NAME
DB_NAME=$DATABASE_NAME
DB_USER=$APP_USER
DB_PASSWORD=$APP_PASSWORD
DB_ROOT_PASSWORD=$ROOT_PASSWORD
DB_USE_CLOUD_SQL_PROXY=true

# Connection Details
DB_PUBLIC_IP=$PUBLIC_IP
DB_PRIVATE_IP=$PRIVATE_IP
DB_CONNECTION_NAME=$CONNECTION_NAME

# Instance Details
DB_INSTANCE_ID=$INSTANCE_ID
DB_REGION=$REGION
DB_ZONE=$ZONE
DB_MACHINE_TYPE=$MACHINE_TYPE
EOF
    
    success "Environment file created: .env.database"
    warning "Remember to add .env.database to .gitignore"
}

# Main execution
main() {
    log "Starting Cloud SQL PostgreSQL instance creation..."
    log "Project: $PROJECT_ID"
    log "Instance: $INSTANCE_ID"
    log "Region: $REGION"
    log "Machine Type: $MACHINE_TYPE"
    echo ""
    
    check_prerequisites
    check_instance_exists
    create_instance
    set_root_password
    create_database
    create_app_user
    configure_database_flags
    get_connection_info
    create_env_file
    
    success "Cloud SQL PostgreSQL instance setup completed successfully!"
    log "Instance is ready for use"
}

# Run main function
main "$@"
