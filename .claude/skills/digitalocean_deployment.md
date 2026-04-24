# DigitalOcean Droplet Deployment Guide

## Overview
Deploy trading bot to DigitalOcean Ubuntu 24.04 LTS Droplet ($6/month) for 24/7 autonomous operation.

## Prerequisites
- DigitalOcean account with $200 credits
- SSH key pair (generate locally if needed: `ssh-keygen -t ed25519`)
- Git repo with trading bot code
- Alpaca API keys (paper trading)

## Droplet Configuration
- **OS:** Ubuntu 24.04 LTS
- **Size:** $6/month (1 GB RAM, 25 GB SSD)
- **Region:** New York 3 (nyc3) — closest to Alpaca servers
- **Auth:** SSH key (recommended over password)
- **Monitoring:** Enabled (DigitalOcean built-in)
- **Backups:** Optional (not required for paper trading)

## Step 1: Create Droplet via DigitalOcean Dashboard
1. Log in to DigitalOcean
2. Click "Create" → "Droplets"
3. Select Ubuntu 24.04 LTS
4. Choose $6/month plan (1 GB RAM, 25 GB SSD)
5. Region: New York 3 (nyc3)
6. Authentication: SSH Key
   - If no key exists: Generate new key in dashboard or paste your public key
   - Test locally: `ssh-keygen -t ed25519` (if needed)
7. Hostname: `trading-bot-prod`
8. Click "Create Droplet"
9. **Wait 2–3 minutes for initialization**
10. Copy the public IP address (e.g., 192.0.2.1)

## Step 2: Initial SSH Connection & System Setup
```bash
# SSH into droplet (replace IP)
ssh root@<YOUR-DROPLET-IP>

# Update system packages
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.11 python3.11-venv python3-pip git sqlite3 curl

# Create unprivileged app user (security best practice)
sudo useradd -m -s /bin/bash tradingbot
sudo usermod -aG sudo tradingbot

# Switch to app user
sudo su - tradingbot
```

## Step 3: Clone Repository & Setup Python Environment
```bash
# Clone your repo (use HTTPS or SSH if configured)
git clone https://github.com/<YOUR-USERNAME>/trading-bot-project.git
cd trading-bot-project

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Verify installation
python -c "import alpaca_trade_api; print('✓ Alpaca API installed')"
```

## Step 4: Configure Environment Variables
```bash
# Create .env file in project root
nano .env

# Paste these lines (replace with actual keys):
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
DATABASE_PATH=/home/tradingbot/trading-bot-project/trading_bot.db
LOG_PATH=/home/tradingbot/trading-bot-project/logs/paper_trading.log

# Save: Ctrl+X, Y, Enter
# Verify
cat .env
```

## Step 5: Test Alpaca Connection
```bash
# Activate venv if not already active
source venv/bin/activate

# Test connection
python -c "
import os
from dotenv import load_dotenv
from alpaca_trade_api import REST
load_dotenv()
api = REST()
account = api.get_account()
print(f'✓ Connected to Alpaca')
print(f'  Account Equity: \${account.equity}')
print(f'  Buying Power: \${account.buying_power}')
"

# Expected output: ✓ Connected to Alpaca, Account Equity: $100000, etc.
```

## Step 6: Create Systemd Service for Bot
Create file: `/etc/systemd/system/trading-bot.service`

```bash
sudo nano /etc/systemd/system/trading-bot.service
```

Paste this content:
```ini
[Unit]
Description=Trading Bot Autonomous Paper Trading
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=tradingbot
WorkingDirectory=/home/tradingbot/trading-bot-project
Environment="PATH=/home/tradingbot/trading-bot-project/venv/bin"
ExecStart=/home/tradingbot/trading-bot-project/venv/bin/python live/bot.py
Restart=always
RestartSec=10
StandardOutput=append:/home/tradingbot/trading-bot-project/logs/systemd.log
StandardError=append:/home/tradingbot/trading-bot-project/logs/systemd.log
SyslogIdentifier=trading-bot

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl start trading-bot
sudo systemctl status trading-bot

# Expected: Active (running) since [timestamp]
```

Check logs:
```bash
sudo tail -30 /home/tradingbot/trading-bot-project/logs/systemd.log
```

## Step 7: Create Systemd Service for Dashboard
Create file: `/etc/systemd/system/trading-dashboard.service`

```bash
sudo nano /etc/systemd/system/trading-dashboard.service
```

