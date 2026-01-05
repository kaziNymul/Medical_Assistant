#!/bin/bash
# AWS Bedrock Setup Script for Medical Assistant
# This script helps configure AWS Bedrock for the AI Clinical Documentation Assistant

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  AWS Bedrock Setup for Medical Assistant${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}AWS CLI is not installed. Please install it first:${NC}"
    echo "  curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o 'awscliv2.zip'"
    echo "  unzip awscliv2.zip"
    echo "  sudo ./aws/install"
    exit 1
fi

echo -e "${GREEN}✓ AWS CLI is installed${NC}"
aws --version
echo ""

# Check if AWS is configured
echo -e "${YELLOW}Step 1: Checking AWS Configuration...${NC}"
if aws sts get-caller-identity &> /dev/null; then
    echo -e "${GREEN}✓ AWS CLI is already configured${NC}"
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    CURRENT_USER=$(aws sts get-caller-identity --query Arn --output text)
    echo "  Account ID: $ACCOUNT_ID"
    echo "  Current User: $CURRENT_USER"
else
    echo -e "${YELLOW}AWS CLI is not configured. Let's set it up...${NC}"
    echo ""
    echo "Please run: aws configure"
    echo ""
    echo "You'll need:"
    echo "  - AWS Access Key ID"
    echo "  - AWS Secret Access Key"
    echo "  - Default region (recommended: us-east-1 or us-west-2 for Bedrock)"
    echo "  - Default output format (json)"
    echo ""
    exit 1
fi
echo ""

# Set region
REGION=${AWS_DEFAULT_REGION:-us-east-1}
echo -e "${YELLOW}Step 2: Using Region: ${REGION}${NC}"
echo ""

# Check Bedrock availability
echo -e "${YELLOW}Step 3: Checking Bedrock Service Availability...${NC}"
if aws bedrock list-foundation-models --region $REGION &> /dev/null; then
    echo -e "${GREEN}✓ Bedrock is accessible in ${REGION}${NC}"
else
    echo -e "${RED}✗ Cannot access Bedrock. You may need to:${NC}"
    echo "  1. Enable Bedrock in the AWS Console"
    echo "  2. Request model access in the AWS Bedrock Console"
    echo "  3. Ensure your IAM user has bedrock permissions"
    echo ""
fi
echo ""

# List available models
echo -e "${YELLOW}Step 4: Listing Available Foundation Models...${NC}"
echo ""
echo "Claude Models (Anthropic):"
aws bedrock list-foundation-models --region $REGION \
    --query "modelSummaries[?contains(modelId, 'claude')].{ModelId:modelId, Provider:providerName, Status:modelLifecycle.status}" \
    --output table 2>/dev/null || echo "  (Unable to list - may need model access)"
echo ""

echo "Titan Models (Amazon):"
aws bedrock list-foundation-models --region $REGION \
    --query "modelSummaries[?contains(modelId, 'titan')].{ModelId:modelId, Provider:providerName, Status:modelLifecycle.status}" \
    --output table 2>/dev/null || echo "  (Unable to list - may need model access)"
echo ""

# Check model access status
echo -e "${YELLOW}Step 5: Checking Model Access Status...${NC}"
echo ""

# Models we need for this project
REQUIRED_MODELS=("anthropic.claude-3-5-sonnet-20241022-v2:0" "amazon.titan-embed-text-v2:0")

for MODEL_ID in "${REQUIRED_MODELS[@]}"; do
    echo -n "Checking $MODEL_ID... "
    STATUS=$(aws bedrock get-foundation-model-availability --model-identifier "$MODEL_ID" --region $REGION --query 'modelAvailability.accessStatus' --output text 2>/dev/null || echo "UNKNOWN")
    
    if [ "$STATUS" == "ACCESSIBLE" ]; then
        echo -e "${GREEN}✓ ACCESSIBLE${NC}"
    elif [ "$STATUS" == "UNKNOWN" ]; then
        echo -e "${YELLOW}⚠ Check console for access${NC}"
    else
        echo -e "${RED}✗ $STATUS - Request access in AWS Console${NC}"
    fi
