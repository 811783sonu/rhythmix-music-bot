# 🚀 Deployment Guide - Rhythmix X Bot

Complete guide to deploy your Telegram music bot on various platforms.

## 📋 Prerequisites

Before deploying, ensure you have:

1. **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)
2. **API ID & API Hash** from [my.telegram.org](https://my.telegram.org/apps)
3. GitHub account (for Git-based deployments)

---

## 🌐 Deploy to Render (Recommended)

Render offers free tier with 512MB RAM - perfect for this bot.

### Step-by-Step Guide

1. **Fork the Repository**
   - Click "Fork" on the GitHub repository
   - Clone to your account

2. **Create Render Account**
   - Visit [render.com](https://render.com)
   - Sign up with GitHub

3. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select the forked repo

4. **Configure Service**
   ```
   Name: rhythmix-music-bot (or any name)
   Region: Choose closest to you
   Branch: main
   Environment: Docker
   Instance Type: Free
   ```

5. **Set Environment Variables**
   
   Click "Environment" and add:
   ```
   API_ID = 20550203
   API_HASH = 690778a70966c6f3f1fbacb96a49f360
   BOT_TOKEN = 8244422744:AAF0ZSEONT7YTpwKldhLGGpZO_tseXlnmYA
   BOT_NAME = Rhythmix X Bot
   PORT = 8000
   ```

6. **Deploy**
   - Click "Create Web Service"
   - Wait 5-10 minutes for first deployment
   - Check logs for "Bot started successfully!"

### Render Dashboard

- **Logs**: Monitor real-time logs
- **Events**: See deployment history
- **Metrics**: CPU, memory usage
- **Shell**: Access container terminal

---

## 🚂 Deploy to Railway

Railway offers $5 free credit monthly.

### Step-by-Step Guide

1. **Create Railway Account**
   - Visit [railway.app](https://railway.app)
   - Sign in with GitHub

2. **New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your forked repository

3. **Configure Variables**
   
   Go to "Variables" tab:
   ```
   API_ID = 20550203
   API_HASH = 690778a70966c6f3f1fbacb96a49f360
   BOT_TOKEN = 8244422744:AAF0ZSEONT7YTpwKldhLGGpZO_tseXlnmYA
   BOT_NAME = Rhythmix X Bot
   PORT = 8000
   ```

4. **Deploy Settings**
   - Railway auto-detects Dockerfile
   - Start Command: `python main.py`
   - No additional configuration needed

5. **Deploy**
   - Click "Deploy"
   - Monitor logs in dashboard

---

## 💜 Deploy to Heroku

Heroku offers free tier with limitations (550 hours/month).

### Step-by-Step Guide

1. **Install Heroku CLI**
   ```bash
   # macOS
   brew tap heroku/brew && brew install heroku

   # Ubuntu/Debian
   curl https://cli-assets.heroku.com/install.sh | sh

   # Windows
   # Download from heroku.com/downloads
   ```

2. **Login to Heroku**
   ```bash
   heroku login
   ```

3. **Create New App**
   ```bash
   cd telegram-music-bot
   heroku create rhythmix-music-bot
   ```

4. **Set Buildpacks**
   ```bash
   heroku buildpacks:add --index 1 https://github.com/jonathanong/heroku-buildpack-ffmpeg-latest.git
   heroku buildpacks:add --index 2 heroku/python
   ```

5. **Set Environment Variables**
   ```bash
   heroku config:set API_ID=20550203
   heroku config:set API_HASH=690778a70966c6f3f1fbacb96a49f360
   heroku config:set BOT_TOKEN=8244422744:AAF0ZSEONT7YTpwKldhLGGpZO_tseXlnmYA
   heroku config:set BOT_NAME="Rhythmix X Bot"
   ```

6. **Deploy**
   ```bash
   git push heroku main
   ```

7. **Scale Worker**
   ```bash
   heroku ps:scale worker=1
   ```

8. **Check Logs**
   ```bash
   heroku logs --tail
   ```

---

## 🖥️ Deploy on VPS (Ubuntu/Debian)

For full control, deploy on your own VPS.

### Requirements

- Ubuntu 20.04+ or Debian 11+
- Minimum 1GB RAM
- Python 3.9+
- Root or sudo access

### Installation Steps

1. **Update System**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install Dependencies**
   ```bash
   sudo apt install -y python3 python3-pip python3-venv ffmpeg git
   ```

3. **Clone Repository**
   ```bash
   git clone https://github.com/yourusername/telegram-music-bot.git
   cd telegram-music-bot
   ```

4. **Create Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

5. **Install Python Packages**
   ```bash
   pip install -r requirements.txt
   ```

6. **Configure Environment**
   ```bash
   cp .env.example .env
   nano .env
   ```
   
   Add your credentials:
   ```env
   API_ID=20550203
   API_HASH=690778a70966c6f3f1fbacb96a49f360
   BOT_TOKEN=8244422744:AAF0ZSEONT7YTpwKldhLGGpZO_tseXlnmYA
   BOT_NAME=Rhythmix X Bot
   ```

7. **Test Run**
   ```bash
   python main.py
   ```

8. **Setup Systemd Service** (for auto-start)
   
   Create service file:
   ```bash
   sudo nano /etc/systemd/system/musicbot.service
   ```
   
   Add content:
   ```ini
   [Unit]
   Description=Telegram Music Bot
   After=network.target

   [Service]
   Type=simple
   User=youruser
   WorkingDirectory=/path/to/telegram-music-bot
   Environment="PATH=/path/to/telegram-music-bot/venv/bin"
   ExecStart=/path/to/telegram-music-bot/venv/bin/python main.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

9. **Enable and Start Service**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable musicbot
   sudo systemctl start musicbot
   ```

10. **Check Status**
    ```bash
    sudo systemctl status musicbot
    sudo journalctl -u musicbot -f
    ```

---

## 🐳 Deploy with Docker

Universal deployment using Docker.

### Using Docker Compose

1. **Create docker-compose.yml**
   ```yaml
   version: '3.8'
   
   services:
     musicbot:
       build: .
       environment:
         - API_ID=20550203
         - API_HASH=690778a70966c6f3f1fbacb96a49f360
         - BOT_TOKEN=8244422744:AAF0ZSEONT7YTpwKldhLGGpZO_tseXlnmYA
         - BOT_NAME=Rhythmix X Bot
       volumes:
         - ./downloads:/app/downloads
       restart: unless-stopped
   ```

2. **Run**
   ```bash
   docker-compose up -d
   ```

3. **Check Logs**
   ```bash
   docker-compose logs -f
   ```

### Using Docker Directly

```bash
# Build image
docker build -t musicbot .

# Run container
docker run -d \
  --name rhythmix-bot \
  -e API_ID=20550203 \
  -e API_HASH=690778a70966c6f3f1fbacb96a49f360 \
  -e BOT_TOKEN=8244422744:AAF0ZSEONT7YTpwKldhLGGpZO_tseXlnmYA \
  -e BOT_NAME="Rhythmix X Bot" \
  -v $(pwd)/downloads:/app/downloads \
  --restart unless-stopped \
  musicbot

# View logs
docker logs -f rhythmix-bot
```

---

## 🔧 Post-Deployment Configuration

### Make Bot Admin in Groups

1. Add bot to your group
2. Make it admin with these permissions:
   - ✅ Manage Voice Chats
   - ✅ Delete Messages
   - ✅ Invite Users

### Start Voice Chat

1. Open group chat
2. Click ⋮ (three dots)
3. Select "Start Voice Chat"
4. Use `/play` command

### Test Commands

```
/start - Check if bot is running
/play test song - Test playback
/ping - Check latency
```

---

## 📊 Monitoring & Maintenance

### Check Bot Status

**Render/Railway:**
- Dashboard → Logs
- Monitor CPU/RAM usage

**Heroku:**
```bash
heroku logs --tail
heroku ps
```

**VPS:**
```bash
sudo systemctl status musicbot
sudo journalctl -u musicbot -n 100
```

### Update Bot

**Render/Railway:**
- Push changes to GitHub
- Auto-deploys on commit

**Heroku:**
```bash
git push heroku main
```

**VPS:**
```bash
cd telegram-music-bot
git pull
sudo systemctl restart musicbot
```

### Clean Downloads Folder

```bash
# Manually
rm -rf downloads/*

# Or add cron job
crontab -e
# Add: 0 */6 * * * rm -rf /path/to/downloads/*
```

---

## ⚠️ Troubleshooting

### Bot Not Responding

1. Check if bot is running:
   ```bash
   # Render: Check logs
   # VPS: sudo systemctl status musicbot
   ```

2. Verify environment variables
3. Check internet connectivity

### Can't Join Voice Chat

1. Ensure bot is admin in group
2. Voice chat must be started
3. Check PyTgCalls connection

### Audio Not Playing

1. Verify FFmpeg installation:
   ```bash
   ffmpeg -version
   ```

2. Check yt-dlp:
   ```bash
   pip install -U yt-dlp
   ```

3. Test URL manually:
   ```bash
   yt-dlp -f bestaudio "youtube-url"
   ```

### Out of Memory

- Upgrade to paid plan
- Clear downloads folder regularly
- Reduce max queue size in config

---

## 🔒 Security Best Practices

1. **Never commit .env file**
   ```bash
   # Already in .gitignore
   ```

2. **Use environment variables**
   - Never hardcode tokens in code

3. **Regular updates**
   ```bash
   pip install -U -r requirements.txt
   ```

4. **Monitor logs**
   - Check for unusual activity
   - Set up alerts

5. **Limit admin access**
   - Use SUDO_USERS config
   - Restrict sensitive commands

---

## 💰 Cost Comparison

| Platform | Free Tier | Paid Plans | Best For |
|----------|-----------|------------|----------|
| **Render** | 512MB RAM, 750hrs/mo | From $7/mo | Small-medium bots |
| **Railway** | $5 credit/mo | $5/mo + usage | Developer-friendly |
| **Heroku** | 550hrs/mo | From $7/mo | Quick deploys |
| **VPS** | N/A | From $5/mo | Full control |

---

## 📞 Support

- **Issues**: GitHub Issues
- **Telegram**: @yourusername
- **Docs**: Check README.md

---

**Happy Deploying! 🎵**