Paste this content:
```ini
[Unit]
Description=Trading Bot Dashboard API (FastAPI)
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=tradingbot
WorkingDirectory=/home/tradingbot/trading-bot-project
Environment="PATH=/home/tradingbot/trading-bot-project/venv/bin"
ExecStart=/home/tradingbot/trading-bot-project/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=append:/home/tradingbot/trading-bot-project/logs/dashboard.log
StandardError=append:/home/tradingbot/trading-bot-project/logs/dashboard.log
SyslogIdentifier=trading-dashboard

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-dashboard
sudo systemctl start trading-dashboard
sudo systemctl status trading-dashboard

# Expected: Active (running) since [timestamp]
```

Check logs:
```bash
sudo tail -30 /home/tradingbot/trading-bot-project/logs/dashboard.log
```

## Step 8: Configure Firewall (UFW)
```bash
# Set default deny for incoming, allow outgoing
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (critical — do this first)
sudo ufw allow 22/tcp

# Allow dashboard API
sudo ufw allow 8000/tcp

# Enable firewall
sudo ufw enable

# Verify rules
sudo ufw status
# Expected:
# Status: active
# To                         Action      From
# --                         ------      ----
# 22/tcp                     ALLOW       Anywhere
# 8000/tcp                   ALLOW       Anywhere
```

## Step 9: Retrieve Droplet IP & Test Access
```bash
# Get public IP
hostname -I
# Copy the public IP address (e.g., 192.0.2.1)

# From your LOCAL machine (not SSH), test dashboard access:
curl http://<YOUR-DROPLET-IP>:8000/api/health
# Expected response: {"status":"ok","timestamp":"2026-04-24T..."}
```

## Step 10: Verify Both Services Running
```bash
# SSH into droplet, check both services
ssh root@<YOUR-DROPLET-IP>

# Bot status
sudo systemctl status trading-bot

# Dashboard status
sudo systemctl status trading-dashboard

# Both should show: Active (running)
```

## Monitoring & Maintenance

### View Bot Logs (Real-time)
```bash
sudo tail -f /home/tradingbot/trading-bot-project/logs/paper_trading.log
```

### View Systemd Logs
```bash
sudo journalctl -u trading-bot -f          # Bot service logs
sudo journalctl -u trading-dashboard -f    # Dashboard service logs
```

### Restart Services
```bash
sudo systemctl restart trading-bot
sudo systemctl restart trading-dashboard
```

### Check Disk Usage
```bash
df -h
# trading_bot.db should be < 100 MB
```

### Reboot Droplet (if needed)
```bash
sudo reboot
# Services auto-start due to systemd enable
```

## Troubleshooting

### Service Won't Start
```bash
# Check service logs
sudo journalctl -u trading-bot -n 50
sudo journalctl -u trading-dashboard -n 50

# Manually run bot to see errors
source /home/tradingbot/trading-bot-project/venv/bin/activate
cd /home/tradingbot/trading-bot-project
python live/bot.py
```

### Can't Connect to Alpaca
```bash
# Verify .env file exists and has correct keys
cat /home/tradingbot/trading-bot-project/.env

# Test connection manually
python -c "
from alpaca_trade_api import REST
import os
os.environ['APCA_API_KEY_ID'] = 'your_key'
os.environ['APCA_API_SECRET_KEY'] = 'your_secret'
api = REST()
print(api.get_account())
"
```

### Dashboard Not Accessible
```bash
# Check if port 8000 is listening
sudo netstat -tulpn | grep 8000
# Expected: LISTEN 0.0.0.0:8000

# Check firewall
sudo ufw status

# Test from droplet itself
curl http://localhost:8000/api/health
```

### Database Locked Error
```bash
# Check if bot process is running
ps aux | grep "python live/bot.py"

# Only one bot instance should run; kill duplicates if needed
sudo systemctl restart trading-bot
```

## Cost Estimation
- **Droplet:** $6/month
- **Total 4-year cost:** ~$288 (well within $200 credit budget if renewed)
- **Bandwidth:** $0/month (DigitalOcean free outbound for first 250 GB/month)

## Security Notes
- Never commit `.env` to Git
- Rotate Alpaca API keys quarterly
- Use SSH key authentication (not password)
- Keep system packages updated: `sudo apt update && sudo apt upgrade -y`
- Monitor Droplet via DigitalOcean dashboard for resource usage

## Next Steps
1. Droplet created and initialized
2. Both bot and dashboard services running
3. Proceed to Phase 5 validation tests (on cloud instance)
