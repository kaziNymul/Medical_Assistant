#!/bin/bash
# HashiCorp Vault Setup Script for Medical Assistant
# This script helps set up Vault for secrets management

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  HashiCorp Vault Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if Vault is installed
if command -v vault &> /dev/null; then
    echo -e "${GREEN}✓ Vault CLI is installed${NC}"
    vault --version
else
    echo -e "${YELLOW}Vault CLI is not installed. Installing...${NC}"
    
    # Install Vault
    wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
    sudo apt update && sudo apt install vault -y
    
    if command -v vault &> /dev/null; then
        echo -e "${GREEN}✓ Vault CLI installed successfully${NC}"
    else
        echo -e "${RED}Failed to install Vault. Please install manually.${NC}"
        echo "See: https://developer.hashicorp.com/vault/downloads"
        exit 1
    fi
fi
echo ""

# Check for existing Vault server or start dev mode
echo -e "${YELLOW}Step 1: Checking Vault Server...${NC}"

if [ -n "$VAULT_ADDR" ]; then
    echo "VAULT_ADDR is set to: $VAULT_ADDR"
    if vault status &> /dev/null; then
        echo -e "${GREEN}✓ Vault server is running and accessible${NC}"
    else
        echo -e "${YELLOW}Cannot connect to Vault at $VAULT_ADDR${NC}"
    fi
else
    echo -e "${YELLOW}VAULT_ADDR not set.${NC}"
    echo ""
    echo "Options:"
    echo "  1. Start Vault in dev mode (for development/testing)"
    echo "  2. Connect to existing Vault server"
    echo "  3. Exit and set up Vault manually"
    echo ""
    read -p "Choose option (1/2/3): " OPTION
    
    case $OPTION in
        1)
            echo ""
            echo -e "${YELLOW}Starting Vault in dev mode...${NC}"
            echo -e "${RED}⚠ WARNING: Dev mode is NOT for production!${NC}"
            echo ""
            
            # Start Vault in dev mode in background
            nohup vault server -dev -dev-root-token-id="dev-root-token" > /tmp/vault-dev.log 2>&1 &
            VAULT_PID=$!
            sleep 2
            
            export VAULT_ADDR='http://127.0.0.1:8200'
            export VAULT_TOKEN='dev-root-token'
            
            echo "export VAULT_ADDR='http://127.0.0.1:8200'" >> ~/.bashrc
            echo "export VAULT_TOKEN='dev-root-token'" >> ~/.bashrc
            
            echo -e "${GREEN}✓ Vault dev server started (PID: $VAULT_PID)${NC}"
            echo ""
            echo "Environment variables set:"
            echo "  VAULT_ADDR=$VAULT_ADDR"
            echo "  VAULT_TOKEN=$VAULT_TOKEN"
            echo ""
            ;;
        2)
            read -p "Enter Vault address (e.g., http://vault.example.com:8200): " VAULT_ADDR
            export VAULT_ADDR
            read -p "Enter Vault token: " VAULT_TOKEN
            export VAULT_TOKEN
            
            if vault status &> /dev/null; then
                echo -e "${GREEN}✓ Connected to Vault${NC}"
            else
                echo -e "${RED}Cannot connect to Vault at $VAULT_ADDR${NC}"
                exit 1
            fi
            ;;
        3)
            echo "Exiting. Please set VAULT_ADDR and VAULT_TOKEN, then re-run."
            exit 0
            ;;
    esac
fi
echo ""

# Enable KV secrets engine if not already enabled
echo -e "${YELLOW}Step 2: Enabling KV Secrets Engine...${NC}"
if vault secrets list | grep -q "^secret/"; then
    echo -e "${GREEN}✓ KV secrets engine already enabled at secret/${NC}"
else
    vault secrets enable -path=secret kv-v2 && \
    echo -e "${GREEN}✓ Enabled KV secrets engine at secret/${NC}" || \
    echo -e "${YELLOW}KV engine may already exist${NC}"
