# SmartBOQ Pro — Deployment Guide

## Production Deployment (Ubuntu 22.04 VPS)

### 1. Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose plugin
sudo apt install docker-compose-plugin -y

# Create app directory
sudo mkdir -p /opt/smartboq-pro
sudo chown $USER:$USER /opt/smartboq-pro
cd /opt/smartboq-pro
```

### 2. Deploy Application

```bash
# Clone repo
git clone https://github.com/your-org/smartboq-pro.git .

# Configure production environment
cp .env.example .env
nano .env
```

**Critical production .env settings:**
```bash
APP_ENV=production
DEBUG=false

# Generate a secure key:
# python -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=<your-64-char-secret>

POSTGRES_PASSWORD=<strong-database-password>
DATABASE_URL=postgresql://smartboq_user:<password>@db:5432/smartboq

ALLOWED_ORIGINS=https://yourdomain.com
```

```bash
# Start production stack
docker compose --profile production up -d

# Verify
docker compose ps
curl http://localhost:8000/health
```

### 3. SSL with Nginx + Certbot

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Certbot auto-updates nginx config. Verify renewal:
sudo certbot renew --dry-run
```

Update `nginx/nginx.conf` for HTTPS:
```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    # ... rest of config
}
server {
    listen 80;
    return 301 https://$host$request_uri;
}
```

### 4. Database Backups

```bash
# Automated daily backup script
cat > /opt/smartboq-pro/scripts/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/smartboq"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
docker compose exec -T db pg_dump \
  -U smartboq_user smartboq \
  | gzip > "$BACKUP_DIR/smartboq_$DATE.sql.gz"
# Keep only last 30 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
echo "Backup completed: smartboq_$DATE.sql.gz"
EOF
chmod +x /opt/smartboq-pro/scripts/backup.sh

# Schedule daily backup at 2 AM
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/smartboq-pro/scripts/backup.sh >> /var/log/smartboq-backup.log 2>&1") | crontab -
```

### 5. Zero-Downtime Updates

```bash
# Pull latest images and restart
cd /opt/smartboq-pro
git pull origin main
docker compose pull
docker compose up -d --remove-orphans
docker compose exec backend alembic upgrade head
```

---

## GitHub Actions Secrets Setup

In your GitHub repository → Settings → Secrets and variables → Actions:

| Secret | Description |
|--------|-------------|
| `DEPLOY_HOST` | Production server IP or hostname |
| `DEPLOY_USER` | SSH username (e.g., ubuntu) |
| `DEPLOY_SSH_KEY` | Private SSH key for deployment |
| `DEPLOY_PORT` | SSH port (default: 22) |

Generate deploy key:
```bash
ssh-keygen -t ed25519 -C "smartboq-deploy" -f ~/.ssh/smartboq_deploy
# Add public key to server: ~/.ssh/authorized_keys
# Add private key as DEPLOY_SSH_KEY secret in GitHub
```

---

## Monitoring & Logs

```bash
# View all logs
docker compose logs -f

# Backend logs only
docker compose logs -f backend

# Database logs
docker compose logs -f db

# Check resource usage
docker stats

# View last 100 errors
docker compose logs backend --since 1h | grep -i error | tail -100
```

---

## Scaling

For high-traffic production deployments:

```yaml
# docker-compose.yml — scale backend
services:
  backend:
    deploy:
      replicas: 3   # Run 3 backend instances
  nginx:
    # nginx.conf upstream already load-balances
```

```bash
docker compose up -d --scale backend=3
```
