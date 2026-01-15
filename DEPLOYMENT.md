# Learner App - VPS Docker Deployment Guide

Deploy your Learner app to any VPS provider (DigitalOcean, Linode, Vultr, Hetzner, etc.)

## Prerequisites

- A VPS with Ubuntu 22.04+ (minimum 1GB RAM, 2GB recommended)
- A domain name pointed to your server's IP
- SSH access to your server

## Quick Start

### 1. Create a VPS

Choose a provider and create a server:
- **DigitalOcean**: $6/mo for 1GB RAM, $12/mo for 2GB RAM
- **Linode**: $5/mo for 1GB RAM
- **Vultr**: $5/mo for 1GB RAM
- **Hetzner**: €4/mo for 2GB RAM (best value)

### 2. Initial Server Setup

SSH into your server and run:

```bash
# Download the deploy script
curl -o deploy.sh https://raw.githubusercontent.com/YOUR_REPO/learner/main/scripts/deploy.sh
chmod +x deploy.sh

# Run initial setup (installs Docker, configures firewall)
sudo ./deploy.sh setup
```

### 3. Clone and Configure

```bash
# Clone the repository
cd /opt/learner
git clone https://github.com/YOUR_USERNAME/learner.git .

# Copy and edit environment file
cp .env.prod.example .env
nano .env  # Fill in your API keys and passwords
```

**Important `.env` values to set:**
```bash
POSTGRES_PASSWORD=<generate-strong-password>
REDIS_PASSWORD=<generate-strong-password>
JWT_SECRET_KEY=<run: openssl rand -hex 32>
ANTHROPIC_API_KEY=<your-api-key>
```

### 4. Deploy

```bash
# Deploy the application
sudo ./scripts/deploy.sh deploy

# Check status
sudo ./scripts/deploy.sh status
```

### 5. Setup SSL (HTTPS)

```bash
# Get SSL certificate from Let's Encrypt
sudo ./scripts/deploy.sh ssl

# Enter your domain when prompted
```

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │                   VPS                        │
                    │                                              │
  Internet ────────►│  ┌─────────┐      ┌─────────────────────┐   │
       :80/:443     │  │  Nginx  │──────│  FastAPI App (:8000)│   │
                    │  │(reverse │      └──────────┬──────────┘   │
                    │  │ proxy)  │                 │              │
                    │  └─────────┘                 │              │
                    │                    ┌─────────┴─────────┐    │
                    │                    │                   │    │
                    │              ┌─────▼─────┐      ┌──────▼──┐ │
                    │              │ PostgreSQL│      │  Redis  │ │
                    │              │ + pgvector│      │         │ │
                    │              └───────────┘      └─────────┘ │
                    └─────────────────────────────────────────────┘
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `./deploy.sh setup` | Initial server setup |
| `./deploy.sh deploy` | Deploy/start the application |
| `./deploy.sh update` | Pull latest code and redeploy |
| `./deploy.sh stop` | Stop all services |
| `./deploy.sh restart` | Restart all services |
| `./deploy.sh status` | Show service status |
| `./deploy.sh logs [service]` | View logs (app, postgres, redis, nginx) |
| `./deploy.sh backup` | Backup PostgreSQL database |
| `./deploy.sh ssl` | Setup Let's Encrypt SSL |
| `./deploy.sh migrate` | Run database migrations |

## Maintenance

### View Logs

```bash
# All services
./scripts/deploy.sh logs

# Specific service
./scripts/deploy.sh logs app
./scripts/deploy.sh logs postgres
./scripts/deploy.sh logs nginx
```

### Backup Database

```bash
# Manual backup
./scripts/deploy.sh backup

# Backups are stored in /opt/learner/backups/
# Auto-cleanup removes backups older than 7 days
```

### Update Application

```bash
# Pull latest code and redeploy
./scripts/deploy.sh update
```

### SSL Certificate Renewal

Certificates auto-renew. Add to crontab for automatic renewal:

```bash
# Add to root's crontab
sudo crontab -e

# Add this line:
0 0 * * * cd /opt/learner && docker compose -f docker-compose.prod.yml --profile ssl up certbot
```

## Monitoring

### Check Resource Usage

```bash
# Overall system
htop

# Docker containers
docker stats
```

### Health Check

```bash
# API health
curl http://localhost:8000/health

# From outside (with SSL)
curl https://yourdomain.com/health
```

## Troubleshooting

### Services Won't Start

```bash
# Check logs for errors
./scripts/deploy.sh logs

# Check .env file exists and has required values
cat .env | grep -E "(PASSWORD|KEY)"
```

### Database Connection Issues

```bash
# Check if PostgreSQL is healthy
docker compose -f docker-compose.prod.yml ps postgres

# Connect to database manually
docker compose -f docker-compose.prod.yml exec postgres psql -U learner -d learner_db
```

### Out of Memory

```bash
# Check memory usage
free -h

# Consider upgrading VPS or reducing MAX_TOKENS in .env
```

### SSL Issues

```bash
# Check nginx configuration
docker compose -f docker-compose.prod.yml exec nginx nginx -t

# View nginx logs
./scripts/deploy.sh logs nginx
```

## Security Checklist

- [ ] Strong passwords in `.env` (use `openssl rand -hex 32`)
- [ ] Firewall enabled (only 22, 80, 443 open)
- [ ] SSH key authentication (disable password auth)
- [ ] Fail2ban installed and running
- [ ] Regular backups configured
- [ ] SSL/HTTPS enabled
- [ ] `.env` file not in version control

## Cost Estimate

| Provider | Spec | Monthly Cost |
|----------|------|--------------|
| DigitalOcean | 1GB RAM, 25GB SSD | $6 |
| DigitalOcean | 2GB RAM, 50GB SSD | $12 |
| Linode | 1GB RAM, 25GB SSD | $5 |
| Vultr | 1GB RAM, 25GB SSD | $5 |
| Hetzner | 2GB RAM, 20GB SSD | €4 (~$4.50) |

**Plus API costs:**
- Anthropic Claude: ~$3-15/1M tokens (varies by model)
- OpenAI embeddings: ~$0.02/1M tokens
