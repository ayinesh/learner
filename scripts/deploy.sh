#!/bin/bash
# Deployment script for Learner App on VPS
# Usage: ./scripts/deploy.sh [setup|deploy|update|logs|backup|ssl]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="${APP_DIR:-/opt/learner}"
COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="${BACKUP_DIR:-/opt/learner/backups}"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Please run as root or with sudo"
        exit 1
    fi
}

# Initial server setup
setup() {
    check_root
    log_info "Setting up server for deployment..."

    # Update system
    apt-get update && apt-get upgrade -y

    # Install Docker if not present
    if ! command -v docker &> /dev/null; then
        log_info "Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
        systemctl enable docker
        systemctl start docker
    fi

    # Install Docker Compose if not present
    if ! command -v docker-compose &> /dev/null; then
        log_info "Installing Docker Compose..."
        apt-get install -y docker-compose-plugin
    fi

    # Install other utilities
    apt-get install -y git curl htop ufw fail2ban

    # Configure firewall
    log_info "Configuring firewall..."
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow ssh
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable

    # Create app directory
    mkdir -p "$APP_DIR"
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$APP_DIR/nginx/ssl"
    mkdir -p "$APP_DIR/nginx/certbot"

    log_info "Server setup complete!"
    log_info "Next steps:"
    echo "  1. Clone your repository to $APP_DIR"
    echo "  2. Copy .env.prod.example to .env and configure"
    echo "  3. Run: ./scripts/deploy.sh deploy"
}

# Deploy the application
deploy() {
    log_info "Deploying application..."

    cd "$APP_DIR"

    # Check for .env file
    if [ ! -f ".env" ]; then
        log_error ".env file not found! Copy .env.prod.example to .env and configure it."
        exit 1
    fi

    # Pull latest images
    log_info "Pulling Docker images..."
    docker compose -f "$COMPOSE_FILE" pull

    # Build application
    log_info "Building application..."
    docker compose -f "$COMPOSE_FILE" build

    # Start services
    log_info "Starting services..."
    docker compose -f "$COMPOSE_FILE" up -d

    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    sleep 10

    # Check service status
    docker compose -f "$COMPOSE_FILE" ps

    log_info "Deployment complete!"
}

# Update application (pull latest code and redeploy)
update() {
    log_info "Updating application..."

    cd "$APP_DIR"

    # Create backup before update
    backup

    # Pull latest code
    log_info "Pulling latest code..."
    git pull origin main

    # Rebuild and restart only the app service
    log_info "Rebuilding application..."
    docker compose -f "$COMPOSE_FILE" build app

    log_info "Restarting application..."
    docker compose -f "$COMPOSE_FILE" up -d --no-deps app

    log_info "Update complete!"
}

# View logs
logs() {
    cd "$APP_DIR"
    service="${1:-app}"
    docker compose -f "$COMPOSE_FILE" logs -f "$service"
}

# Backup database
backup() {
    log_info "Creating backup..."

    cd "$APP_DIR"
    timestamp=$(date +%Y%m%d_%H%M%S)
    backup_file="$BACKUP_DIR/learner_db_$timestamp.sql"

    # Get database credentials from .env
    source .env

    # Dump PostgreSQL database
    docker compose -f "$COMPOSE_FILE" exec -T postgres \
        pg_dump -U "${POSTGRES_USER:-learner}" "${POSTGRES_DB:-learner_db}" > "$backup_file"

    # Compress backup
    gzip "$backup_file"

    log_info "Backup created: ${backup_file}.gz"

    # Remove backups older than 7 days
    find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete
    log_info "Old backups cleaned up"
}

# Setup SSL with Let's Encrypt
ssl() {
    check_root
    log_info "Setting up SSL certificate..."

    cd "$APP_DIR"

    # Get domain from user
    read -p "Enter your domain name (e.g., learner.example.com): " domain

    if [ -z "$domain" ]; then
        log_error "Domain name is required"
        exit 1
    fi

    # Update nginx.conf with domain
    sed -i "s/yourdomain.com/$domain/g" nginx/nginx.conf

    # Stop nginx temporarily
    docker compose -f "$COMPOSE_FILE" stop nginx

    # Get certificate
    docker run --rm \
        -v "$APP_DIR/nginx/certbot:/var/www/certbot" \
        -v "$APP_DIR/nginx/ssl:/etc/letsencrypt" \
        -p 80:80 \
        certbot/certbot certonly \
        --standalone \
        --email "admin@$domain" \
        --agree-tos \
        --no-eff-email \
        -d "$domain"

    # Restart nginx
    docker compose -f "$COMPOSE_FILE" start nginx

    log_info "SSL certificate installed for $domain"
    log_info "Certificate will auto-renew. Add this to crontab:"
    echo "0 0 * * * cd $APP_DIR && docker compose -f $COMPOSE_FILE --profile ssl up certbot"
}

# Stop all services
stop() {
    log_info "Stopping all services..."
    cd "$APP_DIR"
    docker compose -f "$COMPOSE_FILE" down
    log_info "Services stopped"
}

# Restart all services
restart() {
    log_info "Restarting all services..."
    cd "$APP_DIR"
    docker compose -f "$COMPOSE_FILE" restart
    log_info "Services restarted"
}

# Show status
status() {
    cd "$APP_DIR"
    docker compose -f "$COMPOSE_FILE" ps
}

# Run database migrations
migrate() {
    log_info "Running database migrations..."
    cd "$APP_DIR"
    docker compose -f "$COMPOSE_FILE" --profile tools run --rm migrate
    log_info "Migrations complete"
}

# Main command handler
case "$1" in
    setup)
        setup
        ;;
    deploy)
        deploy
        ;;
    update)
        update
        ;;
    logs)
        logs "$2"
        ;;
    backup)
        backup
        ;;
    ssl)
        ssl
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    migrate)
        migrate
        ;;
    *)
        echo "Learner App Deployment Script"
        echo ""
        echo "Usage: $0 {setup|deploy|update|logs|backup|ssl|stop|restart|status|migrate}"
        echo ""
        echo "Commands:"
        echo "  setup    - Initial server setup (install Docker, configure firewall)"
        echo "  deploy   - Deploy the application"
        echo "  update   - Pull latest code and redeploy"
        echo "  logs     - View application logs (logs [service])"
        echo "  backup   - Backup PostgreSQL database"
        echo "  ssl      - Setup SSL certificate with Let's Encrypt"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  status   - Show service status"
        echo "  migrate  - Run database migrations"
        exit 1
        ;;
esac
