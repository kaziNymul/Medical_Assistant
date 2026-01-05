#!/bin/bash
# ==============================================
# Production Deployment Script
# AI Clinical Documentation Assistant
# ==============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker compose.prod.yml"
PROJECT_NAME="medical-assistant"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Medical Assistant Production Deploy  ${NC}"
echo -e "${BLUE}========================================${NC}"

# Function to print status
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    echo -e "\n${BLUE}Checking prerequisites...${NC}"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    print_status "Docker is installed"
    
    # Check Docker Compose
    if ! command -v docker compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi
    print_status "Docker Compose is installed"
    
    # Check if data exists
    if [ ! -d "data/vector_store" ]; then
        print_warning "Vector store not found. Run indexing first!"
    else
        print_status "Vector store found"
    fi
    
    if [ ! -d "data/pii" ]; then
        print_warning "PII database not found"
    else
        print_status "PII database found"
    fi
}

# Load environment
load_environment() {
    echo -e "\n${BLUE}Loading environment...${NC}"
    
    if [ -f ".env.prod" ]; then
        export $(cat .env.prod | grep -v '^#' | xargs)
        print_status "Loaded .env.prod"
    elif [ -f ".env" ]; then
        export $(cat .env | grep -v '^#' | xargs)
        print_status "Loaded .env"
    else
        print_warning "No .env file found, using defaults"
    fi
}

# Build images
build_images() {
    echo -e "\n${BLUE}Building Docker images...${NC}"
    
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME build --no-cache
    
    print_status "Docker images built successfully"
}

# Initialize Vault with secrets
init_vault() {
    echo -e "\n${BLUE}Initializing Vault...${NC}"
    
    # Start Vault first
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d vault
    
    # Wait for Vault to be ready
    echo "Waiting for Vault to start..."
    sleep 5
    
    # Check if secrets already exist
    VAULT_ADDR="http://127.0.0.1:8200"
    VAULT_TOKEN="${VAULT_TOKEN:-prod-vault-token}"
    
    # Write secrets to Vault
    echo "Writing secrets to Vault..."
    
    docker exec medical-vault vault kv put secret/medical-assistant \
        AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-your-access-key}" \
        AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-your-secret-key}" \
        AWS_REGION="${AWS_REGION:-us-east-1}" \
        DATABRICKS_HOST="${DATABRICKS_HOST:-}" \
        DATABRICKS_TOKEN="${DATABRICKS_TOKEN:-}" \
        LLM_PROVIDER="bedrock" 2>/dev/null || true
    
    print_status "Vault initialized with secrets"
}

# Sync data to Databricks
sync_databricks() {
    echo -e "\n${BLUE}Syncing data to Databricks...${NC}"
    
    # Check if sync script exists
    if [ -f "$PROJECT_DIR/scripts/sync_to_databricks.py" ]; then
        # Run sync (dry-run first to show what will happen)
        python3 "$PROJECT_DIR/scripts/sync_to_databricks.py" --dry-run
        
        read -p "Proceed with Databricks sync? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python3 "$PROJECT_DIR/scripts/sync_to_databricks.py"
            print_status "Databricks sync complete"
        else
            print_warning "Databricks sync skipped"
        fi
    else
        print_warning "Databricks sync script not found"
    fi
}

# Deploy services
deploy_services() {
    echo -e "\n${BLUE}Deploying services...${NC}"
    
    # Pull latest images (if using registry)
    # docker compose -f $COMPOSE_FILE -p $PROJECT_NAME pull
    
    # Start all services
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d
    
    print_status "Services deployed"
}

# Wait for health checks
wait_for_health() {
    echo -e "\n${BLUE}Waiting for services to be healthy...${NC}"
    
    # Wait for backend
    echo "Waiting for backend..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            print_status "Backend is healthy"
            break
        fi
        if [ $i -eq 30 ]; then
            print_error "Backend failed to start"
            exit 1
        fi
        sleep 2
    done
    
    # Wait for frontend
    echo "Waiting for frontend..."
    for i in {1..30}; do
        if curl -s http://localhost:3000 > /dev/null 2>&1; then
            print_status "Frontend is healthy"
            break
        fi
        if [ $i -eq 30 ]; then
            print_error "Frontend failed to start"
            exit 1
        fi
        sleep 2
    done
}

# Show status
show_status() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${GREEN}  Deployment Complete!${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    echo -e "\n${BLUE}Services:${NC}"
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME ps
    
    echo -e "\n${BLUE}Access Points:${NC}"
    echo -e "  Frontend:  ${GREEN}http://localhost:3000${NC}"
    echo -e "  Backend:   ${GREEN}http://localhost:8000${NC}"
    echo -e "  API Docs:  ${GREEN}http://localhost:8000/docs${NC}"
    echo -e "  Vault:     ${GREEN}http://localhost:8200${NC}"
    
    echo -e "\n${BLUE}Useful Commands:${NC}"
    echo -e "  View logs:    docker compose -f $COMPOSE_FILE logs -f"
    echo -e "  Stop:         docker compose -f $COMPOSE_FILE down"
    echo -e "  Restart:      docker compose -f $COMPOSE_FILE restart"
}

# Main deployment flow
main() {
    case "${1:-deploy}" in
        deploy)
            check_prerequisites
            load_environment
            build_images
            init_vault
            deploy_services
            wait_for_health
            show_status
            ;;
        deploy-full)
            check_prerequisites
            load_environment
            build_images
            init_vault
            deploy_services
            wait_for_health
            sync_databricks
            show_status
            ;;
        sync-databricks)
            load_environment
            sync_databricks
            ;;
        build)
            build_images
            ;;
        start)
            deploy_services
            wait_for_health
            show_status
            ;;
        stop)
            echo -e "${BLUE}Stopping services...${NC}"
            docker compose -f $COMPOSE_FILE -p $PROJECT_NAME down
            print_status "Services stopped"
            ;;
        restart)
            echo -e "${BLUE}Restarting services...${NC}"
            docker compose -f $COMPOSE_FILE -p $PROJECT_NAME restart
            wait_for_health
            show_status
            ;;
        logs)
            docker compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f
            ;;
        status)
            docker compose -f $COMPOSE_FILE -p $PROJECT_NAME ps
            ;;
        *)
            echo "Usage: $0 {deploy|deploy-full|sync-databricks|build|start|stop|restart|logs|status}"
            echo ""
            echo "Commands:"
            echo "  deploy          - Deploy without Databricks sync"
            echo "  deploy-full     - Deploy + sync to Databricks"
            echo "  sync-databricks - Only sync data to Databricks"
            echo "  build           - Build Docker images"
            echo "  start           - Start services"
            echo "  stop            - Stop services"
            echo "  restart         - Restart services"
            echo "  logs            - View logs"
            echo "  status          - Show service status"
            exit 1
            ;;
    esac
}

main "$@"
