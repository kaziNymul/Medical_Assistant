# Deployment Guide: AI Clinical Documentation Assistant

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose installed
- AWS Account with Bedrock access
- Data already indexed (vector store populated)

### Deploy in 3 Steps

```bash
# 1. Configure environment
cp .env.prod.example .env.prod
nano .env.prod  # Add your AWS credentials

# 2. Make deploy script executable
chmod +x scripts/deploy.sh

# 3. Deploy!
./scripts/deploy.sh deploy
```

---

## 📋 Deployment Options

### Option 1: Docker Compose (Recommended for Single Server)

```bash
# Full deployment
./scripts/deploy.sh deploy

# Just build images
./scripts/deploy.sh build

# Start services (after build)
./scripts/deploy.sh start

# View logs
./scripts/deploy.sh logs

# Stop services
./scripts/deploy.sh stop
```

### Option 2: Manual Docker Commands

```bash
# Build
docker-compose -f docker-compose.prod.yml build

# Start
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f backend
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Production Architecture                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│   ┌─────────┐     ┌──────────┐     ┌─────────────────────┐  │
│   │ Browser │────▶│  Nginx   │────▶│  Frontend (React)   │  │
│   └─────────┘     │  :80/443 │     │  :3000              │  │
│                   └────┬─────┘     └─────────────────────┘  │
│                        │                                     │
│                        │ /api/*                              │
│                        ▼                                     │
│              ┌─────────────────────┐                        │
│              │   Backend (FastAPI) │                        │
│              │   :8000             │                        │
│              └──────────┬──────────┘                        │
│                         │                                    │
│         ┌───────────────┼───────────────┐                   │
│         ▼               ▼               ▼                   │
│   ┌──────────┐   ┌────────────┐   ┌──────────┐             │
│   │  Vault   │   │   FAISS    │   │ PII DB   │             │
│   │  :8200   │   │ (vectors)  │   │ (SQLite) │             │
│   └──────────┘   └────────────┘   └──────────┘             │
│         │                                                    │
│         ▼                                                    │
│   ┌──────────────────────────────────────┐                  │
│   │         AWS Bedrock (Cloud)          │                  │
│   │  • Claude 3 Haiku (LLM)              │                  │
│   │  • Titan Embed V2 (Embeddings)       │                  │
│   └──────────────────────────────────────┘                  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔐 Security Configuration

### 1. Vault Secrets Setup

After deployment, verify Vault secrets:

```bash
# Check Vault status
docker exec medical-vault vault status

# List secrets
docker exec medical-vault vault kv get secret/medical-assistant
```

### 2. SSL/TLS (Production)

For HTTPS, add your certificates:

```bash
# Create SSL directory
mkdir -p config/ssl

# Add your certificates
cp /path/to/cert.pem config/ssl/
cp /path/to/key.pem config/ssl/

# Start with nginx proxy
docker-compose -f docker-compose.prod.yml --profile with-proxy up -d
```

### 3. Firewall Rules

```bash
# Allow only necessary ports
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw deny 8000/tcp   # Block direct backend access
sudo ufw deny 8200/tcp   # Block direct Vault access
```

---

## 📊 Monitoring

### Health Checks

```bash
# Backend health
curl http://localhost:8000/health

# Frontend health  
curl http://localhost:3000/health

# Vault health
curl http://localhost:8200/v1/sys/health
```

### Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend

# Last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail=100 backend
```

### Resource Usage

```bash
# Container stats
docker stats medical-backend medical-frontend medical-vault
```

---

## 🔄 Updates & Maintenance

### Rolling Update

```bash
# Pull latest code
git pull origin main

# Rebuild and restart with zero downtime
docker-compose -f docker-compose.prod.yml build backend
docker-compose -f docker-compose.prod.yml up -d --no-deps backend
```

### Backup

```bash
# Backup PII database
docker cp medical-backend:/app/data/pii/pii_mapping.db ./backups/

# Backup vector store
docker cp medical-backend:/app/data/vector_store ./backups/

# Backup Vault data
docker cp medical-vault:/vault/data ./backups/vault/
```

### Restore

```bash
# Restore PII database
docker cp ./backups/pii_mapping.db medical-backend:/app/data/pii/

# Restart to pick up changes
docker-compose -f docker-compose.prod.yml restart backend
```

---

## ☁️ Cloud Deployment Options

### AWS EC2

```bash
# 1. Launch EC2 instance (t3.medium minimum)
# 2. Install Docker
sudo yum install -y docker
sudo systemctl start docker

# 3. Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 4. Clone and deploy
git clone <your-repo>
cd medical_assistant
./scripts/deploy.sh deploy
```

### AWS ECS/Fargate

See `docs/aws-ecs-deployment.md` for container orchestration setup.

### Kubernetes

See `docs/kubernetes-deployment.md` for K8s manifests.

---

## 🐛 Troubleshooting

### Backend won't start

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs backend

# Common issues:
# - Vault not ready: Wait for Vault health check
# - Missing AWS credentials: Check .env.prod
# - Port conflict: Change API_PORT
```

### Vault connection failed

```bash
# Verify Vault is running
docker ps | grep vault

# Check Vault logs
docker logs medical-vault

# Reinitialize Vault
docker exec medical-vault vault kv put secret/medical-assistant \
    AWS_ACCESS_KEY_ID="your-key" \
    AWS_SECRET_ACCESS_KEY="your-secret"
```

### Frontend blank page

```bash
# Check build output
docker logs medical-frontend

# Verify API connection
curl http://localhost:8000/health

# Check browser console for CORS errors
```

---

## 📈 Scaling

### Horizontal Scaling (Multiple Backend Instances)

```yaml
# In docker-compose.prod.yml
backend:
  deploy:
    replicas: 3
```

### Load Balancing

Use nginx upstream for multiple backends:

```nginx
upstream backend {
    server backend1:8000;
    server backend2:8000;
    server backend3:8000;
}
```

---

## ✅ Production Checklist

- [ ] AWS credentials configured in Vault
- [ ] SSL certificates installed (for HTTPS)
- [ ] Firewall rules configured
- [ ] Backup strategy implemented
- [ ] Monitoring/alerting set up
- [ ] Log rotation configured
- [ ] Resource limits set in docker-compose
- [ ] Health check endpoints verified
- [ ] CORS origins restricted to production domains
- [ ] Debug mode disabled (`DEBUG=false`)