done
echo ""

# Create IAM policy for Bedrock
echo -e "${YELLOW}Step 6: Creating IAM Policy for Bedrock...${NC}"
POLICY_NAME="MedicalAssistantBedrockPolicy"

# Check if policy already exists
if aws iam get-policy --policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}" &> /dev/null; then
    echo -e "${GREEN}✓ Policy ${POLICY_NAME} already exists${NC}"
else
    # Create the policy document
    cat > /tmp/bedrock-policy.json << 'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BedrockInvokeAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
                "arn:aws:bedrock:*::foundation-model/amazon.titan-*"
            ]
        },
        {
            "Sid": "BedrockListAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock:ListFoundationModels",
                "bedrock:GetFoundationModel",
                "bedrock:GetFoundationModelAvailability"
            ],
            "Resource": "*"
        }
    ]
}
EOF

    aws iam create-policy \
        --policy-name $POLICY_NAME \
        --policy-document file:///tmp/bedrock-policy.json \
        --description "Policy for Medical Assistant to access AWS Bedrock" \
        --region $REGION && \
    echo -e "${GREEN}✓ Created policy ${POLICY_NAME}${NC}" || \
    echo -e "${RED}✗ Failed to create policy${NC}"
fi
echo ""

# Create a service user for the application
echo -e "${YELLOW}Step 7: Creating Service User (Optional)...${NC}"
SERVICE_USER="medical-assistant-bedrock"

read -p "Create a dedicated service user for the application? (y/n): " CREATE_USER
if [ "$CREATE_USER" == "y" ]; then
    if aws iam get-user --user-name $SERVICE_USER &> /dev/null; then
        echo -e "${YELLOW}User ${SERVICE_USER} already exists${NC}"
    else
        aws iam create-user --user-name $SERVICE_USER && \
        echo -e "${GREEN}✓ Created user ${SERVICE_USER}${NC}"
    fi
    
    # Attach policy to user
    aws iam attach-user-policy \
        --user-name $SERVICE_USER \
        --policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}" && \
    echo -e "${GREEN}✓ Attached policy to user${NC}"
    
    # Create access keys
    echo ""
    read -p "Create new access keys for ${SERVICE_USER}? (y/n): " CREATE_KEYS
    if [ "$CREATE_KEYS" == "y" ]; then
        echo ""
        echo -e "${YELLOW}⚠ IMPORTANT: Save these credentials securely!${NC}"
        echo "=================================================="
        aws iam create-access-key --user-name $SERVICE_USER
        echo "=================================================="
        echo ""
        echo -e "${YELLOW}Store these in HashiCorp Vault at: secret/medical-assistant/aws${NC}"
        echo ""
    fi
fi
echo ""

# Output configuration summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Configuration Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "AWS Region: $REGION"
echo "Account ID: $ACCOUNT_ID"
echo ""
echo "Required Environment Variables or Vault Secrets:"
echo "  AWS_ACCESS_KEY_ID"
echo "  AWS_SECRET_ACCESS_KEY"
echo "  AWS_REGION=$REGION"
echo ""
echo "Vault Path: secret/medical-assistant/aws"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. If models show 'Request access', go to AWS Bedrock Console"
echo "   https://console.aws.amazon.com/bedrock/home#/modelaccess"
echo "   and request access to Claude 3.5 Sonnet and Titan Embeddings"
echo ""
echo "2. Store credentials in HashiCorp Vault:"
echo "   vault kv put secret/medical-assistant/aws \\"
echo "       aws_access_key_id=YOUR_KEY \\"
echo "       aws_secret_access_key=YOUR_SECRET \\"
echo "       aws_region=$REGION"
echo ""
echo "3. Test the configuration:"
echo "   python -c 'from src.utils.vault import get_secrets; print(get_secrets(\"aws\"))'"
echo ""
echo -e "${GREEN}Setup complete!${NC}"