fi
echo ""

# Create secrets for Medical Assistant
echo -e "${YELLOW}Step 3: Setting up Medical Assistant Secrets...${NC}"
echo ""

# AWS Secrets
echo "Setting up AWS secrets..."
read -p "Enter AWS Access Key ID (or press Enter to skip): " AWS_KEY
if [ -n "$AWS_KEY" ]; then
    read -p "Enter AWS Secret Access Key: " AWS_SECRET
    read -p "Enter AWS Region (default: us-east-1): " AWS_REGION
    AWS_REGION=${AWS_REGION:-us-east-1}
    
    vault kv put secret/medical-assistant/aws \
        aws_access_key_id="$AWS_KEY" \
        aws_secret_access_key="$AWS_SECRET" \
        aws_region="$AWS_REGION" && \
    echo -e "${GREEN}✓ AWS secrets stored${NC}"
fi
echo ""

# Application Secrets
echo "Setting up Application secrets..."
# Generate a random API key
APP_SECRET_KEY=$(openssl rand -hex 32)
read -p "Enter API Key (or press Enter for auto-generated): " CUSTOM_API_KEY
API_KEY=${CUSTOM_API_KEY:-$(openssl rand -hex 16)}

vault kv put secret/medical-assistant/app \
    secret_key="$APP_SECRET_KEY" \
    api_key="$API_KEY" && \
echo -e "${GREEN}✓ Application secrets stored${NC}"
echo ""

# Database (optional for future use)
echo "Setting up Database secrets (optional)..."
read -p "Enter Database URL (or press Enter to skip): " DB_URL
if [ -n "$DB_URL" ]; then
    vault kv put secret/medical-assistant/database \
        url="$DB_URL" && \
    echo -e "${GREEN}✓ Database secrets stored${NC}"
fi
echo ""

# Verify secrets
echo -e "${YELLOW}Step 4: Verifying Secrets...${NC}"
echo ""
echo "Stored secrets:"
vault kv list secret/medical-assistant/ 2>/dev/null || echo "  (no secrets found)"
echo ""

echo "AWS secrets:"
vault kv get -format=json secret/medical-assistant/aws 2>/dev/null | jq '.data.data | keys' || echo "  (not configured)"
echo ""

echo "App secrets:"
vault kv get -format=json secret/medical-assistant/app 2>/dev/null | jq '.data.data | keys' || echo "  (not configured)"
echo ""

# Create .env file for development
echo -e "${YELLOW}Step 5: Creating .env file for Vault connection...${NC}"
cat > /mnt/e/medical_assistant/.env << EOF
# Vault Configuration
VAULT_ADDR=${VAULT_ADDR:-http://127.0.0.1:8200}
VAULT_TOKEN=${VAULT_TOKEN:-dev-root-token}
VAULT_MOUNT_POINT=secret
VAULT_PATH_PREFIX=medical-assistant

# Fallback values (used if Vault is unavailable)
AWS_REGION=${AWS_REGION:-us-east-1}
EOF

echo -e "${GREEN}✓ Created .env file${NC}"
echo ""

# Output summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Setup Complete${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Vault Configuration:"
echo "  VAULT_ADDR: ${VAULT_ADDR:-http://127.0.0.1:8200}"
echo "  Secrets Path: secret/medical-assistant/"
echo ""
echo "Secrets stored at:"
echo "  - secret/medical-assistant/aws"
echo "  - secret/medical-assistant/app"
echo "  - secret/medical-assistant/database (if configured)"
echo ""
echo -e "${YELLOW}To access secrets in Python:${NC}"
echo '  from src.utils.vault import get_secret, get_secrets'
echo '  aws_creds = get_secrets("aws")'
echo '  api_key = get_secret("app", "api_key")'
echo ""
echo -e "${YELLOW}To manually read secrets:${NC}"
echo "  vault kv get secret/medical-assistant/aws"
echo ""
echo -e "${GREEN}Vault setup complete!${NC}"
